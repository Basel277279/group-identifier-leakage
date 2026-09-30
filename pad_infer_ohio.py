"""Pad inference scored against Ohio's *published* pad membership.

Pennsylvania's DEP publishes an operator-reported well_pad_id; pad_infer.py
scores a coordinate-only inference against it. Ohio turns out to publish the
same thing, independently, inside the RBDMS Access database: tblPadWells links
4,619 wells to 1,071 approved pads. This is the replication.

Inputs -- all from Rbdmsd97Weekly.zip, exported with mdbtools:

    mdb-export Rbdmsd972.mdb tblLocational > loc.csv
    mdb-export Rbdmsd97.mdb  Well         > well.csv
    mdb-export Rbdmsd97.mdb  tblPadWells  > padwells.csv

Result: radius 100 m, no operator constraint, no year window --
precision 0.987, recall 0.991, F1 0.989, ARI 0.989, 96.8% of pads exact.
Pennsylvania, same code: 150 m, F1 0.995, 99.2% exact.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import collections
import datetime
import math
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = P.OH_DIR

R_EARTH_M = 6371008.8


def metres(a, b):
    la, lo = math.radians(a['lat']), math.radians(a['lon'])
    lb, lb2 = math.radians(b['lat']), math.radians(b['lon'])
    x = (lb2 - lo) * math.cos(0.5 * (la + lb))
    y = lb - la
    return R_EARTH_M * math.hypot(x, y)


def infer(wells, radius_m, use_operator=True, year_window=None):
    """Single-link clustering within radius, optionally constrained."""
    cell_lat = radius_m / 111320.0
    # cos of the most poleward latitude, not the mean -- see the note in
    # `leakage_experiment.infer_pads`. Ohio spans 38.4 to 42.0 degrees, so
    # the two agree there; this keeps the two implementations identical.
    coslat = max(math.cos(math.radians(max(abs(w['lat']) for w in wells))), 1e-6)
    cell_lon = radius_m / (111320.0 * coslat)
    grid = collections.defaultdict(list)
    for i, w in enumerate(wells):
        grid[(int(w['lat'] / cell_lat), int(w['lon'] / cell_lon))].append(i)
    parent = list(range(len(wells)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b

    for (gy, gx), idxs in grid.items():
        near = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                near += grid.get((gy + dy, gx + dx), [])
        for i in idxs:
            for j in near:
                if j <= i:
                    continue
                a, b = wells[i], wells[j]
                if use_operator and a['op'] != b['op']:
                    continue
                if year_window is not None:
                    ya, yb = a.get('yr'), b.get('yr')
                    if ya and yb and abs(ya - yb) > year_window:
                        continue
                if metres(a, b) <= radius_m:
                    union(i, j)
    lab = {}
    for i in range(len(wells)):
        lab.setdefault(find(i), len(lab))
    return [lab[find(i)] for i in range(len(wells))]


def pair_scores(truth, pred):
    n = len(truth)
    cont = collections.Counter(zip(truth, pred))
    a = collections.Counter(truth)
    b = collections.Counter(pred)
    c2 = lambda k: k * (k - 1) // 2
    tp = sum(c2(v) for v in cont.values())
    same_t = sum(c2(v) for v in a.values())
    same_p = sum(c2(v) for v in b.values())
    total = c2(n)
    prec = tp / same_p if same_p else 0.0
    rec = tp / same_t if same_t else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    exp = same_t * same_p / total
    mx = 0.5 * (same_t + same_p)
    ari = (tp - exp) / (mx - exp) if mx != exp else 0.0
    return prec, rec, f1, ari


def exact_pads(truth, pred):
    t = collections.defaultdict(set)
    p = collections.defaultdict(set)
    for i, (a, b) in enumerate(zip(truth, pred)):
        t[a].add(i)
        p[b].add(i)
    pset = {frozenset(v) for v in p.values()}
    return sum(1 for v in t.values() if frozenset(v) in pset), len(t), len(p)


def spud_year(s):
    if not isinstance(s, str):
        return None
    s = s.strip()
    for fmt in ('%m/%d/%y %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(s, fmt).year
        except ValueError:
            pass
    return None


def load():
    loc = pd.read_csv(os.path.join(DATA, 'loc.csv'), dtype=str, low_memory=False,
                      usecols=['LOCATION_ID', 'WH_LAT83', 'WH_LONG83', 'WH_LAT', 'WH_LONG'])
    loc['api14'] = loc.LOCATION_ID.str.strip().str.zfill(14)
    for c in ('WH_LAT83', 'WH_LONG83', 'WH_LAT', 'WH_LONG'):
        loc[c] = pd.to_numeric(loc[c], errors='coerce')
    # prefer NAD83; fall back to the NAD27 pair where 83 is absent
    loc['lat'] = loc.WH_LAT83.where(loc.WH_LAT83.between(38, 42.5), loc.WH_LAT)
    loc['lon'] = loc.WH_LONG83.where(loc.WH_LONG83.between(-85, -80), loc.WH_LONG)

    well = pd.read_csv(os.path.join(DATA, 'well.csv'), dtype=str, low_memory=False,
                       usecols=['API_WELLNO', 'OPNO', 'DT_SPUD'])
    well['api14'] = well.API_WELLNO.str.strip().str.zfill(14)
    well = well.drop_duplicates('api14')

    pw = pd.read_csv(os.path.join(DATA, 'padwells.csv'), dtype=str)
    pw['api14'] = pw.ApiWellNo.str.strip().str.zfill(14)
    pw = pw.drop_duplicates('api14')

    df = (pw.merge(loc[['api14', 'lat', 'lon']], on='api14', how='left')
            .merge(well[['api14', 'OPNO', 'DT_SPUD']], on='api14', how='left'))
    dropped = len(df)
    df = df[df.lat.between(38, 42.5) & df.lon.between(-85, -80)]
    print('pad-linked wells %d, usable coordinates %d' % (dropped, len(df)))
    return [{'api': r.api14, 'pad': r.PadNumber, 'lat': r.lat, 'lon': r.lon,
             'op': (r.OPNO or '').strip(), 'yr': spud_year(r.DT_SPUD)}
            for r in df.itertuples()]


def main():
    W = load()
    truth = [w['pad'] for w in W]
    print('scored: %d wells on %d reported pads\n' % (len(W), len(set(truth))))
    print('%-8s %-9s %-7s %8s %8s %8s %8s %9s %9s'
          % ('radius', 'operator', 'years', 'prec', 'recall', 'F1', 'ARI', 'pads', 'exact'))
    best = None
    for radius in (50, 100, 150, 200, 300, 400, 500, 750, 1000):
        for use_op, yw in ((True, None), (False, None), (True, 3)):
            pred = infer(W, radius, use_op, yw)
            prec, rec, f1, ari = pair_scores(truth, pred)
            ex, nt, npd = exact_pads(truth, pred)
            print('%-8d %-9s %-7s %8.3f %8.3f %8.3f %8.3f %9d %8.1f%%'
                  % (radius, 'yes' if use_op else 'no', yw or '-', prec, rec, f1, ari,
                     npd, 100 * ex / nt))
            if best is None or f1 > best[0]:
                best = (f1, radius, use_op, yw, prec, rec, ari, ex, nt, npd)
    print('\nbest by F1: radius %d m, operator %s, year window %s'
          % (best[1], 'yes' if best[2] else 'no', best[3] or 'none'))
    print('  precision %.3f  recall %.3f  F1 %.3f  ARI %.3f' % (best[4], best[5], best[0], best[6]))
    print('  %d inferred pads against %d reported; %d exact (%.1f%%)'
          % (best[9], best[8], best[7], 100 * best[7] / best[8]))


if __name__ == '__main__':
    main()
