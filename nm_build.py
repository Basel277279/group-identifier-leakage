"""Collapse New Mexico's 48.25 M production rows into one row per well.

Standard library only. Two streaming passes, constant memory.

WHAT THE CHECK RUN ESTABLISHED
    The grain is (well, pool, year, month, prd_knd_cde), not (well, pool,
    year, month): each month emits a separate row per product -- G gas,
    O oil, W water -- which is why 53% of rows looked like duplicates.
    89,405 of 89,406 producing wells join to wellhistory (99.999%).
    28% of rows carry amend_ind = Y. Whether those REPLACE an earlier filing
    or ADD to it is the one thing still unknown, so this script measures it
    rather than assuming.

PASS 1  per well: first GAS month, months reported, pools, and running
        cumulative per product -- both raw and excluding amendments, so the
        gap between them is visible.
PASS 2  only the first 12 reported months of each well, at full
        (well, pool, month, product) grain, keeping the latest mod_dte per
        key. Reports how many keys had competing filings and how much the
        value moved -- that is the amendment answer.

Writes nm_well_summary.csv (one row per producing well) and nm_build_log.txt.

    python nm_build.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import csv
import os
import shutil
import sys
import time

DATA = P.NM_DIR
CSV_DIR = os.path.join(DATA, 'csv')
OUT = os.path.join(CSV_DIR, 'nm_well_summary.csv')
MONTHS = 12                       # "first 365 days" = first 12 reported months

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


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def api_of(row, i_st, i_cy, i_wl):
    return (row[i_st].strip().zfill(2) + row[i_cy].strip().zfill(3)
            + row[i_wl].strip().zfill(5))


def wells_table(path):
    out = {}
    with open(path, newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if not (r.get('rec_termn_dte') or '').startswith('9999'):
                continue
            a = (r['api_st_cde'].strip().zfill(2)
                 + r['api_cnty_cde'].strip().zfill(3)
                 + r['api_well_idn'].strip().zfill(5))
            out[a] = {
                'lat': r.get('latitude', ''),
                'lon': r.get('longitude', ''),
                'operator': r.get('ogrid_cde', ''),
                'spud_dte': (r.get('spud_dte') or '')[:10],
                'directional_status': (r.get('directional_status') or '').strip(),
                'well_typ_cde': (r.get('well_typ_cde') or '').strip(),
                'well_name': r.get('well_name', ''),
                'tvd': r.get('dpth_tvd_num', ''),
                'md': r.get('dpth_mvd_num', ''),
            }
    return out


def open_prod():
    path = os.path.join(CSV_DIR, 'wcproduction.csv')
    fh = open(path, newline='', encoding='utf-8')
    rd = csv.reader(fh)
    cols = next(rd)
    ix = {c: i for i, c in enumerate(cols)}
    return fh, rd, ix



def date_key(s):
    """A date field as a sortable (YYYY, MM, DD) tuple, whatever format it is in.

    This used to be a raw string comparison, which orders `01/14/2025` before
    `2025-01-14` by punctuation rather than by date. That is not hypothetical:
    Colorado's ECMC exports the same filing in both formats in different files,
    and a string comparison there picks the wrong winner. New Mexico's
    `mod_dte` has looked like ISO in every extract read so far, so this changes
    no published number -- it removes the dependence on that continuing.
    """
    s = (s or '').strip()
    if not s or s.upper() in ('NULL', 'NONE'):
        return (0, 0, 0)
    d = s.replace('T', ' ').split()[0]
    try:
        if '-' in d:
            a, b, c = d.split('-')[:3]
            return (int(a), int(b), int(c)) if len(a) == 4 else (int(c), int(b), int(a))
        if '/' in d:
            a, b, c = d.split('/')[:3]
            return (int(c), int(a), int(b)) if len(c) == 4 else (0, 0, 0)
    except (ValueError, IndexError):
        pass
    return (0, 0, 0)


def main():
    sys.stdout = Tee(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'nm_build_log.txt'))
    t0 = time.time()

    # Keep the previous table under a dated name rather than overwriting it.
    # Two rebuilds have changed what this file means -- first which month opens
    # the 365-day window, then the addition of `n_months_in_window` -- and each
    # time the old table was worth keeping for comparison. A single fixed backup
    # name silently preserved only the first of them.
    if os.path.exists(OUT):
        stamp = time.strftime('%Y%m%d-%H%M%S',
                              time.localtime(os.path.getmtime(OUT)))
        keep = OUT.replace('.csv', '_prev_%s.csv' % stamp)
        if not os.path.exists(keep):
            shutil.copyfile(OUT, keep)
            print('kept the previous table as %s' % os.path.basename(keep))

    wells = wells_table(os.path.join(CSV_DIR, 'wellhistory.csv'))
    print('wellhistory: %d current wells (%.0f s)' % (len(wells), time.time() - t0))

    # ---------------------------------------------------------------- pass 1
    print('\npass 1: first month, span, cumulative ...')
    fh, rd, ix = open_prod()
    i_st, i_cy, i_wl = ix['api_st_cde'], ix['api_cnty_cde'], ix['api_well_idn']
    i_yr, i_mt, i_pool = ix['prodn_yr'], ix['prodn_mth'], ix['pool_idn']
    i_knd, i_amt, i_amd = ix['prd_knd_cde'], ix['prod_amt'], ix['amend_ind']
    i_day = ix.get('prodn_day_num')

    first = {}          # api -> min ym with positive GAS (see below)
    last = {}
    cum = {}            # api -> {kind: raw total}
    cum_n = {}          # api -> {kind: total excluding amend_ind Y}
    pools = {}          # api -> set of pool ids
    nrows = {}
    kinds = set()
    n = 0
    with fh:
        for row in rd:
            n += 1
            a = api_of(row, i_st, i_cy, i_wl)
            y, m = num(row[i_yr]), num(row[i_mt])
            if y is None or m is None:
                continue
            ym = int(y) * 12 + int(m)
            amt = num(row[i_amt]) or 0.0
            k = row[i_knd].strip()
            kinds.add(k)

            # The 365-day window opens on the first month with GAS, not on
            # the first month with any volume. New Mexico records four product
            # kinds -- C, G, O and W -- so a flowback month of water alone
            # used to start the clock, and 954 of the 15,901 modelled wells
            # (6.0%) had their window opened one to eleven months before their
            # first gas. Those wells carried some pre-gas months inside the
            # window and lost the tail of their real first gas year, which
            # diluted the measured effect: removing them raised the state's
            # validation inflation from +0.069 to +0.088, against +0.067 for a
            # random drop of the same size. Colorado already gates on gas or
            # oil (`co_build.py`), so this also makes the two states agree.
            # `last` still tracks any volume; it is descriptive only.
            if amt > 0 and k == 'G':
                if a not in first or ym < first[a]:
                    first[a] = ym
            if amt > 0:
                if a not in last or ym > last[a]:
                    last[a] = ym
            cum.setdefault(a, {})
            cum[a][k] = cum[a].get(k, 0.0) + amt
            if row[i_amd].strip() != 'Y':
                cum_n.setdefault(a, {})
                cum_n[a][k] = cum_n[a].get(k, 0.0) + amt
            pools.setdefault(a, set()).add(row[i_pool].strip())
            nrows[a] = nrows.get(a, 0) + 1

            if n % 4_000_000 == 0:
                print('\r  %d rows, %.0f s' % (n, time.time() - t0), end='')
    print('\r  %d rows, %.0f s' % (n, time.time() - t0))
    kinds = sorted(k for k in kinds if k)
    print('  product kinds: %s' % kinds)
    print('  wells with a positive gas month: %d' % len(first))

    # ---------------------------------------------------------------- pass 2
    print('\npass 2: first %d reported months, amendments resolved ...' % MONTHS)
    fh, rd, ix = open_prod()
    i_mod = ix.get('mod_dte')
    window = {}         # (api, pool, ym, kind) -> (mod_dte, amt)
    competing = 0
    changed = 0
    delta = 0.0
    n = 0
    with fh:
        for row in rd:
            n += 1
            a = api_of(row, i_st, i_cy, i_wl)
            f = first.get(a)
            if f is None:
                continue
            y, m = num(row[i_yr]), num(row[i_mt])
            if y is None or m is None:
                continue
            ym = int(y) * 12 + int(m)
            if ym < f or ym >= f + MONTHS:
                continue
            key = (a, row[i_pool].strip(), ym, row[i_knd].strip())
            mod = row[i_mod] if i_mod is not None else ''
            amt = num(row[i_amt]) or 0.0
            prev = window.get(key)
            if prev is None:
                window[key] = (mod, amt)
            else:
                competing += 1
                if amt != prev[1]:
                    changed += 1
                    delta += abs(amt - prev[1])
                if date_key(mod) >= date_key(prev[0]):
                    window[key] = (mod, amt)
            if n % 4_000_000 == 0:
                print('\r  %d rows, %d keys, %.0f s'
                      % (n, len(window), time.time() - t0), end='')
    print('\r  %d rows, %d keys, %.0f s' % (n, len(window), time.time() - t0))

    print('\n--- amendments, inside the first %d months ---' % MONTHS)
    print('  keys with more than one filing : %d' % competing)
    print('  of those, the value differed   : %d' % changed)
    print('  total absolute difference      : %.0f' % delta)
    if competing:
        print('  -> resolved by keeping the latest mod_dte')
    else:
        print('  -> no competing filings; amend_ind rows are additive, not '
              'replacements')

    # `window` is already keyed on the month, so the number of DISTINCT months
    # a well filed inside its first-365-day window comes free. It is written out
    # as `n_months_in_window` because without it New Mexico has no first-year
    # completeness rule at all, while Ohio requires four complete quarters and
    # Colorado twelve filed months. A well whose window has not yet elapsed --
    # the record ends in 2026-08, so anything first producing after 2025-09 --
    # contributes a PARTIAL sum under the same column name as a full year, and
    # because pad-mates come online together that truncation is pad-constant and
    # reads as leakage. Downstream, `leakage_experiment.load_new_mexico` keeps
    # only the wells that reach MONTHS.
    f365 = {}
    win_months = {}
    for (a, _pool, ym, k), (_mod, amt) in window.items():
        f365.setdefault(a, {})
        f365[a][k] = f365[a].get(k, 0.0) + amt
        win_months.setdefault(a, set()).add(ym)

    # ---------------------------------------------------------------- write
    hdr = (['api10', 'well_name', 'lat', 'lon', 'operator', 'spud_dte',
            'directional_status', 'well_typ_cde', 'tvd', 'md',
            'first_prod_ym', 'last_prod_ym', 'months_span',
            'n_months_in_window', 'n_pools',
            'n_prod_rows', 'in_wellhistory']
           + ['first365_' + k for k in kinds]
           + ['cum_' + k for k in kinds]
           + ['cumNoAmend_' + k for k in kinds])

    def ymtxt(v):
        if v is None:
            return ''
        y, m = divmod(int(v), 12)
        return '%04d-%02d' % (y, m) if m else '%04d-12' % (y - 1)

    with open(OUT, 'w', newline='', encoding='utf-8') as out:
        w = csv.writer(out)
        w.writerow(hdr)
        for a in sorted(cum):
            wi = wells.get(a, {})
            f, l = first.get(a), last.get(a)
            w.writerow(
                [a, wi.get('well_name', ''), wi.get('lat', ''), wi.get('lon', ''),
                 wi.get('operator', ''), wi.get('spud_dte', ''),
                 wi.get('directional_status', ''), wi.get('well_typ_cde', ''),
                 wi.get('tvd', ''), wi.get('md', ''),
                 ymtxt(f), ymtxt(l),
                 (l - f + 1) if (f is not None and l is not None) else '',
                 len(win_months.get(a, ())),
                 len(pools.get(a, ())), nrows.get(a, 0),
                 1 if a in wells else 0]
                + ['%.0f' % f365.get(a, {}).get(k, 0.0) for k in kinds]
                + ['%.0f' % cum.get(a, {}).get(k, 0.0) for k in kinds]
                + ['%.0f' % cum_n.get(a, {}).get(k, 0.0) for k in kinds])

    print('\nwrote %s  (%d wells, %.1f MB)'
          % (OUT, len(cum), os.path.getsize(OUT) / 1e6))
    print('done in %.0f s' % (time.time() - t0))
    sys.stdout.flush()


if __name__ == '__main__':
    main()
