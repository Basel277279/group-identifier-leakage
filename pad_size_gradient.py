"""Does the inflation really come from the pad? Seeded, with a placebo control.

The first pass reported inflation rising with wells per pad, and offered
single-well pads as a control. That control is worthless: on a single-well pad
every well is its own group, so pad-grouped CV *is* random CV and the zero is
true by construction. It checks the code, not the claim.

The control that works is a PLACEBO GROUPING -- groups with exactly the same
size distribution as the real pads, but with membership permuted at random, so
they are statistically identical to pads in every way except that they are not
pads. If grouped cross-validation is inherently pessimistic, placebo groups will
depress the score too. If the drop is caused by pad membership specifically,
placebo will sit on top of the random split and only the real pads will fall.

    random     ShuffleSplit,      20% held out
    pad        GroupShuffleSplit, 20% held out, real pads
    placebo    GroupShuffleSplit, 20% held out, size-matched random groups

Every cell is SEEDS x SPLITS fits. The `*_sd` columns are the population
standard deviation over all SEEDS x SPLITS fold scores, not a between-seed
spread and not a standard error: do NOT divide them by sqrt(SEEDS). The paper's
intervals on this quantity come from `fig_data.csv`, which keeps one row per
seed, and are wider. This script exists because the 8+ bin in the first pass
rested on a single seed; it is a redundant route to Table 2 and agrees with
`fig_data.csv` on every cell mean.

    python pad_size_gradient.py

Needs pandas, numpy, scikit-learn. Reads the same inputs as
leakage_experiment.py and reuses its loaders.
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'le', os.path.join(HERE, 'leakage_experiment.py'))
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
SEEDS = 24
SPLITS = 5
TEST_FRAC = 0.20
BINS = [(1, 1, '1 well'), (2, 3, '2-3 wells'), (4, 5, '4-5 wells'),
        (6, 7, '6-7 wells'), (8, 999, '8+ wells')]


def placebo_groups(sizes, rng):
    """Random groups with exactly the pads' size distribution.

    np.repeat expands the size vector back to one label per well, so the
    result has sum(sizes) entries -- one per well, not one per pad.
    """
    labels = np.repeat(np.arange(len(sizes)), sizes)
    rng.shuffle(labels)
    return labels


def one_scheme(X, y, splitter, groups, seed):
    out = []
    it = (splitter.split(X, y) if groups is None
          else splitter.split(X, y, groups=groups))
    for tr, te in it:
        if len(te) < 20 or len(tr) < 50:
            continue
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                          random_state=seed, early_stopping=False)
        m.fit(X[tr], y[tr])
        p = m.predict(X[te])
        ss_res = float(((y[te] - p) ** 2).sum())
        ss_tot = float(((y[te] - y[te].mean()) ** 2).sum())
        if ss_tot > 0:
            out.append(1 - ss_res / ss_tot)
    return out


def cell(df, feats, padcol):
    X = df[feats].to_numpy(dtype=float)
    y = df['y'].to_numpy(dtype=float)
    pad = pd.factorize(df[padcol].astype(str))[0]
    sizes = np.bincount(pad)
    sizes = sizes[sizes > 0]

    res = {'random': [], 'pad': [], 'placebo': []}
    for s in range(SEEDS):
        rng = np.random.default_rng(1000 + s)
        res['random'] += one_scheme(
            X, y, ShuffleSplit(SPLITS, test_size=TEST_FRAC, random_state=s),
            None, s)
        res['pad'] += one_scheme(
            X, y, GroupShuffleSplit(SPLITS, test_size=TEST_FRAC, random_state=s),
            pad, s)
        res['placebo'] += one_scheme(
            X, y, GroupShuffleSplit(SPLITS, test_size=TEST_FRAC, random_state=s),
            placebo_groups(sizes, rng), s)
    return {k: (float(np.mean(v)), float(np.std(v))) for k, v in res.items()
            if v}


def run(state, loader, use_true_pads):
    d, feats = loader()
    if use_true_pads and d.pad_true.notna().any():
        padcol, kind = 'pad_true', 'published register'
    else:
        d['pad_inf'] = le.infer_pads(d.lat.to_numpy(), d.lon.to_numpy())
        padcol, kind = 'pad_inf', 'inferred at 150 m'
    d['pad_size'] = d.groupby(d[padcol].astype(str))[padcol].transform('size').values

    print('\n' + '=' * 92)
    print('%s -- %d wells, pads %s, %d seeds x %d splits, %.0f%% held out'
          % (state.upper(), len(d), kind, SEEDS, SPLITS, 100 * TEST_FRAC))
    print('=' * 92)
    print('%-12s %7s   %-15s %-15s %-15s %12s %12s'
          % ('pad size', 'wells', 'random', 'placebo', 'pad',
             'pad-random', 'placebo-rand'))
    rows = []
    for lo, hi, lab in BINS:
        sub = d[(d.pad_size >= lo) & (d.pad_size <= hi)]
        if len(sub) < 400:
            print('%-12s %7d   (too few)' % (lab, len(sub)))
            continue
        c = cell(sub, feats, padcol)
        r, p, g = c['random'], c['placebo'], c['pad']
        print('%-12s %7d   %6.3f +-%.3f   %6.3f +-%.3f   %6.3f +-%.3f   %+11.3f %+12.3f'
              % (lab, len(sub), r[0], r[1], p[0], p[1], g[0], g[1],
                 g[0] - r[0], p[0] - r[0]))
        rows.append({'state': state, 'pad_bin': lab, 'wells': len(sub),
                     'random': r[0], 'random_sd': r[1],
                     'placebo': p[0], 'placebo_sd': p[1],
                     'pad': g[0], 'pad_sd': g[1],
                     'inflation': r[0] - g[0],
                     'placebo_effect': r[0] - p[0]})
    return rows


def main():
    rows = []
    rows += run('pennsylvania', le.load_pennsylvania, True)
    rows += run('new_mexico', le.load_new_mexico, False)
    out = pd.DataFrame(rows)
    out.to_csv(P.out('pad_size_gradient.csv'), index=False)

    print('\n' + '=' * 92)
    print('INFLATION (random minus pad) vs PLACEBO EFFECT (random minus placebo)')
    print('=' * 92)
    print(out.pivot_table(index='pad_bin', columns='state',
                          values=['inflation', 'placebo_effect'])
          .reindex([b[2] for b in BINS]).round(3).to_string())
    print('\nIf the placebo column is near zero while inflation grows, the drop '
          'is\ncaused by pad membership and not by grouped validation itself.')
    print('\nwrote pad_size_gradient.csv')


if __name__ == '__main__':
    main()
