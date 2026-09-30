"""Does New Mexico's and Ohio's zero-for-missing depth change the measurement?

THE PROBLEM
    Two agencies write a zero where a depth was never recorded. In the New
    Mexico analysis set (13,947 wells) `md` is zero for 39.6% of wells and
    `tvd` for 41.4%; in Ohio (1,158 wells) `DTD` is zero for 45 wells and null
    for 42 more. A zero is not a missing value: it is a well 0 ft deep, and the
    model reads it as one. `HistGradientBoostingRegressor` handles NaN natively
    — it learns a default direction for missing values at each split — so the
    zeros could simply have been recoded and were not.

WHY THE PAPER DOES NOT RECODE THEM
    Not because it does not matter but because the measurement is a
    *difference* between two partitions of the same table. Both sides see the
    same features; a feature that is degraded is degraded identically under the
    random split and under the pad split, so it cannot manufacture a gap
    between them. That is an argument, though, and an argument is worth less
    than a number. This script produces the number.

WHAT IT DOES
    Scores New Mexico and Ohio at the 150 m pad radius exactly as
    `radius_sweep.py` does — twenty-four seeds, five 80/20 splits each, random against
    pad-grouped — once with the zeros as published and once with them recoded
    to NaN, and prints both inflations.

    python3 zero_depth_check.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

import importlib.util
import numpy as np
import pandas as pd
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
FE = ['lat', 'lon', 'spud_year', 'depth', 'elev', 'n_stim']


def fit(X, y, sp, groups, seed):
    out = []
    it = sp.split(X, y) if groups is None else sp.split(X, y, groups=groups)
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
    return float(np.mean(out)) if out else np.nan


def score(X, y, groups):
    v = []
    for s in range(SEEDS):
        sp = (ShuffleSplit(SPLITS, test_size=TEST, random_state=s) if groups is None
              else GroupShuffleSplit(SPLITS, test_size=TEST, random_state=s))
        v.append(fit(X, y, sp, groups, s))
    return float(np.nanmean(v))


def load_new_mexico():
    d, feats = le.load_new_mexico()
    return d, feats, ['depth', 'elev']          # md and tvd


def load_ohio():
    o = pd.read_csv(P.oh('oh_analysis.csv'), dtype={'PadNumber': str, 'OPNO': str},
                    low_memory=False)
    o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
    o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
    o['spud_year'] = (pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed')
                      .dt.year.fillna(o.first_prod.dt.year))
    o['depth'] = pd.to_numeric(o.DTD, errors='coerce')
    o['elev'] = pd.to_numeric(o.ELEV_GR, errors='coerce')
    o['n_stim'] = np.nan
    o = (o.replace([np.inf, -np.inf], np.nan)
          .dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True))
    return o, FE, ['depth']                     # DTD only; ELEV_GR has no zeros


def main():
    rows = []
    for state, loader in (('New Mexico', load_new_mexico), ('Ohio', load_ohio)):
        d, feats, zerocols = loader()
        pad = le.infer_pads(d.lat.to_numpy(), d.lon.to_numpy(), radius_m=RADIUS)
        nz = int(sum((pd.to_numeric(d[c], errors='coerce') == 0).sum() for c in zerocols))
        print('%s: %d wells, %d pads at %d m, %d zero values in %s'
              % (state, len(d), len(set(pad)), RADIUS, nz, ', '.join(zerocols)))

        for label, frame in (('as published', d),
                             ('zeros recoded NaN',
                              d.assign(**{c: pd.to_numeric(d[c], errors='coerce')
                                          .replace(0, np.nan) for c in zerocols}))):
            X = frame[feats].to_numpy(dtype=float)
            y = frame['y'].to_numpy(dtype=float)
            r, p = score(X, y, None), score(X, y, pad)
            print('    %-18s random %.4f   pad %.4f   inflation %+.4f'
                  % (label, r, p, r - p))
            rows.append(dict(state=state, treatment=label, n=len(frame),
                             random=r, pad=p, inflation=r - p))

    out = pd.DataFrame(rows)
    out.to_csv(P.out('zero_depth_check.csv'), index=False)
    for s in out.state.unique():
        a, b = out[out.state == s].inflation.to_numpy()
        print('%s: recoding moves the inflation by %+.4f' % (s, b - a))
    print('wrote zero_depth_check.csv')


if __name__ == '__main__':
    main()
