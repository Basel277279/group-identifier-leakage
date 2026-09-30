"""Scan staged Colorado production files and accumulate, for the analysis
wells only, what actually falls inside each well's first-365-day window.

Run once per staged batch; state persists in co_window_state.json so the raw
files can be deleted between batches.

    python3 co_window_scan.py <file> [<file> ...]
    python3 co_window_scan.py --report
"""
import collections
import csv
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

STATE = P.out('co_window_state.json')
ANALYSIS = os.path.join(P.CO_DIR, 'co_analysis.csv')


def load_windows():
    co = pd.read_csv(ANALYSIS, low_memory=False)
    w = {}
    for api, fp in zip(co.api8.astype(str).str.zfill(8), co.first_prod_ym):
        y, m = str(fp).split('-')
        f0 = int(y) * 12 + int(m)
        w[api] = f0
    return w


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as fh:
            s = json.load(fh)
        return {k: set(map(tuple, v)) for k, v in s['keys'].items()}, set(map(tuple, s['dups'])), s['files']
    return collections.defaultdict(set), set(), []


def save_state(keys, dups, files):
    with open(STATE, 'w') as fh:
        json.dump({'keys': {k: sorted(v) for k, v in keys.items()},
                   'dups': sorted(dups), 'files': files}, fh)


def scan(path, win, keys, dups, seen):
    n = hit = 0
    with open(path, newline='', encoding='utf-8-sig', errors='replace') as fh:
        rd = csv.reader(fh)
        ix = {c: i for i, c in enumerate(next(rd))}
        need = ('ApiCountyCode', 'ApiSequenceNumber', 'ReportYear', 'ReportMonth')
        if any(c not in ix for c in need):
            print('  %-28s SKIPPED (columns)' % os.path.basename(path))
            return
        cy, sq = ix['ApiCountyCode'], ix['ApiSequenceNumber']
        iy, im = ix['ReportYear'], ix['ReportMonth']
        i_f = ix.get('FormationCode')
        i_s = ix.get('ApiSidetrack')
        for r in rd:
            n += 1
            try:
                api = r[cy].strip().zfill(3) + r[sq].strip().zfill(5)
                ym = int(r[iy]) * 12 + int(r[im])
            except (ValueError, IndexError):
                continue
            f0 = win.get(api)
            if f0 is None or ym < f0 or ym >= f0 + 12:
                continue
            fm = r[i_f].strip() if i_f is not None and i_f < len(r) else ''
            st = r[i_s].strip() if i_s is not None and i_s < len(r) else ''
            k = (ym, fm, st)
            gk = (api,) + k
            if gk in seen:
                dups.add(gk)
            seen.add(gk)
            keys[api].add(k)
            hit += 1
    print('  %-28s %9d rows, %7d in a window' % (os.path.basename(path), n, hit))


def report(win, keys, dups, files):
    print('\nfiles scanned: %d' % len(files))
    print('analysis wells: %d' % len(win))
    rows_ne_months = short = never = 0
    dist = collections.Counter()
    for api in win:
        k = keys.get(api, set())
        rows = len(k)
        months = len({ym for ym, _, _ in k})
        if rows == 0:
            never += 1
            continue
        if rows != months:
            rows_ne_months += 1
        if rows == 12 and months < 12:
            short += 1
        dist[months] += 1
    print('\nwells with no rows found in their window: %d' % never)
    print('wells where the ROW count differs from the MONTH count: %d'
          % rows_ne_months)
    print('wells admitted by "rows == 12" whose window holds FEWER than 12 '
          'distinct months: %d' % short)
    print('\ndistinct months in the window, distribution:')
    for m in sorted(dist):
        print('   %2d months  %6d wells' % (m, dist[m]))
    print('\nduplicated (well, month, formation, sidetrack) keys inside a '
          'window: %d' % len(dups))
    if dups:
        a = collections.Counter(k[0] for k in dups)
        print('   affecting %d wells; worst well has %d duplicated rows'
              % (len(a), max(a.values())))


if __name__ == '__main__':
    win = load_windows()
    keys, dups, files = load_state()
    keys = collections.defaultdict(set, keys)
    if '--report' in sys.argv:
        report(win, keys, dups, files)
        sys.exit(0)
    seen = {(a,) + k for a, ks in keys.items() for k in ks}
    for p in sys.argv[1:]:
        if os.path.basename(p) in files:
            print('  %-28s already scanned' % os.path.basename(p))
            continue
        scan(p, win, keys, dups, seen)
        files.append(os.path.basename(p))
    save_state(keys, dups, files)
    print('state saved: %d wells with rows, %d files' % (len(keys), len(files)))
