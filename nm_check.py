"""Diagnose the New Mexico production table before building anything on it.

wcproduction.csv is 4.35 GB / 48.25 M rows, too big to move, so this runs where
the file is and writes nm_check_log.txt beside itself.

STANDARD LIBRARY ONLY -- no pandas, nothing to install. It is also faster than
a DataFrame version here, because nothing is materialised.

It answers four questions and asserts nothing:
  1. What columns does wcproduction have, and what do the first rows look like?
  2. Does every producing well exist in wellhistory?  (the Colorado question)
  3. What is the reporting grain -- is (well, pool, year, month) unique, or do
     amendments duplicate it?
  4. What period does it cover, and how much is horizontal?

    python nm_check.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import csv
import itertools
import os
import sys
import time

DATA = P.NM_DIR
CSV_DIR = os.path.join(DATA, 'csv')
BLOCK = 1_000_000        # duplicate detection window, rows

ID_COLS = {'api_st_cde', 'api_cnty_cde', 'api_well_idn', 'pool_idn',
           'prodn_mth', 'prodn_yr', 'ogrid_cde', 'eff_dte', 'amend_ind',
           'c115_wc_stat_cde', 'mod_dte', 'prod_prop_idn', 'wc_stat_cde',
           'prodn_meth_cde', 'well_typ_cde', 'inj_knd_cde'}

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


def load_wells(path):
    """Current wells only, with the flags we need."""
    wells, geo, horiz = set(), set(), set()
    with open(path, newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if not (r.get('rec_termn_dte') or '').startswith('9999'):
                continue
            a = (r['api_st_cde'].strip().zfill(2)
                 + r['api_cnty_cde'].strip().zfill(3)
                 + r['api_well_idn'].strip().zfill(5))
            wells.add(a)
            lat, lon = num(r.get('latitude')), num(r.get('longitude'))
            if lat is not None and lon is not None \
                    and 31 <= lat <= 37.2 and -109.2 <= lon <= -102.9:
                geo.add(a)
            if (r.get('directional_status') or '').strip() == 'H':
                horiz.add(a)
    return wells, geo, horiz


def main():
    sys.stdout = Tee(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'nm_check_log.txt'))
    prod_path = os.path.join(CSV_DIR, 'wcproduction.csv')
    well_path = os.path.join(CSV_DIR, 'wellhistory.csv')
    for p in (prod_path, well_path):
        if not os.path.exists(p):
            print('MISSING %s' % p)
            return
    print('wcproduction.csv  %.2f GB' % (os.path.getsize(prod_path) / 1e9))

    t0 = time.time()
    wells, geo, horiz = load_wells(well_path)
    print('wellhistory: %d current wells, %d with coordinates, %d horizontal'
          ' (%.0f s)' % (len(wells), len(geo), len(horiz), time.time() - t0))

    with open(prod_path, newline='', encoding='utf-8') as fh:
        rd = csv.reader(fh)
        cols = next(rd)
        print('\n--- columns (%d) ---\n%s' % (len(cols), cols))

        ix = {c: i for i, c in enumerate(cols)}
        need = ['api_st_cde', 'api_cnty_cde', 'api_well_idn',
                'prodn_yr', 'prodn_mth']
        missing = [c for c in need if c not in ix]
        if missing:
            print('\nCannot proceed: wcproduction lacks %s' % missing)
            return
        i_st, i_cy, i_wl = ix['api_st_cde'], ix['api_cnty_cde'], ix['api_well_idn']
        i_yr, i_mt = ix['prodn_yr'], ix['prodn_mth']
        i_pool = ix.get('pool_idn')
        i_amd = ix.get('amend_ind')
        measures = [c for c in cols if c not in ID_COLS]
        mi = [(c, ix[c]) for c in measures]
        print('treating as measures: %s' % measures)

        print('\n--- first 3 rows ---')
        sample = []
        for _ in range(3):
            try:
                sample.append(next(rd))
            except StopIteration:
                break
        for row in sample:
            print('  ' + ' | '.join('%s=%s' % (c, v) for c, v in zip(cols, row)))

        print('\nscanning ...')
        rows = 0
        prod_wells = set()
        ym_min = ym_max = None
        amend = {}
        totals = {c: 0.0 for c, _ in mi}
        seen = set()
        dup_rows = 0
        key_rows = 0

        # chain, never list() -- 48 M rows must not be materialised
        for row in itertools.chain(sample, rd):
            rows += 1
            a = (row[i_st].strip().zfill(2) + row[i_cy].strip().zfill(3)
                 + row[i_wl].strip().zfill(5))
            prod_wells.add(a)

            y, m = num(row[i_yr]), num(row[i_mt])
            if y is not None and m is not None:
                ym = int(y) * 12 + int(m)
                ym_min = ym if ym_min is None else min(ym_min, ym)
                ym_max = ym if ym_max is None else max(ym_max, ym)

            if i_amd is not None:
                k = row[i_amd].strip()
                amend[k] = amend.get(k, 0) + 1

            key = (a, row[i_pool] if i_pool is not None else '',
                   row[i_yr], row[i_mt])
            if key in seen:
                dup_rows += 1
            else:
                seen.add(key)
            key_rows += 1
            if len(seen) >= BLOCK:
                seen.clear()

            for c, j in mi:
                v = num(row[j])
                if v is not None:
                    totals[c] += v

            if rows % 2_000_000 == 0:
                print('\r  %d rows, %.0f s' % (rows, time.time() - t0), end='')
        print('\r  %d rows, %.0f s' % (rows, time.time() - t0))

    matched = prod_wells & wells
    print('\n--- join ---')
    print('production rows              %12d' % rows)
    print('distinct producing wells     %12d' % len(prod_wells))
    print('found in wellhistory         %12d   %.3f%%'
          % (len(matched), 100 * len(matched) / max(len(prod_wells), 1)))
    print('with usable coordinates      %12d   %.3f%%'
          % (len(prod_wells & geo), 100 * len(prod_wells & geo) / max(len(prod_wells), 1)))
    print('flagged horizontal           %12d   %.3f%%'
          % (len(prod_wells & horiz), 100 * len(prod_wells & horiz) / max(len(prod_wells), 1)))
    unmatched = prod_wells - wells
    if unmatched:
        print('unmatched: %d wells, sample %s'
              % (len(unmatched), sorted(unmatched)[:10]))

    print('\n--- grain ---')
    print('rows repeating (well, pool, year, month) inside a %d-row window:'
          % BLOCK)
    print('  %d of %d  (%.3f%%)   -- a lower bound, not the true rate'
          % (dup_rows, key_rows, 100 * dup_rows / max(key_rows, 1)))
    if amend:
        print('amend_ind: %s' % amend)

    def ymtxt(v):
        y, m = divmod(int(v), 12)
        return '%04d-%02d' % (y, m) if m else '%04d-12' % (y - 1)
    if ym_min is not None:
        print('\n--- period ---')
        print('reporting months %s to %s' % (ymtxt(ym_min), ymtxt(ym_max)))

    print('\n--- measure totals (sanity only) ---')
    for c, _ in mi:
        print('  %-22s %22.0f' % (c, totals[c]))

    print('\ndone in %.0f s' % (time.time() - t0))
    sys.stdout.flush()


if __name__ == '__main__':
    main()
