"""The New Mexico counterpart of `oh_feat_audit.py`.

WHY THIS EXISTS
    The Ohio audit found `n_q_total` — the number of quarters a well has
    reported — sitting in the feature set. It is downstream of the outcome, it
    correlated +0.26 with the target, and it was removed. That audit was run on
    Ohio because Ohio is where the suspicious column was noticed. Running it on
    one state and not the others is not an audit; it is a coincidence.

    New Mexico's sixth feature is `n_pools`, the number of distinct pools the
    well reports production into. Like `n_q_total` it is counted from the
    production filings, so it is post-outcome in the same sense and is subject
    to the same test.

WHAT IT MEASURES
    The distribution of `n_pools`, its correlation with the target, and the
    inflation at the 150 m pad radius with the column and without it — six
    seeds, five 80/20 splits each, as everywhere else in this paper.

    python3 nm_feat_audit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

import importlib.util
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit

spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le = importlib.util.module_from_spec(spec)
sys.modules['le'] = le
spec.loader.exec_module(le)

# 24 seeds, not six. At six the pooled inflations were not reproducible
# to the three decimals the manuscript printed: re-running the same data
# under a different labelling of the SAME pad partition moved Colorado's
# grouped score by 0.011, and Pennsylvania's and New Mexico's
# coordinate-removal effects did not resolve at all. The data is public,
# so a replicator who lands 0.02 away must be able to see that as
# agreement rather than contradiction; that needs seeds and intervals.
SEEDS, SPLITS, TEST, RADIUS = 24, 5, 0.20, 150


def fit(X, y, sp, g, seed):
    out = []
    it = sp.split(X, y) if g is None else sp.split(X, y, groups=g)
    for tr, te in it:
        if len(te) < 20 or len(tr) < 50:
            continue
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                          random_state=seed, early_stopping=False)
        m.fit(X[tr], y[tr])
        p = m.predict(X[te])
        sst = float(((y[te] - y[te].mean()) ** 2).sum())
        if sst > 0:
            out.append(1 - float(((y[te] - p) ** 2).sum()) / sst)
    return float(np.mean(out))


def sc(X, y, g):
    return np.array([fit(X, y,
                         (ShuffleSplit(SPLITS, test_size=TEST, random_state=s) if g is None
                          else GroupShuffleSplit(SPLITS, test_size=TEST, random_state=s)),
                         g, s) for s in range(SEEDS)])


def main():
    d, _ = le.load_new_mexico()
    # the loader maps n_pools -> n_stim and tvd -> elev; see leakage_experiment.py
    print('New Mexico: %d wells' % len(d))
    print('n_pools distribution:')
    for v, c in d.n_stim.value_counts().sort_index().items():
        print('    %g  %6d  (%.1f%%)' % (v, c, 100 * c / len(d)))
    print('corr(n_pools, log10 first-365-day gas) = %+.4f'
          % np.corrcoef(d.n_stim, d.y)[0, 1])

    pad = le.infer_pads(d.lat.to_numpy(), d.lon.to_numpy(), radius_m=RADIUS)
    y = d.y.to_numpy(float)
    for lab, F in (('with n_pools', ['lat', 'lon', 'spud_year', 'depth', 'elev', 'n_stim']),
                   ('WITHOUT it', ['lat', 'lon', 'spud_year', 'depth', 'elev'])):
        X = d[F].to_numpy(float)
        r, g = sc(X, y, None), sc(X, y, pad)
        print('%-14s random %.4f  pad %.4f  inflation %+.4f'
              % (lab, r.mean(), g.mean(), (r - g).mean()), flush=True)


if __name__ == '__main__':
    main()
