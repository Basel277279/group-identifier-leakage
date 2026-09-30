"""How many Colorado wells would the corrected month counter admit or drop?

`co_build.py` used to set `n_months_in_window` by counting production ROWS,
and Colorado files one row per well-month per formation. Everything
downstream keeps the wells whose count is exactly 12. So the old rule

  * ADMITTED a well with 2 formations x 6 months (12 rows, 6 real months), and
  * DROPPED  a well with 2 formations x 12 months (24 rows, 12 real months).

Scanning the raw annual files for the 10,858 wells already in
`co_analysis.csv` showed none of the first kind. This asks the other question,
over every Colorado well rather than the ones the old rule already let
through: how many wells have a full twelve distinct months in their window but
more than twelve rows, and so would be newly admitted?

Two passes over the staged production files, as `co_build.py` does:
  pass 1  each well's first month with gas or oil
  pass 2  distinct months, and rows, inside [first, first + 12)

    python3 co_admit_scan.py <dir with *_prod_reports.csv and monthly_prod.csv>
"""
import collections
import csv
import glob
import os
import sys


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def files_in(d):
    fs = sorted(glob.glob(os.path.join(d, '*_prod_reports.csv')))
    m = os.path.join(d, 'monthly_prod.csv')
    if os.path.exists(m):
        fs.append(m)
    return fs


def each_row(path):
    with open(path, newline='', encoding='utf-8-sig', errors='replace') as fh:
        rd = csv.reader(fh)
        ix = {c: i for i, c in enumerate(next(rd))}
        need = ('ApiCountyCode', 'ApiSequenceNumber', 'ReportYear',
                'ReportMonth', 'GasProduced', 'OilProduced')
        if any(c not in ix for c in need):
            return
        cy, sq = ix['ApiCountyCode'], ix['ApiSequenceNumber']
        iy, im = ix['ReportYear'], ix['ReportMonth']
        ig, io = ix['GasProduced'], ix['OilProduced']
        for r in rd:
            try:
                api = r[cy].strip().zfill(3) + r[sq].strip().zfill(5)
                ym = int(r[iy]) * 12 + int(r[im])
            except (ValueError, IndexError):
                continue
            yield api, ym, num(r[ig]) or 0.0, num(r[io]) or 0.0


def main(d):
    fs = files_in(d)
    if not fs:
        print('no production files under %s' % d)
        return 1
    print('%d files' % len(fs))

    first = {}
    for p in fs:
        n = 0
        for api, ym, g, o in each_row(p):
            n += 1
            if (g > 0 or o > 0) and (api not in first or ym < first[api]):
                first[api] = ym
        print('  pass 1  %-26s %9d rows' % (os.path.basename(p), n))
    print('%d wells with a positive gas-or-oil month' % len(first))

    months = collections.defaultdict(set)
    rows = collections.Counter()
    for p in fs:
        for api, ym, g, o in each_row(p):
            f = first.get(api)
            if f is None or ym < f or ym >= f + 12:
                continue
            months[api].add(ym)
            rows[api] += 1
        print('  pass 2  %-26s done' % os.path.basename(p))

    old_admits = new_admits = agree = short = 0
    for api in first:
        m, r = len(months.get(api, ())), rows.get(api, 0)
        old = (r == 12)
        new = (m == 12)
        if old and new:
            agree += 1
        elif old and not new:
            short += 1          # old rule let a SHORT window through
        elif new and not old:
            new_admits += 1     # corrected rule admits a well the old one lost
        old_admits += old
    print()
    print('wells the OLD rule admitted (rows == 12)          : %d' % old_admits)
    print('  of those, a genuinely full 12 months            : %d' % agree)
    print('  of those, FEWER than 12 real months             : %d' % short)
    print('wells the CORRECTED rule newly admits (months==12): %d' % new_admits)
    print()
    print('These counts are before the lateral > 1000 ft and shapefile')
    print('filters, so the newly admitted figure is an upper bound on how')
    print('much the Colorado analysis set would grow.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else '.'))
