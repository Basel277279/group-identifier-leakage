"""Can a well pad be inferred from public wellhead data alone? Pennsylvania only.

SUPERSEDED, KEPT FOR THE RECORD. This is the first version of the recovery
test, written when Pennsylvania was the only register in hand.
`recovery_sweep.py` sweeps both registers across radii and constraints and is
the paper's; `pad_infer_ohio.py` is the Ohio counterpart of this file. Where
this script and `recovery_sweep.py` disagree, `recovery_sweep.py` is right.

Ground truth: Pennsylvania DEP publishes an operator-reported pad identifier
(well_pad_id) for 2,499 of the 2,505 wells. Most states do not. This scores a
pad inference built only from fields every state publishes -- wellhead
coordinates, operator, and spud date -- against that truth.

Scoring is pairwise: over all pairs of wells, does the inference agree with the
truth about whether the two share a pad? Precision, recall and F1 on the
"same pad" class, plus the Adjusted Rand Index and the share of true pads
recovered exactly.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import csv, math, collections, itertools

R_EARTH_M = 6371008.8

def load():
    path = os.path.join(P.PA_DIR, 'P2_wells_with_logs.csv')
    d = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    out = []
    for r in d:
        pid = (r.get('well_pad_id') or '').strip()
        try:
            lat = float(r['lat_index']); lon = float(r['lon_index'])
        except (TypeError, ValueError):
            continue
        if not pid:
            continue
        out.append({'api': r.get('API') or r.get('api10'), 'pad': pid, 'lat': lat, 'lon': lon,
                    'op': (r.get('operator_permit') or '').strip().upper(),
                    'spud': (r.get('spud_date') or '').strip()})
    return out

def spud_year(s):
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            import datetime
            return datetime.datetime.strptime(s, fmt).year
        except Exception:
            pass
    return None

def metres(a, b):
    la, lo = math.radians(a['lat']), math.radians(a['lon'])
    lb, lb2 = math.radians(b['lat']), math.radians(b['lon'])
    x = (lb2 - lo) * math.cos(0.5 * (la + lb))
    y = lb - la
    return R_EARTH_M * math.hypot(x, y)

def infer(wells, radius_m, use_operator=True, year_window=None):
    """Single-link clustering within radius, optionally constrained."""
    # bucket by coarse grid to keep it near-linear. Longitude cells are widened
    # by 1/cos(phi) at the most poleward latitude in the data, for the reason
    # given in `leakage_experiment.infer_pads`; this file carried a single cell
    # size in degrees when it was written.
    cell_lat = radius_m / 111320.0
    coslat = max(math.cos(math.radians(max(abs(w['lat']) for w in wells))), 1e-6)
    cell_lon = radius_m / (111320.0 * coslat)
    grid = collections.defaultdict(list)
    for i, w in enumerate(wells):
        grid[(int(w['lat'] / cell_lat), int(w['lon'] / cell_lon))].append(i)
    parent = list(range(len(wells)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(i, j):
        a, b = find(i), find(j)
        if a != b: parent[a] = b
    for (gy, gx), idxs in grid.items():
        near = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                near += grid.get((gy + dy, gx + dx), [])
        for i in idxs:
            for j in near:
                if j <= i: continue
                a, b = wells[i], wells[j]
                if use_operator and a['op'] != b['op']: continue
                if year_window is not None:
                    ya, yb = a.get('yr'), b.get('yr')
                    if ya and yb and abs(ya - yb) > year_window: continue
                if metres(a, b) <= radius_m: union(i, j)
    lab = {}
    for i in range(len(wells)):
        lab.setdefault(find(i), len(lab))
    return [lab[find(i)] for i in range(len(wells))]

def pair_scores(truth, pred):
    """Pairwise precision/recall/F1 and ARI, computed from the contingency table."""
    n = len(truth)
    cont = collections.Counter(zip(truth, pred))
    a = collections.Counter(truth); b = collections.Counter(pred)
    c2 = lambda k: k * (k - 1) // 2
    tp = sum(c2(v) for v in cont.values())
    same_t = sum(c2(v) for v in a.values())
    same_p = sum(c2(v) for v in b.values())
    total = c2(n)
    fp = same_p - tp; fn = same_t - tp
    prec = tp / same_p if same_p else 0.0
    rec = tp / same_t if same_t else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    exp = same_t * same_p / total
    mx = 0.5 * (same_t + same_p)
    ari = (tp - exp) / (mx - exp) if mx != exp else 0.0
    return prec, rec, f1, ari, tp, fp, fn

def exact_pads(truth, pred):
    t = collections.defaultdict(set); p = collections.defaultdict(set)
    for i, (a, b) in enumerate(zip(truth, pred)):
        t[a].add(i); p[b].add(i)
    pset = {frozenset(v) for v in p.values()}
    return sum(1 for v in t.values() if frozenset(v) in pset), len(t), len(p)

W = load()
for w in W: w['yr'] = spud_year(w['spud'])
truth = [w['pad'] for w in W]
print('wells with a reported pad and coordinates: %d on %d pads\n' % (len(W), len(set(truth))))

print('%-8s %-9s %-7s %8s %8s %8s %8s %9s %9s' %
      ('radius', 'operator', 'years', 'prec', 'recall', 'F1', 'ARI', 'pads', 'exact'))
best = None
for radius in (50, 100, 150, 200, 300, 400, 500, 750, 1000):
    for use_op, yw in ((True, None), (False, None), (True, 3)):
        pred = infer(W, radius, use_op, yw)
        prec, rec, f1, ari, tp, fp, fn = pair_scores(truth, pred)
        ex, nt, npd = exact_pads(truth, pred)
        print('%-8d %-9s %-7s %8.3f %8.3f %8.3f %8.3f %9d %8.1f%%' %
              (radius, 'yes' if use_op else 'no', yw or '-', prec, rec, f1, ari,
               npd, 100 * ex / nt))
        if best is None or f1 > best[0]: best = (f1, radius, use_op, yw, prec, rec, ari, ex, nt, npd)
print('\nbest by F1: radius %d m, operator %s, year window %s'
      % (best[1], 'yes' if best[2] else 'no', best[3] or 'none'))
print('  precision %.3f  recall %.3f  F1 %.3f  ARI %.3f' % (best[4], best[5], best[0], best[6]))
print('  %d inferred pads against %d true; %d true pads recovered exactly (%.1f%%)'
      % (best[9], best[8], best[7], 100 * best[7] / best[8]))
