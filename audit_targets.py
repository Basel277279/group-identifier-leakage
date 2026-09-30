"""Settle three open questions about how the target was built, on the raw files.

Run this on the machine that holds the regulator downloads. It reads the same
files `co_build.py` and `nm_build.py` read, changes nothing, and writes two
small CSVs plus a printed summary. Send the two CSVs back; they are a few
hundred kilobytes, not gigabytes.

    python3 audit_targets.py --co  "E:/P3_Data/Data/Colorado"
    python3 audit_targets.py --nm  "E:/P3_Data/Data/NewMexico/csv"
    python3 audit_targets.py --co "..." --nm "..."        both at once

WHAT IT ANSWERS

1. COLORADO -- is `n_months_in_window` counting months or rows?
   `co_build.py:212` increments a counter once per production ROW, and
   Colorado files one row per well-month PER FORMATION. Everything downstream
   keeps wells whose counter is exactly 12. If the counter is really rows,
   then a well completed in two formations reaches 12 after six months and is
   admitted with half a year of gas called "the first 365 days", while a
   genuinely complete two-formation well counts 24 and is dropped. This
   recomputes both the row count and the DISTINCT-month count for every well
   and reports how many wells the two disagree about.

2. COLORADO -- does `monthly_prod.csv` overlap the annual files?
   `prod_files()` appends it unconditionally and nothing deduplicates, so any
   (well, month, formation) present in both is counted twice in first365_G.
   This counts the overlapping keys.

3. NEW MEXICO -- can the 365-day window open on a month with no gas?
   `nm_build.py:137` starts the window at the first month with any positive
   volume, over all product kinds, and New Mexico records C, O and W as well
   as G. Colorado requires gas or oil. This reports, per well, the first month
   with any volume and the first month with gas, and counts the wells where
   they differ.

Outputs: co_month_audit.csv, nm_firstmonth_audit.csv
"""
import argparse
import collections
import csv
import glob
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_NM = os.path.join(HERE, 'Data', 'NewMexico', 'csv')
DEFAULT_CO = os.path.join(HERE, 'Data')


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------- Colorado
def colorado(data):
    files = sorted(glob.glob(os.path.join(data, '*_prod_reports.csv')))
    monthly = os.path.join(data, 'monthly_prod.csv')
    has_monthly = os.path.exists(monthly)
    if has_monthly:
        files.append(monthly)
    if not files:
        print('Colorado: no production files under %s' % data)
        return
    print('Colorado: %d files%s' % (len(files),
          ', including monthly_prod.csv' if has_monthly else ''))

    first = {}                       # api -> earliest ym with gas or oil
    keys = collections.defaultdict(set)   # api -> {(ym, formation)} seen where
    annual_keys = set()
    monthly_keys = set()

    for p in files:
        is_monthly = os.path.basename(p) == 'monthly_prod.csv'
        with open(p, newline='', encoding='utf-8-sig', errors='replace') as fh:
            rd = csv.reader(fh)
            ix = {c: i for i, c in enumerate(next(rd))}
            need = ('ApiCountyCode', 'ApiSequenceNumber', 'ReportYear',
                    'ReportMonth', 'GasProduced', 'OilProduced')
            if any(c not in ix for c in need):
                print('  %-30s SKIPPED' % os.path.basename(p))
                continue
            i_cy, i_sq = ix['ApiCountyCode'], ix['ApiSequenceNumber']
            i_y, i_m = ix['ReportYear'], ix['ReportMonth']
            i_g, i_o = ix['GasProduced'], ix['OilProduced']
            # whatever column distinguishes the formation, if any
            i_f = next((ix[c] for c in ('FormationCode', 'Formation',
                                        'ApiSidetrack', 'FacilityId')
                        if c in ix), None)
            for row in rd:
                try:
                    api = row[i_cy].strip().zfill(3) + row[i_sq].strip().zfill(5)
                    ym = int(row[i_y]) * 12 + int(row[i_m])
                except (ValueError, IndexError):
                    continue
                g, o = num(row[i_g]) or 0.0, num(row[i_o]) or 0.0
                f = row[i_f].strip() if i_f is not None and i_f < len(row) else ''
                k = (api, ym, f)
                (monthly_keys if is_monthly else annual_keys).add(k)
                if (g > 0 or o > 0) and (api not in first or ym < first[api]):
                    first[api] = ym
                keys[api].add((ym, f))
        print('  read %s' % os.path.basename(p))

    dup = annual_keys & monthly_keys
    print('\n2. monthly_prod.csv overlap with the annual files: %d duplicated '
          '(well, month, formation) keys' % len(dup))
    if dup:
        print('   -> those months are counted TWICE in cum_G and first365_G')

    out = os.path.join(HERE, 'co_month_audit.csv')
    disagree = short = 0
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['api8', 'rows_in_window', 'distinct_months_in_window'])
        for api, f0 in first.items():
            win = [(ym, fm) for (ym, fm) in keys[api] if f0 <= ym < f0 + 12]
            rows = len(win)
            months = len({ym for ym, _ in win})
            w.writerow([api, rows, months])
            if rows != months:
                disagree += 1
            if rows == 12 and months < 12:
                short += 1
    print('\n1. wells where the row count differs from the month count: %d of %d'
          % (disagree, len(first)))
    print('   wells admitted by "rows == 12" that have FEWER than 12 real '
          'months: %d' % short)
    print('   -> these are the wells whose "first 365 days" is short')
    print('   wrote %s' % out)


# ------------------------------------------------------------- New Mexico
def new_mexico(csv_dir):
    path = os.path.join(csv_dir, 'wcproduction.csv')
    if not os.path.exists(path):
        print('New Mexico: %s not found' % path)
        return
    print('New Mexico: reading %s' % path)
    any_first, gas_first = {}, {}
    n = 0
    with open(path, newline='', encoding='utf-8-sig', errors='replace') as fh:
        rd = csv.reader(fh)
        ix = {c: i for i, c in enumerate(next(rd))}
        need = ('api_st_cde', 'api_cnty_cde', 'api_well_idn', 'prodn_yr',
                'prodn_mth', 'prd_knd_cde', 'prod_amt')
        if any(c not in ix for c in need):
            print('  missing columns: %s' % [c for c in need if c not in ix])
            return
        i_st, i_cy, i_wl = ix['api_st_cde'], ix['api_cnty_cde'], ix['api_well_idn']
        i_yr, i_mt = ix['prodn_yr'], ix['prodn_mth']
        i_knd, i_amt = ix['prd_knd_cde'], ix['prod_amt']
        for row in rd:
            n += 1
            if n % 2_000_000 == 0:
                print('  %d million rows, %d wells so far' %
                      (n // 1_000_000, len(any_first)), flush=True)
            try:
                a = (row[i_st].strip().zfill(2) + row[i_cy].strip().zfill(3)
                     + row[i_wl].strip().zfill(5))
                ym = int(row[i_yr]) * 12 + int(row[i_mt])
            except (ValueError, IndexError):
                continue
            amt = num(row[i_amt]) or 0.0
            if amt <= 0:
                continue
            k = row[i_knd].strip().upper()
            if a not in any_first or ym < any_first[a]:
                any_first[a] = ym
            if k == 'G' and (a not in gas_first or ym < gas_first[a]):
                gas_first[a] = ym
        print('  %d rows' % n)

    out = os.path.join(HERE, 'nm_firstmonth_audit.csv')
    diff = 0
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['api10', 'first_any_ym', 'first_gas_ym', 'months_early'])
        for a, f0 in any_first.items():
            fg = gas_first.get(a)
            early = (fg - f0) if fg is not None else ''
            w.writerow([a, f0, fg if fg is not None else '', early])
            if fg is not None and fg > f0:
                diff += 1
    print('\n3. wells whose window opens BEFORE their first gas month: %d of %d'
          % (diff, len(any_first)))
    print('   -> for those wells first365_G omits the tail of the real first '
          'gas year')
    print('   wrote %s' % out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--co', help='folder holding YYYY_prod_reports.csv')
    ap.add_argument('--nm', help='folder holding wcproduction.csv')
    a = ap.parse_args()

    # With no arguments -- pressing Run in an IDE -- fall back to the folders
    # that sit beside this script, so the script needs no configuring.
    co, nm = a.co, a.nm
    if not co and not nm:
        # New Mexico only by default: its 4.35 GB wcproduction.csv is the
        # part that cannot be moved off this machine. Colorado is done
        # elsewhere; add --co to run it here too.
        if os.path.exists(os.path.join(DEFAULT_NM, 'wcproduction.csv')):
            nm = DEFAULT_NM
        if not co and not nm:
            print('Nothing found to audit.')
            print('  looked for %s' % os.path.join(DEFAULT_NM, 'wcproduction.csv'))
            print('  looked for %s' % os.path.join(DEFAULT_CO, '*_prod_reports.csv'))
            print('\nPass a folder explicitly if the data is elsewhere:')
            ap.print_help()
            sys.exit(1)
        print('No arguments given; using the data beside this script.')
        if nm:
            print('  New Mexico: %s' % nm)
        if co:
            print('  Colorado:   %s' % co)
        print()

    if co:
        colorado(co)
    if nm:
        print()
        new_mexico(nm)
