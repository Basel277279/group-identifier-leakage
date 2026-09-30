"""Paper 3, the core experiment: what does the validation split change?

One model, one target, one feature set. Only the train/test partition varies.
Everything else is held fixed, so every difference in the reported score is
attributable to the split and to nothing else.

THE SPLITS
    random            5-fold, shuffled -- what most published models use
    pad (true)        GroupKFold on the regulator's own pad id   [PA only]
    pad (inferred)    GroupKFold on 150 m single-link clusters
    operator          GroupKFold on operator
    spud year         GroupKFold on year of spud
    spatial 10 km     GroupKFold on a 10 km grid cell
    spatial 25 km     GroupKFold on a 25 km grid cell

WHY PENNSYLVANIA MATTERS TWICE
    It is the only state here with a published pad id AND enough wells, so it
    is the only place the inferred grouping can be scored against the true one
    *through the model* rather than through clustering metrics. If "pad (true)"
    and "pad (inferred)" agree, the benchmark transfers to states with no pad
    register -- which is the whole design.

    python leakage_experiment.py
    python leakage_experiment.py pennsylvania

Needs pandas, numpy, scikit-learn.
"""
import collections
import math
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold, KFold

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P            # noqa: E402  -- resolves Data/ under the project

PA = P.PA_DIR
NM = P.NM_DIR

N_SPLITS = 5
SEED = 0
PAD_RADIUS_M = 150.0
R_EARTH_M = 6371008.8


# --------------------------------------------------------------- pad inference
def infer_pads(lat, lon, radius_m=PAD_RADIUS_M):
    """Single-link clustering within radius.

    The grid must use a different cell size in longitude: a degree of longitude
    is only cos(lat) of a degree of latitude in metres, so a single cell size
    in degrees makes the longitude cells too narrow and a +-1 cell search can
    miss pairs that are within the radius. Verified identical to brute force
    at every radius from 10 m to 10 km after this correction.
    """
    n = len(lat)
    if n == 0:                       # np.mean([]) is nan; bail before it bites
        return np.empty(0, dtype=np.int64)
    cell_lat = radius_m / 111320.0
    # cos of the MOST POLEWARD latitude in the data, not the mean. A cell is
    # radius_m * cos(phi)/cos(phi_ref) metres wide at latitude phi, so a mean
    # reference makes cells narrower than the radius wherever phi exceeds it,
    # and a +-1 cell search can then miss a pair that is inside the radius.
    # Using the maximum makes every cell at least radius_m wide everywhere,
    # which is what the +-1 search assumes. On these four states it changes no
    # partition at any radius -- New Mexico and Colorado were re-clustered at
    # 100, 150 and 300 m under both rules and came out identical -- so the
    # guarantee becomes unconditional rather than accidental.
    coslat = max(math.cos(math.radians(float(np.max(np.abs(lat))))), 1e-6)
    cell_lon = radius_m / (111320.0 * coslat)
    grid = collections.defaultdict(list)
    for i in range(n):
        grid[(int(lat[i] / cell_lat), int(lon[i] / cell_lon))].append(i)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for (gy, gx), idxs in grid.items():
        near = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                near += grid.get((gy + dy, gx + dx), [])
        for i in idxs:
            la, lo = math.radians(lat[i]), math.radians(lon[i])
            for j in near:
                if j <= i:
                    continue
                lb, lb2 = math.radians(lat[j]), math.radians(lon[j])
                x = (lb2 - lo) * math.cos(0.5 * (la + lb))
                y = lb - la
                if R_EARTH_M * math.hypot(x, y) <= radius_m:
                    a, b = find(i), find(j)
                    if a != b:
                        parent[a] = b
    lab, out = {}, np.empty(n, dtype=np.int64)
    for i in range(n):
        r = find(i)
        if r not in lab:
            lab[r] = len(lab)
        out[i] = lab[r]
    return out


def grid_block(lat, lon, km):
    """A coarse square grid, the usual 'spatial blocking' comparator."""
    dlat = km / 111.32
    dlon = km / (111.32 * np.cos(np.radians(np.mean(lat))))
    return (np.floor(lat / dlat).astype(np.int64) * 100000
            + np.floor(lon / dlon).astype(np.int64))


# ------------------------------------------------------------------- loaders
def load_pennsylvania():
    d = pd.read_csv(os.path.join(PA, 'P2_wells_with_logs.csv'), low_memory=False)
    d = d[d.well_pad_id.notna()].copy()
    d['lat'] = pd.to_numeric(d.lat_index, errors='coerce')
    d['lon'] = pd.to_numeric(d.lon_index, errors='coerce')
    d['y_raw'] = pd.to_numeric(d.gas_first365_mcf, errors='coerce')
    d['spud_year'] = pd.to_datetime(d.spud_date, errors='coerce').dt.year
    d['operator'] = d.operator_permit.astype(str)
    d['pad_true'] = d.well_pad_id.astype(str)
    d['depth'] = pd.to_numeric(d.total_depth_ft, errors='coerce')
    d['elev'] = pd.to_numeric(d.elevation_ft, errors='coerce')
    d['n_stim'] = pd.to_numeric(d.n_stimulations, errors='coerce')
    feats = ['lat', 'lon', 'spud_year', 'depth', 'elev', 'n_stim']
    return tidy(d, feats), feats


NM_WINDOW_MONTHS = 12


def load_new_mexico():
    d = pd.read_csv(os.path.join(NM, 'csv', 'nm_well_summary.csv'),
                    low_memory=False, dtype={'api10': str, 'operator': str})
    d = d[d.directional_status == 'H'].copy()
    # A COMPLETE first year, the same rule Ohio and Colorado apply.
    #
    # This used to be absent, and it mattered more than it looks. The window is
    # the twelve calendar months from a well's first gas month, but the record
    # ends in 2026-08, so for a well first producing after 2025-09 the window
    # has not elapsed and `first365_G` is a partial sum. 1,964 of the 15,911
    # wells the old rule kept -- 12.3% -- had fewer than twelve months of
    # filings inside their window, 1,546 of them simply too recent. Pad-mates
    # come online together, so that truncation is pad-constant: it reads to the
    # model exactly like a leaking covariate, and under a random split pad-mates
    # in training give it away. Requiring the full window moved New Mexico's
    # inflation at 150 m from +0.073 to +0.041 and its 8+ occupancy cell from
    # +0.415 to +0.353, so the missing rule was carrying close to half of what
    # the state appeared to show. `nm_rule_effect.py` measures both arms.
    #
    # `n_months_in_window` is written by `nm_build.py`. It is REQUIRED rather
    # than optional: an older summary table without the column would otherwise
    # be read silently under the old, wrong rule.
    if 'n_months_in_window' not in d.columns:
        raise SystemExit(
            'nm_well_summary.csv has no n_months_in_window column. Re-run '
            'nm_build.py: without it there is no first-year completeness rule '
            'for New Mexico and 12% of wells carry a partial-year target.')
    d = d[pd.to_numeric(d.n_months_in_window, errors='coerce')
          == NM_WINDOW_MONTHS].copy()
    d['lat'] = pd.to_numeric(d.lat, errors='coerce')
    d['lon'] = pd.to_numeric(d.lon, errors='coerce')
    d['spud_year'] = pd.to_datetime(d.spud_dte, errors='coerce').dt.year
    d = d[(d.spud_year >= 2010) & (d.spud_year <= 2026)]
    d['y_raw'] = pd.to_numeric(d.first365_G, errors='coerce')
    d['depth'] = pd.to_numeric(d.md, errors='coerce')
    d['elev'] = pd.to_numeric(d.tvd, errors='coerce')
    d['n_stim'] = pd.to_numeric(d.n_pools, errors='coerce')
    d['pad_true'] = np.nan                      # no published pad register
    feats = ['lat', 'lon', 'spud_year', 'depth', 'elev', 'n_stim']
    return tidy(d, feats), feats


def tidy(d, feats):
    d = d[d.y_raw > 0].copy()
    d['y'] = np.log10(d.y_raw)
    d = d.dropna(subset=['lat', 'lon', 'y', 'spud_year'])
    d = d[d.lat.between(24, 50) & d.lon.between(-125, -65)]
    for f in feats:
        d[f] = pd.to_numeric(d[f], errors='coerce')
    return d.reset_index(drop=True)


LOADERS = {'pennsylvania': load_pennsylvania, 'new_mexico': load_new_mexico}


# ---------------------------------------------------------------- the engine
def score(d, feats, splitter, groups, name):
    X = d[feats].to_numpy(dtype=float)
    y = d['y'].to_numpy(dtype=float)
    r2s, maes, ntest = [], [], []
    it = (splitter.split(X, y) if groups is None
          else splitter.split(X, y, groups=groups))
    for tr, te in it:
        if len(te) < 20 or len(tr) < 50:
            continue
        # early_stopping is pinned OFF rather than left at sklearn's 'auto',
        # which switches internal early stopping on above 10,000 TRAINING rows.
        # Left at the default, New Mexico's ~12,700-row training folds early-stop
        # and the other three states' do not, so the learner would differ by
        # state -- a silent ~0.003 on New Mexico's inflation, and inconsistent
        # with this paper's claim that one learner is used throughout.
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                          random_state=SEED,
                                          early_stopping=False)
        m.fit(X[tr], y[tr])
        p = m.predict(X[te])
        ss_res = float(((y[te] - p) ** 2).sum())
        ss_tot = float(((y[te] - y[te].mean()) ** 2).sum())
        r2s.append(1 - ss_res / ss_tot if ss_tot > 0 else np.nan)
        maes.append(float(np.abs(y[te] - p).mean()))
        ntest.append(len(te))
    if not r2s:
        return None
    ng = len(set(groups)) if groups is not None else len(d)
    return {'scheme': name, 'groups': ng, 'folds': len(r2s),
            'r2': float(np.mean(r2s)), 'r2_sd': float(np.std(r2s)),
            'mae': float(np.mean(maes)), 'median_test': int(np.median(ntest))}


def run(state):
    print('=' * 78)
    print(state.upper())
    t0 = time.time()
    d, feats = LOADERS[state]()
    print('%d wells, target = log10 first-365-day gas, features = %s'
          % (len(d), feats))

    pad_inf = infer_pads(d.lat.to_numpy(), d.lon.to_numpy())
    d['pad_inferred'] = pad_inf
    print('inferred pads at %d m: %d' % (PAD_RADIUS_M, len(set(pad_inf))))

    schemes = [('random', KFold(N_SPLITS, shuffle=True, random_state=SEED), None)]
    if d.pad_true.notna().any():
        schemes.append(('pad (true)', GroupKFold(N_SPLITS),
                        d.pad_true.astype(str).to_numpy()))
    schemes += [
        ('pad (inferred %dm)' % PAD_RADIUS_M, GroupKFold(N_SPLITS), pad_inf),
        ('operator', GroupKFold(N_SPLITS), d.operator.astype(str).to_numpy()),
        ('spud year', GroupKFold(N_SPLITS), d.spud_year.astype(int).to_numpy()),
        ('spatial 10 km', GroupKFold(N_SPLITS),
         grid_block(d.lat.to_numpy(), d.lon.to_numpy(), 10)),
        ('spatial 25 km', GroupKFold(N_SPLITS),
         grid_block(d.lat.to_numpy(), d.lon.to_numpy(), 25)),
    ]

    rows = []
    for name, sp, g in schemes:
        r = score(d, feats, sp, g, name)
        if r:
            rows.append(r)
            print('  %-22s R2 %.3f (sd %.3f)  MAE %.3f  groups %6d'
                  % (name, r['r2'], r['r2_sd'], r['mae'], r['groups']))

    res = pd.DataFrame(rows)
    ref = res.loc[res.scheme.str.startswith('pad (true)'), 'r2']
    if ref.empty:
        ref = res.loc[res.scheme.str.startswith('pad (inferred'), 'r2']
    ref = float(ref.iloc[0])
    res['inflation_vs_pad'] = res.r2 - ref
    res.insert(0, 'state', state)
    print('  (%.0f s)' % (time.time() - t0))
    return res


def main():
    """A 5-fold GroupKFold survey. SUPERSEDED — not what the paper reports.

    This was the first pass, before the schedule settled on six seeds of five
    80/20 group-shuffled splits. Its numbers differ from the paper's, by 0.005
    on the headline random-versus-pad inflation and by as much as 0.18 on the
    few-group proxies, where 5-fold GroupKFold and repeated shuffle splits draw
    very different folds. `radius_sweep.py` and `proxy_compare.py` produce the
    values the paper reports; this survives as a smoke test for the loaders and
    the scoring path, and writes to a name that cannot be mistaken for a result.
    """
    states = [a for a in sys.argv[1:] if a in LOADERS] or list(LOADERS)
    out = pd.concat([run(s) for s in states], ignore_index=True)
    path = P.out('leakage_smoke_test.csv')
    out.to_csv(path, index=False)

    print('\n' + '=' * 78)
    print('R2 by split, and how far each sits above the pad-grouped reference')
    print('=' * 78)
    piv = out.pivot_table(index='scheme', columns='state', values='r2')
    order = ['random', 'spatial 10 km', 'spatial 25 km', 'operator',
             'spud year', 'pad (inferred %dm)' % PAD_RADIUS_M, 'pad (true)']
    piv = piv.reindex([s for s in order if s in piv.index])
    print(piv.round(3).to_string())
    print('\ninflation vs the pad reference:')
    piv2 = out.pivot_table(index='scheme', columns='state',
                           values='inflation_vs_pad')
    print(piv2.reindex([s for s in order if s in piv2.index]).round(3).to_string())
    print('\nwrote %s' % path)


if __name__ == '__main__':
    main()
