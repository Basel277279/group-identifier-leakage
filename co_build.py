"""Build the Colorado well table: one row per well, same shape as New Mexico's.

Standard library only -- no pandas, no pyshp, nothing to install. The well
attributes come out of the shapefile's .dbf, which is read directly from inside
WELLS_SHP.ZIP by the small reader below; the geometry is not needed, because
the .dbf already carries Latitude and Longitude.

INPUTS, all already downloaded into Data\\ :
    WELLS_SHP.ZIP                 124,415 wells: API, lat/long, spud, operator,
                                  Max_MD, Max_TVD, Loc_Qual, field, status
    YYYY_prod_reports.csv         monthly production, one row per well-month
                                  per formation; ~657k rows and 100 MB a year

METHOD
    Two streaming passes over the production files, as for New Mexico:
      pass 1  per well -- first month with positive volume, last month,
              cumulative gas/oil/water
      pass 2  per well -- the first twelve months from that start
    Memory stays at one entry per well (about 50k), never one per well-month.

    The production key is ApiCountyCode + ApiSequenceNumber + ApiSidetrack; the
    shapefile is keyed on county + sequence only, so sidetracks are summed into
    their parent wellbore, which is the unit the shapefile describes.

    python co_build.py              years 2010-2026
    python co_build.py 1999 2026    any range

Writes co_well_summary.csv and co_build_log.txt.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import csv
import glob
import os
import struct
import sys
import time
import zipfile

DATA = P.DATA
OUT_DIR = os.path.join(DATA, 'Colorado')
MONTHS = 12

csv.field_size_limit(1 << 24)


class Tee:
    def __init__(self, path):
        self.term = sys.stdout
        self.log = open(path, 'w', encoding='utf-8')

    def write(self, s):
        self.term.write(s)
        self.log.write(s)

    def flush(self):
        self.term.flush()
        self.log.flush()


# --------------------------------------------------------------- dbf reader
def read_dbf(fh, wanted=None):
    """Yield dicts from a dBASE III/IV .dbf. Enough of the format for ESRI."""
    head = fh.read(32)
    n_rec, hdr_len, rec_len = struct.unpack('<xxxxIHH20x', head)
    fields = []
    while True:
        raw = fh.read(32)
        if raw[0:1] in (b'\r', b''):
            break
        name = raw[:11].split(b'\x00')[0].decode('latin-1').strip()
        ftype = raw[11:12].decode('latin-1')
        flen = raw[16]
        fields.append((name, ftype, flen))
    fh.seek(hdr_len)
    keep = [(i, f) for i, f in enumerate(fields)
            if wanted is None or f[0] in wanted]
    for _ in range(n_rec):
        rec = fh.read(rec_len)
        if not rec or rec[0:1] == b'*':          # deleted
            continue
        row, pos = {}, 1
        for i, (name, ftype, flen) in enumerate(fields):
            val = rec[pos:pos + flen]
            pos += flen
            if wanted is not None and name not in wanted:
                continue
            s = val.decode('latin-1').strip()
            if ftype in 'NF':
                try:
                    s = float(s) if ('.' in s or ftype == 'F') else int(s)
                except ValueError:
                    s = None
            elif ftype == 'D' and len(s) == 8:
                s = '%s-%s-%s' % (s[:4], s[4:6], s[6:])
            row[name] = s
        yield row


def load_wells():
    zpath = os.path.join(DATA, 'WELLS_SHP.ZIP')
    want = {'API', 'API_County', 'API_Seq', 'API_Label', 'Operat_Num',
            'Operator', 'Well_Name', 'Spud_Date', 'Ground_Ele', 'Max_MD',
            'Max_TVD', 'Field_Name', 'Facil_Stat', 'Well_Class', 'Loc_Qual',
            'Latitude', 'Longitude'}
    with zipfile.ZipFile(zpath) as zf:
        name = [n for n in zf.namelist() if n.lower().endswith('.dbf')][0]
        with zf.open(name) as fh:
            import io
            buf = io.BytesIO(fh.read())
        out = {}
        for r in read_dbf(buf, want):
            api = str(r.get('API') or '').strip().zfill(8)
            if api and api != '00000000':
                out[api] = r
    return out


def prod_files(y0, y1):
    fs = []
    for y in range(y0, y1 + 1):
        p = os.path.join(DATA, '%d_prod_reports.csv' % y)
        if os.path.exists(p):
            fs.append(p)
    p = os.path.join(DATA, 'monthly_prod.csv')          # current year, monthly
    if os.path.exists(p):
        fs.append(p)
    return fs


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def nominal_year(path):
    """The year in `YYYY_prod_reports.csv`, or None for `monthly_prod.csv`."""
    base = os.path.basename(path)
    head = base.split('_')[0]
    return int(head) if head.isdigit() and len(head) == 4 else None


def accepted_key(s):
    """`AcceptedDate` as a sortable YYYYMMDD integer, in either format it comes in.

    The ECMC exports the SAME filing in two formats -- `01/14/2025 00:00:00` in
    one file and `2025-01-14 00:00:00.000` in another -- so a string comparison
    orders them by punctuation instead of by date. Parse, don't compare text.
    """
    s = (s or '').strip()
    if not s or s.upper() == 'NULL':
        return 0
    d = s.split()[0]
    try:
        if '-' in d:
            y, m, dd = d.split('-')[:3]
        elif '/' in d:
            m, dd, y = d.split('/')[:3]
        else:
            return 0
        return int(y) * 10000 + int(m) * 100 + int(dd)
    except (ValueError, IndexError):
        return 0


def _reader(p):
    """Yield (key, pref, api, ym, g, o, w) per row, or None if unreadable.

    `key` is (API, sidetrack, month, formation) -- the grain at which the ECMC
    files production. `pref` orders competing filings of one key: later
    AcceptedDate first, then higher DocNum.
    """
    fh = open(p, newline='', encoding='utf-8-sig', errors='replace')
    rd = csv.reader(fh)
    cols = next(rd)
    ix = {c: i for i, c in enumerate(cols)}
    need = ('ApiCountyCode', 'ApiSequenceNumber', 'ReportYear',
            'ReportMonth', 'GasProduced', 'OilProduced')
    missing = [c for c in need if c not in ix]
    if missing:
        fh.close()
        print('  %-34s SKIPPED, columns %s' % (os.path.basename(p), missing))
        return
    i_cy, i_sq = ix['ApiCountyCode'], ix['ApiSequenceNumber']
    i_y, i_m = ix['ReportYear'], ix['ReportMonth']
    i_g, i_o = ix['GasProduced'], ix['OilProduced']
    i_w, i_st = ix.get('WaterProduced'), ix.get('ApiSidetrack')
    i_fm, i_ac = ix.get('FormationCode'), ix.get('AcceptedDate')
    i_dc = ix.get('DocNum')
    with fh:
        for row in rd:
            try:
                api = row[i_cy].strip().zfill(3) + row[i_sq].strip().zfill(5)
                y, m = int(row[i_y]), int(row[i_m])
            except (ValueError, IndexError):
                continue
            st = row[i_st].strip() if i_st is not None and i_st < len(row) else ''
            fm = row[i_fm].strip() if i_fm is not None and i_fm < len(row) else ''
            ac = row[i_ac] if i_ac is not None and i_ac < len(row) else ''
            try:
                dc = int(row[i_dc]) if i_dc is not None and row[i_dc].strip().isdigit() else 0
            except (ValueError, IndexError):
                dc = 0
            ym = y * 12 + m
            yield ((api, st, ym, fm), (accepted_key(ac), dc), api, ym,
                   num(row[i_g]) or 0.0, num(row[i_o]) or 0.0,
                   (num(row[i_w]) or 0.0) if i_w is not None else 0.0)


def rolling_index(files):
    """Keys that appear OUT OF PLACE, with the best filing of each.

    WHY THIS EXISTS. `co_build.py` used to add every row it read. That was safe
    while each `YYYY_prod_reports.csv` held only year YYYY, and it stopped being
    safe: `2025_prod_reports.csv` is a rolling extract spanning 2000-2025 and
    `monthly_prod.csv` spans 2004-2026, so the same filing is read twice and its
    volume added twice. Measured on the 2024 and 2025 annual files and
    monthly_prod.csv: 178,504 of 1,723,363 (API, sidetrack, month, formation)
    keys are filed more than once, and they are NOT amendments -- the duplicates
    carry the same DocNum and differ only in how the date is formatted. Removing
    them changes `first365_G` for 1,254 of the 12,139 wells in the Colorado
    table, 10.3%, by a median factor of 1.27 and at worst 2.33.

    Holding every key in memory would cost gigabytes, and it is not necessary: a
    duplicate can only arise from a row that sits outside its file's nominal
    year, or from `monthly_prod.csv`, which has no nominal year. Those are the
    only keys indexed here -- a few hundred thousand rather than ten million.
    Rows that sit in their own year are then skipped if and only if a rolling
    row claims the same key, and rolling rows compete with each other on
    AcceptedDate. `check_disjoint` below verifies the assumption this rests on.
    """
    best = {}
    for p in files:
        ny = nominal_year(p)
        t, n = time.time(), 0
        for key, pref, _api, ym, _g, _o, _w in _reader(p) or ():
            if ny is not None and (ym - 1) // 12 == ny:
                continue                      # in its own year: not rolling
            n += 1
            if best.get(key, (-1, -1)) < pref:
                best[key] = pref
        print('  %-34s %8d rolling rows  %5.0f s'
              % (os.path.basename(p), n, time.time() - t), flush=True)
    print('  indexed %d out-of-place keys' % len(best), flush=True)
    return best


def check_disjoint(files):
    """Fail loudly if two single-year files claim the same year.

    The de-duplication above assumes the in-place rows of different annual files
    cannot collide. That holds because each names its year; this checks it
    rather than trusting the filenames.
    """
    seen = {}
    for p in files:
        ny = nominal_year(p)
        if ny is None:
            continue
        if ny in seen:
            raise SystemExit('%s and %s both claim %d; de-duplication assumes '
                             'one file per year.'
                             % (os.path.basename(seen[ny]),
                                os.path.basename(p), ny))
        seen[ny] = p


def scan(files, handler, best):
    """Feed each DISTINCT filing to `handler` exactly once."""
    used = set()
    for p in files:
        ny = nominal_year(p)
        t, n, skipped = time.time(), 0, 0
        for key, pref, api, ym, g, o, w in _reader(p) or ():
            n += 1
            rolling = ny is None or (ym - 1) // 12 != ny
            if rolling:
                if best.get(key) != pref or key in used:
                    skipped += 1
                    continue
                used.add(key)
            elif key in best:
                skipped += 1          # a later export of this filing wins
                continue
            handler(api, ym, g, o, w)
        print('  %-34s %8d rows, %d duplicates dropped  %5.0f s'
              % (os.path.basename(p), n, skipped, time.time() - t), flush=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sys.stdout = Tee(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'co_build_log.txt'))
    y0 = int(sys.argv[1]) if len(sys.argv) > 2 else 2010
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    t0 = time.time()

    print('reading WELLS_SHP.ZIP ...')
    wells = load_wells()
    print('  %d wells in the shapefile' % len(wells))

    files = prod_files(y0, y1)
    print('\nproduction files (%d):' % len(files))
    check_disjoint(files)

    print('\npass 0: indexing filings that appear in more than one file ...')
    best = rolling_index(files)

    first, last, cum = {}, {}, {}

    def pass1(api, ym, g, o, w):
        if g > 0 or o > 0:
            if api not in first or ym < first[api]:
                first[api] = ym
            if api not in last or ym > last[api]:
                last[api] = ym
        c = cum.get(api)
        if c is None:
            cum[api] = [g, o, w, 1]
        else:
            c[0] += g; c[1] += o; c[2] += w; c[3] += 1

    print('\npass 1 ...')
    scan(files, pass1, best)
    print('  %d wells with production, %d with a positive month'
          % (len(cum), len(first)))

    win = {}

    # Colorado files one row per well-month PER FORMATION, so counting rows is
    # not counting months: a well completed in two formations would reach
    # twelve rows in six months, and everything downstream keeps the wells
    # whose count is exactly twelve. On this vintage of the data the two agree
    # for every analysis well -- each files a single row per month
    # in its first year, verified against the raw files -- so this changes no
    # published number. It is a distinct-month count so that a re-user with a
    # different vintage is not silently given a short window.
    win_months = {}

    def pass2(api, ym, g, o, w):
        f = first.get(api)
        if f is None or ym < f or ym >= f + MONTHS:
            return
        win_months.setdefault(api, set()).add(ym)
        v = win.get(api)
        if v is None:
            win[api] = [g, o, w, 0]
        else:
            v[0] += g; v[1] += o; v[2] += w
        win[api][3] = len(win_months[api])

    print('\npass 2 ...')
    scan(files, pass2, best)
    print('  %d wells with a first-12-month window' % len(win))

    def ymtxt(v):
        if v is None:
            return ''
        y, m = divmod(int(v), 12)
        return '%04d-%02d' % (y, m) if m else '%04d-12' % (y - 1)

    out = os.path.join(OUT_DIR, 'co_well_summary.csv')
    hdr = ['api8', 'well_name', 'lat', 'lon', 'operator', 'operator_name',
           'spud_dte', 'loc_qual', 'field', 'well_class', 'status',
           'ground_elev', 'max_md', 'max_tvd', 'first_prod_ym', 'last_prod_ym',
           'months_span', 'n_rows', 'first365_G', 'first365_O', 'first365_W',
           'n_months_in_window', 'cum_G', 'cum_O', 'cum_W', 'in_shapefile']
    n_geo = 0
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        wr = csv.writer(fh)
        wr.writerow(hdr)
        for api in sorted(cum):
            w = wells.get(api, {})
            f, l = first.get(api), last.get(api)
            c = cum[api]
            v = win.get(api, [0, 0, 0, 0])
            lat, lon = w.get('Latitude'), w.get('Longitude')
            if lat and lon and 36 < float(lat) < 41.1 and -110 < float(lon) < -101:
                n_geo += 1
            wr.writerow([
                api, w.get('Well_Name', ''), lat if lat is not None else '',
                lon if lon is not None else '', w.get('Operat_Num', ''),
                w.get('Operator', ''), w.get('Spud_Date', ''),
                w.get('Loc_Qual', ''), w.get('Field_Name', ''),
                w.get('Well_Class', ''), w.get('Facil_Stat', ''),
                w.get('Ground_Ele', ''), w.get('Max_MD', ''), w.get('Max_TVD', ''),
                ymtxt(f), ymtxt(l),
                (l - f + 1) if (f is not None and l is not None) else '',
                c[3], '%.0f' % v[0], '%.0f' % v[1], '%.0f' % v[2], v[3],
                '%.0f' % c[0], '%.0f' % c[1], '%.0f' % c[2],
                1 if api in wells else 0])

    matched = sum(1 for a in cum if a in wells)
    print('\nwrote %s' % out)
    print('  %d producing wells | %d matched to the shapefile (%.3f%%) | %d with coordinates'
          % (len(cum), matched, 100.0 * matched / max(len(cum), 1), n_geo))
    print('done in %.0f s' % (time.time() - t0))
    sys.stdout.flush()


if __name__ == '__main__':
    main()
