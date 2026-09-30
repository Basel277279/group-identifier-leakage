"""How well is the pad recovered from coordinates alone? Scored against both
published registers, across radii and constraints.

Clustering only -- no model fitting -- so this is seconds, not minutes.

Pairwise precision/recall/F1 on the "same pad" class, the Adjusted Rand Index,
and the share of true pads recovered exactly. Three constraint settings:
distance only, distance + same operator, distance + a 3-year spud window --
the two extra fields a practitioner would naturally reach for.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import math, collections, importlib.util, sys, numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le = importlib.util.module_from_spec(spec); sys.modules['le'] = le; spec.loader.exec_module(le)
OH = P.oh() + os.sep
RADII = [25, 50, 75, 100, 150, 200, 300, 500, 750, 1000]


def infer(wells, radius_m, use_operator=False, year_window=None):
    import math
    # longitude cells must be widened by 1/cos(lat): a single cell size in
    # degrees makes them too narrow in metres and the +-1 search misses pairs.
    # The reference is the MOST POLEWARD latitude, not the mean, for the reason
    # given in `leakage_experiment.infer_pads`: against a mean, every cell north
    # of it is narrower than the radius and the +-1 search can miss a pair that
    # is inside it. This file carried the mean until the two were reconciled;
    # on both registers the partitions were identical at all ten radii either
    # way, so no published number changes.
    cell_lat = radius_m / 111320.0
    coslat = max(math.cos(math.radians(max(abs(w['lat']) for w in wells))), 1e-6)
    cell_lon = radius_m / (111320.0 * coslat)
    grid = collections.defaultdict(list)
    for i, w in enumerate(wells):
        grid[(int(w['lat']/cell_lat), int(w['lon']/cell_lon))].append(i)
    parent = list(range(len(wells)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for (gy, gx), idxs in grid.items():
        near = []
        for dy in (-1,0,1):
            for dx in (-1,0,1): near += grid.get((gy+dy, gx+dx), [])
        for i in idxs:
            a = wells[i]; la, lo = math.radians(a['lat']), math.radians(a['lon'])
            for j in near:
                if j <= i: continue
                b = wells[j]
                if use_operator and a['op'] != b['op']: continue
                if year_window is not None and a['yr'] and b['yr'] \
                        and abs(a['yr']-b['yr']) > year_window: continue
                lb, lb2 = math.radians(b['lat']), math.radians(b['lon'])
                x = (lb2-lo)*math.cos(0.5*(la+lb)); y = lb-la
                if 6371008.8*math.hypot(x, y) <= radius_m:
                    ra, rb = find(i), find(j)
                    if ra != rb: parent[ra] = rb
    lab = {}
    return [lab.setdefault(find(i), len(lab)) for i in range(len(wells))]


def scores(truth, pred):
    c2 = lambda k: k*(k-1)//2
    cont = collections.Counter(zip(truth, pred))
    a = collections.Counter(truth); b = collections.Counter(pred)
    tp = sum(c2(v) for v in cont.values())
    st = sum(c2(v) for v in a.values()); sp = sum(c2(v) for v in b.values())
    tot = c2(len(truth))
    prec = tp/sp if sp else 0.0; rec = tp/st if st else 0.0
    f1 = 2*prec*rec/(prec+rec) if prec+rec else 0.0
    exp = st*sp/tot; mx = 0.5*(st+sp)
    ari = (tp-exp)/(mx-exp) if mx != exp else 0.0
    t = collections.defaultdict(set); p = collections.defaultdict(set)
    for i, (x, y) in enumerate(zip(truth, pred)): t[x].add(i); p[y].add(i)
    pset = {frozenset(v) for v in p.values()}
    exact = sum(1 for v in t.values() if frozenset(v) in pset)/len(t)
    return prec, rec, f1, ari, exact, len(set(pred)), len(t)


def run(name, wells, truth):
    print('\n%s -- %d wells, %d published pads' % (name, len(wells), len(set(truth))))
    print('%-8s %-12s %8s %8s %8s %8s %8s' %
          ('radius', 'constraint', 'prec', 'recall', 'F1', 'ARI', 'exact'))
    rows = []
    for r in RADII:
        for use_op, yw, tag in ((False, None, 'distance'),
                                (True, None, '+ operator'),
                                (False, 3, '+ 3-yr spud')):
            pred = infer(wells, r, use_op, yw)
            prec, rec, f1, ari, ex, npd, nt = scores(truth, pred)
            print('%-8d %-12s %8.3f %8.3f %8.3f %8.3f %7.1f%%'
                  % (r, tag, prec, rec, f1, ari, 100*ex))
            rows.append({'state': name, 'radius_m': r, 'constraint': tag,
                         'precision': prec, 'recall': rec, 'f1': f1, 'ari': ari,
                         'exact': ex, 'pads_inferred': npd, 'pads_true': nt})
    return rows


rows = []


def pa_register():
    """The FULL published register: every well DEP gives a `well_pad_id`, not
    just the ones with a usable first-year production history.

    This test needs no production, so restricting it to the modelling set would
    throw away 35 wells for no reason and, worse, would make Pennsylvania's row
    mean something different from Ohio's, which has always used its full
    register. Both are now the register as published: 2,499 wells on 1,044 pads
    here, 4,618 on 1,070 in Ohio. The modelling subset gives 2,464 wells on
    1,014 pads and, at 150 m, F1 0.9954 against 0.9954 -- the choice changes no
    conclusion, only what the number is a statement about.
    """
    import pandas as pd
    d = pd.read_csv(os.path.join(P.PA_DIR, 'P2_wells_with_logs.csv'),
                    low_memory=False)
    d = d[d.well_pad_id.notna()].copy()
    d['lat'] = pd.to_numeric(d.lat_index, errors='coerce')
    d['lon'] = pd.to_numeric(d.lon_index, errors='coerce')
    d['yr'] = pd.to_datetime(d.spud_date, errors='coerce').dt.year
    d = d.dropna(subset=['lat', 'lon'])
    W = [{'lat': float(r.lat), 'lon': float(r.lon),
          'op': str(r.operator_permit).strip().upper(),
          'yr': int(r.yr) if r.yr == r.yr else None} for r in d.itertuples()]
    return W, d.well_pad_id.astype(str).tolist()


W, truth = pa_register()
rows += run('Pennsylvania', W, truth)

# the FULL published register, all vintages -- not just wells still producing.
# 15.3% of these pads contain more than one operator; among pads spudded
# entirely from 2020 only 2.3% do (`operator_vintage.py`), which is why the
# operator constraint looks harmless on recent wells.
def ohio_register():
    """The full published register: 4,618 wells on 1,070 pads, every vintage,
    not just the wells still producing.

    Prefers the small derived table `oh_register.csv`, which holds exactly the
    five columns this test needs. It is built here from the three RBDMS
    exports the first time, then reused -- those exports are 245 MB and
    `oh_register.csv` is 200 kB, which is the difference between a project
    that can be handed to someone and one that cannot.

    Rebuild it from scratch by deleting oh_register.csv, having run
    `oh_build.py --from-access` (or mdb-export) to produce loc/well/padwells.
    """
    small = P.oh('oh_register.csv')
    if os.path.exists(small):
        return pd.read_csv(small, dtype={'PadNumber': str, 'OPNO': str})

    pw = pd.read_csv(OH + 'padwells.csv', dtype=str)
    pw['api14'] = pw.ApiWellNo.str.strip().str.zfill(14)
    pw = pw.drop_duplicates('api14')
    wl = pd.read_csv(OH + 'well.csv', dtype=str, low_memory=False,
                     usecols=['API_WELLNO', 'OPNO', 'DT_SPUD'])
    wl['api14'] = wl.API_WELLNO.str.strip().str.zfill(14)
    wl = wl.drop_duplicates('api14')
    lc = pd.read_csv(OH + 'loc.csv', dtype=str, low_memory=False,
                     usecols=['LOCATION_ID', 'WH_LAT83', 'WH_LONG83',
                              'WH_LAT', 'WH_LONG'])
    lc['api14'] = lc.LOCATION_ID.str.strip().str.zfill(14)
    for c in ('WH_LAT83', 'WH_LONG83', 'WH_LAT', 'WH_LONG'):
        lc[c] = pd.to_numeric(lc[c], errors='coerce')
    lc['lat'] = lc.WH_LAT83.where(lc.WH_LAT83.between(38, 42.5), lc.WH_LAT)
    lc['lon'] = lc.WH_LONG83.where(lc.WH_LONG83.between(-85, -80), lc.WH_LONG)
    o = (pw.merge(lc[['api14', 'lat', 'lon']], on='api14')
           .merge(wl[['api14', 'OPNO', 'DT_SPUD']], on='api14', how='left'))
    o = o[o.lat.between(38, 42.5) & o.lon.between(-85, -80)]
    o['yr'] = pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed').dt.year
    o = o[['api14', 'PadNumber', 'lat', 'lon', 'OPNO', 'yr']]
    o.to_csv(small, index=False)
    print('wrote %s (%d wells, %d pads)'
          % (small, len(o), o.PadNumber.nunique()))
    return o


o = ohio_register()
W = [{'lat': r.lat, 'lon': r.lon, 'op': str(r.OPNO),
      'yr': int(r.yr) if r.yr == r.yr else None} for r in o.itertuples()]
rows += run('Ohio', W, o.PadNumber.astype(str).tolist())

pd.DataFrame(rows).to_csv(P.out('recovery_sweep.csv'), index=False)
print('\nwrote recovery_sweep.csv')
