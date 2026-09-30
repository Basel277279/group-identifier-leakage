"""Is the pad a step, or the bottom of a continuum of spatial locality?

The held-out-fraction test refuted the pad-mate account of the leak. The
remaining candidate is locality: a pad is spatially compact, so removing it
removes a neighbourhood, and the more neighbourhood you remove the lower the
score. That would explain why 10-25 km blocks score BELOW the pad reference,
which the pad-mate account cannot.

THE TEST
    Group by single-link distance clustering at radii from 10 m to 10 km and
    score each. Wells on one pad sit 5-30 m apart at surface, so:

    - if locality is a continuum, the score should fall smoothly with radius
      and the published-pad score should lie ON that curve;
    - if pad-mates are genuinely special, there should be a STEP as the radius
      crosses pad spacing, with the published-pad score sitting off the trend.

    At every radius a size-matched placebo is run as well: groups with the same
    size distribution as the real clusters but random membership. Without it a
    decline could simply reflect larger groups.

Pennsylvania and Ohio carry published pad registers; New Mexico is included for
its size and range.

    python radius_sweep.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd, time
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le = importlib.util.module_from_spec(spec); sys.modules['le'] = le; spec.loader.exec_module(le)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit

# 24 seeds, not six. At six the pooled inflations were not reproducible
# to the three decimals the manuscript printed: re-running the same data
# under a different labelling of the SAME pad partition moved Colorado's
# grouped score by 0.011, and Pennsylvania's and New Mexico's
# coordinate-removal effects did not resolve at all. The data is public,
# so a replicator who lands 0.02 away must be able to see that as
# agreement rather than contradiction; that needs seeds and intervals.
SEEDS, SPLITS, TEST = 24, 5, 0.20
RADII = [10, 25, 50, 100, 150, 300, 1000, 3000, 10000]
OH = P.oh() + os.sep


def fit(X, y, sp, groups, seed):
    out = []
    it = sp.split(X, y) if groups is None else sp.split(X, y, groups=groups)
    for tr, te in it:
        if len(te) < 20 or len(tr) < 50: continue
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                          random_state=seed, early_stopping=False)
        m.fit(X[tr], y[tr]); p = m.predict(X[te])
        sst = float(((y[te] - y[te].mean())**2).sum())
        if sst > 0: out.append(1 - float(((y[te]-p)**2).sum())/sst)
    return float(np.mean(out)) if out else np.nan


def score(X, y, groups):
    """Mean over seeds; groups=None for a plain random split."""
    v = []
    for s in range(SEEDS):
        sp = (ShuffleSplit(SPLITS, test_size=TEST, random_state=s) if groups is None
              else GroupShuffleSplit(SPLITS, test_size=TEST, random_state=s))
        v.append(fit(X, y, sp, groups, s))
    return float(np.mean(v)), float(np.std(v, ddof=1))


def placebo_like(groups, seed):
    sizes = np.bincount(pd.factorize(groups)[0])
    sizes = sizes[sizes > 0]
    lab = np.repeat(np.arange(len(sizes)), sizes)
    np.random.default_rng(seed).shuffle(lab)
    return lab


def run(name, d, feats, padcol):
    X = d[feats].to_numpy(float); y = d['y'].to_numpy(float)
    lat, lon = d.lat.to_numpy(), d.lon.to_numpy()
    print('\n' + '=' * 96)
    print('%s -- %d wells' % (name.upper(), len(d)))
    print('=' * 96)
    r0, sd0 = score(X, y, None)
    print('%-12s %8s %9s   %-16s %-16s %10s' %
          ('grouping', 'groups', 'mean size', 'score', 'placebo', 'inflation'))
    print('%-12s %8d %9.2f   %6.3f +-%.3f    %-16s %10s'
          % ('random', len(d), 1.0, r0, sd0, '', ''), flush=True)
    rows = [{'state': name, 'grouping': 'random', 'radius_m': 0,
             'groups': len(d), 'mean_size': 1.0, 'score': r0, 'score_sd': sd0,
             'placebo': r0, 'inflation': 0.0}]

    if padcol is not None:
        g = pd.factorize(d[padcol].astype(str))[0]
        s, sd = score(X, y, g)
        ps, _ = score(X, y, placebo_like(g, 7))
        n = len(set(g))
        print('%-12s %8d %9.2f   %6.3f +-%.3f    %6.3f           %+10.3f'
              % ('pad register', n, len(d)/n, s, sd, ps, r0 - s), flush=True)
        rows.append({'state': name, 'grouping': 'pad register', 'radius_m': -1,
                     'groups': n, 'mean_size': len(d)/n, 'score': s,
                     'score_sd': sd, 'placebo': ps, 'inflation': r0 - s})

    for r in RADII:
        g = le.infer_pads(lat, lon, radius_m=float(r))
        n = len(set(g))
        s, sd = score(X, y, g)
        ps, _ = score(X, y, placebo_like(g, 7))
        print('%-12s %8d %9.2f   %6.3f +-%.3f    %6.3f           %+10.3f'
              % ('%d m' % r, n, len(d)/n, s, sd, ps, r0 - s), flush=True)
        rows.append({'state': name, 'grouping': '%d m' % r, 'radius_m': r,
                     'groups': n, 'mean_size': len(d)/n, 'score': s,
                     'score_sd': sd, 'placebo': ps, 'inflation': r0 - s})
    return rows
# --- END OF REUSABLE HELPERS --- radius_fine.py / co_fig.py split here


# Ohio drops n_stim: it was n_q_total, the number of quarters reported,
# which is partly downstream of the target. Five features for Ohio.
FE = ['lat', 'lon', 'spud_year', 'depth', 'elev']
allrows = []

d, feats = le.load_pennsylvania()
allrows += run('Pennsylvania', d, feats, 'pad_true')

o = pd.read_csv(OH + 'oh_analysis.csv', dtype={'PadNumber': str, 'OPNO': str},
                low_memory=False)
o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
o['spud_year'] = pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth'] = pd.to_numeric(o.DTD, errors='coerce'); o['elev'] = pd.to_numeric(o.ELEV_GR, errors='coerce')
o['pad_true'] = o.PadNumber.astype(str)
o = o.replace([np.inf, -np.inf], np.nan).dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True)
allrows += run('Ohio', o, FE, 'pad_true')

n, featsn = le.load_new_mexico()
allrows += run('New Mexico', n, featsn, None)

pd.DataFrame(allrows).to_csv(P.out('radius_sweep.csv'), index=False)
print('\nwrote radius_sweep.csv')
