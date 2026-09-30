"""Does the inferred grouping substitute for the register, measured through the model?

Pennsylvania and Ohio both publish a pad register alongside wellhead
coordinates and production, so in both the substitution can be tested where it
is actually used: on the reported score, not in clustering space.

THE TEST
    Fit the same model under the register grouping and under the 150 m inferred
    grouping, thirty seeds, five 80/20 group-shuffled splits each, and take the
    difference *per seed* so the comparison is paired — the two groupings see
    the same seed, and the seed-to-seed variation cancels. The interval is a
    two-sided 95% t interval on the thirty paired differences.

WHY IT IS DEPOSITED
    §10 claims every number in the paper comes from a released script. This
    number — contribution 5, and one of the few in the abstract — was for a
    time quoted from a working note instead, which is exactly the gap this
    script closes.

    python3 register_vs_inferred.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

import importlib.util
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit

spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le = importlib.util.module_from_spec(spec)
sys.modules['le'] = le
spec.loader.exec_module(le)

SEEDS, SPLITS, TEST, RADIUS = 30, 5, 0.20, 150
T95 = 2.045230                                        # two-sided 95%, 29 dof


def fit(X, y, groups, seed):
    sp = GroupShuffleSplit(SPLITS, test_size=TEST, random_state=seed)
    out = []
    for tr, te in sp.split(X, y, groups=groups):
        if len(te) < 20 or len(tr) < 50:
            continue
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                          random_state=seed, early_stopping=False)
        m.fit(X[tr], y[tr])
        p = m.predict(X[te])
        sst = float(((y[te] - y[te].mean()) ** 2).sum())
        if sst > 0:
            out.append(1 - float(((y[te] - p) ** 2).sum()) / sst)
    return float(np.mean(out)), int(np.mean([len(tr) for tr, _ in
                                             sp.split(X, y, groups=groups)]))


def load_ohio():
    o = pd.read_csv(P.oh('oh_analysis.csv'), dtype={'PadNumber': str}, low_memory=False)
    o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
    o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
    o['spud_year'] = (pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed')
                      .dt.year.fillna(o.first_prod.dt.year))
    o['depth'] = pd.to_numeric(o.DTD, errors='coerce')
    o['elev'] = pd.to_numeric(o.ELEV_GR, errors='coerce')
    o = (o.replace([np.inf, -np.inf], np.nan)
          .dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True))
    return o, ['lat', 'lon', 'spud_year', 'depth', 'elev'], o.PadNumber.astype(str).to_numpy()


def run(state, d, feats, reg):
    X = d[feats].to_numpy(dtype=float)
    y = d['y'].to_numpy(dtype=float)
    inf = le.infer_pads(d.lat.to_numpy(), d.lon.to_numpy(), radius_m=RADIUS)
    print('%s: %d wells, %d registered pads, %d inferred at %d m'
          % (state, len(d), len(set(reg)), len(set(inf)), RADIUS))

    rows = []
    for s in range(SEEDS):
        r, ntr_r = fit(X, y, reg, s)
        i, ntr_i = fit(X, y, inf, s)
        rows.append(dict(state=state, seed=s, register=r, inferred=i, diff=i - r,
                         train_register=ntr_r, train_inferred=ntr_i))
    out = pd.DataFrame(rows)
    dif = out['diff'].to_numpy()
    half = T95 * dif.std(ddof=1) / np.sqrt(SEEDS)
    print('  register  R2 %.4f +/- %.4f' % (out.register.mean(), out.register.std(ddof=1)))
    print('  inferred  R2 %.4f +/- %.4f' % (out.inferred.mean(), out.inferred.std(ddof=1)))
    print('  paired difference %+.4f, 95%% CI %+.4f to %+.4f'
          % (dif.mean(), dif.mean() - half, dif.mean() + half))
    print('  per-seed differences %+.4f to %+.4f' % (dif.min(), dif.max()))
    # round rather than truncate: %d on 1969.7 printed 1969, and that figure
    # reached Table S3 while the text rounded the same number to 1,970
    print('  mean training set: register %.0f, inferred %.0f'
          % (out.train_register.mean(), out.train_inferred.mean()), flush=True)
    return out


def main():
    d, feats = le.load_pennsylvania()
    frames = [run('Pennsylvania', d, feats, d.pad_true.astype(str).to_numpy())]
    o, ofeats, oreg = load_ohio()
    frames.append(run('Ohio', o, ofeats, oreg))
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(P.out('register_vs_inferred.csv'), index=False)
    print('wrote register_vs_inferred.csv')


if __name__ == '__main__':
    main()
