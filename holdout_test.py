"""Does the saturation come from the held-out fraction? A pre-registered test.

MECHANISM UNDER TEST
    Under a random split with held-out fraction t, each of a test well's k-1
    pad-mates is in the training set with probability (1-t), so the chance that
    at least one is present is

        P_leak(k, t) = 1 - t^(k-1)

    If the saturation of inflation with pad size is caused by this and nothing
    else, then two things must hold:
      (a) the knee moves LEFT as t falls  (t=0.1 saturates by k=3;
          t=0.4 not until k=7), and
      (b) inflation plotted against P_leak instead of k must COLLAPSE the three
          held-out fractions onto a single curve.

    (b) is the real test. (a) alone could be produced by several mechanisms.

    Stated before running, so it is a prediction and not a description.

New Mexico, 15,911 horizontal wells -- the largest set with the widest range of
pad occupancy. Six seeds x five splits per cell, random vs pad-grouped only
(the placebo is already established as flat).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
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
SEEDS, SPLITS = 24, 5
FRACTIONS = (0.10, 0.20, 0.40)
BINS = [(1,1,'1'),(2,2,'2'),(3,3,'3'),(4,5,'4-5'),(6,7,'6-7'),(8,11,'8-11'),(12,999,'12+')]

def fit(X, y, sp, groups, seed):
    out = []
    it = sp.split(X, y) if groups is None else sp.split(X, y, groups=groups)
    for tr, te in it:
        if len(te) < 20 or len(tr) < 50: continue
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, random_state=seed,
                                       early_stopping=False)
        m.fit(X[tr], y[tr]); p = m.predict(X[te])
        sst = float(((y[te]-y[te].mean())**2).sum())
        if sst > 0: out.append(1 - float(((y[te]-p)**2).sum())/sst)
    return float(np.mean(out)) if out else np.nan

d, feats = le.load_new_mexico()
d['pad'] = le.infer_pads(d.lat.to_numpy(), d.lon.to_numpy())
d['pad_size'] = d.groupby('pad')['pad'].transform('size').values
print('New Mexico: %d wells, %d pads\n' % (len(d), d.pad.nunique()))
print('%-8s %-8s %7s %7s %8s %8s %10s %9s' %
      ('t', 'pad size', 'wells', 'meanK', 'random', 'pad', 'inflation', 'P_leak'))
rows = []
for t in FRACTIONS:
    for lo, hi, lab in BINS:
        s = d[(d.pad_size >= lo) & (d.pad_size <= hi)]
        if len(s) < 400: continue
        X = s[feats].to_numpy(float); y = s['y'].to_numpy(float)
        pad = pd.factorize(s['pad'].astype(str))[0]
        per = []
        for seed in range(SEEDS):
            r = fit(X, y, ShuffleSplit(SPLITS, test_size=t, random_state=seed), None, seed)
            g = fit(X, y, GroupShuffleSplit(SPLITS, test_size=t, random_state=seed), pad, seed)
            per.append(r - g)
        k = s.pad_size.to_numpy(float)
        p_leak = float(np.mean(1 - t**(k-1)))
        infl = float(np.mean(per)); sd = float(np.std(per, ddof=1))
        print('%-8.2f %-8s %7d %7.1f %8s %8s %+10.3f %9.4f'
              % (t, lab, len(s), k.mean(), '', '', infl, p_leak), flush=True)
        rows.append({'t': t, 'bin': lab, 'wells': len(s), 'mean_k': k.mean(),
                     'p_leak': p_leak, 'inflation': infl, 'inflation_sd': sd})
pd.DataFrame(rows).to_csv(P.out('holdout_test.csv'), index=False)
print('\nwrote holdout_test.csv')
