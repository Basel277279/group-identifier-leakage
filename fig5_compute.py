"""Paper 3, Figure 5 data: the leak travels through covariates that identify
the pad, and dropping the coordinates does not stop it.

TWO QUESTIONS, FOUR STATES, ONE SCRIPT

  A  Does removing lat/lon remove the leak?
        full features      lat, lon, spud_year, depth, <tvd|n_stim>, elevation
        no coordinates     the same minus lat, lon
     Inflation = random-split R2 minus pad-grouped R2, under each feature set.
     Pad grouping is the published register in Pennsylvania and Ohio and the
     150 m inferred clustering in New Mexico and Colorado.

  B  Can one ordinary covariate carry the leak on its own?
        elevation alone    ground elevation, nothing else
     Reported as the random-split R2 and the pad-grouped R2 side by side, so
     the reader sees the sign change rather than a difference.
     Two descriptive statistics go with it:
        pad_const    share of multi-well pads whose wells share one elevation
        uniq_share   share of wells whose elevation value occurs on one pad only

WHICH ELEVATION
    Pennsylvania  elevation_ft      (permit)
    Ohio          ELEV_GR           (RBDMS, ground elevation)
    New Mexico    elev_gl_num       (wellhistory; the loader's `elev` is TVD,
                                     which is NOT a surface attribute)
    Colorado      ground_elev       (COGCC)

    python3 fig5_compute.py      -> fig5_data.csv
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit

spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le = importlib.util.module_from_spec(spec)
sys.modules['le'] = le
spec.loader.exec_module(le)

OH = P.oh() + os.sep
NMS = P.nmcsv() + os.sep
CO = P.co('co_analysis.csv')

# 24 seeds, not six. At six the pooled inflations were not reproducible
# to the three decimals the manuscript printed: re-running the same data
# under a different labelling of the SAME pad partition moved Colorado's
# grouped score by 0.011, and Pennsylvania's and New Mexico's
# coordinate-removal effects did not resolve at all. The data is public,
# so a replicator who lands 0.02 away must be able to see that as
# agreement rather than contradiction; that needs seeds and intervals.
SEEDS, SPLITS, TEST = 24, 5, 0.20


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


T95 = 2.068658        # t(0.975, 23): SEEDS = 24


def per_seed(X, y, g):
    """One R2 per seed, each already a mean over SPLITS folds.

    Returned as the ARRAY, not as a mean and an sd, because the quantity the
    paper reports is a DIFFERENCE between two arms scored on the same seed.
    Collapsing each arm first throws away the pairing and leaves no honest way
    to put an interval on the difference -- which is how the manuscript came to
    print three decimals it had not earned.
    """
    return np.array([fit(X, y,
                         (ShuffleSplit(SPLITS, test_size=TEST, random_state=s)
                          if g is None else
                          GroupShuffleSplit(SPLITS, test_size=TEST, random_state=s)),
                         g, s) for s in range(SEEDS)])


def sc(X, y, g):
    """Mean and between-seed sd of R2 over SEEDS x SPLITS fits."""
    v = per_seed(X, y, g)
    return float(v.mean()), float(v.std(ddof=1))


def ci_of(v):
    """Half-width of a 95% interval on the mean of `v`."""
    return float(T95 * v.std(ddof=1) / np.sqrt(len(v)))


def constancy(vals, pad):
    """(share of multi-well pads with one elevation value,
        share of wells whose value occurs on exactly one pad)."""
    df = pd.DataFrame({'v': np.round(np.asarray(vals, float), 3), 'p': pad})
    g = df.groupby('p').v
    multi = g.size() > 1
    const = float((g.nunique()[multi] == 1).mean()) if multi.any() else float('nan')
    pads_per_val = df.groupby('v').p.nunique()
    uniq = float(df.v.map(pads_per_val).eq(1).mean())
    return const, uniq


def block(name, d, pad, full, elevcol):
    y = d['y'].to_numpy(float)
    nocoord = [f for f in full if f not in ('lat', 'lon')]
    row = {'state': name, 'n_wells': len(d), 'n_pads': int(pd.Series(pad).nunique())}

    seeds = {}
    for lab, F in (('full', full), ('nocoord', nocoord), ('elev', [elevcol])):
        X = d[F].to_numpy(float)
        rv = per_seed(X, y, None)
        pv = per_seed(X, y, pad)
        iv = rv - pv                      # paired by seed, which is the point
        seeds[lab] = iv
        row['%s_random' % lab] = float(rv.mean())
        row['%s_random_sd' % lab] = float(rv.std(ddof=1))
        row['%s_pad' % lab] = float(pv.mean())
        row['%s_pad_sd' % lab] = float(pv.std(ddof=1))
        row['%s_infl' % lab] = float(iv.mean())
        row['%s_infl_ci' % lab] = ci_of(iv)
        print('  %-9s random %+.3f (%.3f)  pad %+.3f (%.3f)  inflation %+.3f +- %.3f'
              % (lab, rv.mean(), rv.std(ddof=1), pv.mean(), pv.std(ddof=1),
                 iv.mean(), ci_of(iv)), flush=True)

    # Does removing the coordinates change the inflation? Paired on the seed,
    # which is the only way to ask: the two arms share the model's randomness.
    dif = seeds['nocoord'] - seeds['full']
    row['nocoord_change'] = float(dif.mean())
    row['nocoord_change_ci'] = ci_of(dif)
    lo, hi = dif.mean() - ci_of(dif), dif.mean() + ci_of(dif)
    row['nocoord_verdict'] = ('worse' if lo > 0 else
                              'better' if hi < 0 else 'indistinguishable')
    print('  removing the coordinates: %+.4f (95%% CI %+.4f to %+.4f) -> %s'
          % (dif.mean(), lo, hi, row['nocoord_verdict']), flush=True)
    for lab, v in seeds.items():
        SEED_ROWS.extend({'state': name, 'arm': lab, 'seed': i,
                          'inflation': float(x)} for i, x in enumerate(v))

    row['pad_const'], row['uniq_share'] = constancy(d[elevcol], pad)
    print('  elevation constant within %.1f%% of multi-well pads; '
          '%.1f%% of wells hold a value unique to one pad'
          % (100 * row['pad_const'], 100 * row['uniq_share']), flush=True)
    return row


rows = []
SEED_ROWS = []          # one row per state x arm x seed, written beside the summary

# ---------------------------------------------------------------- Pennsylvania
print('\nPennsylvania (published pad register)', flush=True)
d, feats = le.load_pennsylvania()
d = d.dropna(subset=['elev']).reset_index(drop=True)
rows.append(block('Pennsylvania', d, pd.factorize(d.pad_true.astype(str))[0],
                  feats, 'elev'))

# ------------------------------------------------------------------------ Ohio
print('\nOhio (published pad register)', flush=True)
o = pd.read_csv(OH + 'oh_analysis.csv', dtype={'PadNumber': str}, low_memory=False)
o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
o['spud_year'] = pd.to_datetime(o.DT_SPUD, errors='coerce',
                                format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth'] = pd.to_numeric(o.DTD, errors='coerce')
o['elev'] = pd.to_numeric(o.ELEV_GR, errors='coerce')
o = o.replace([np.inf, -np.inf], np.nan)
o = o.dropna(subset=['lat', 'lon', 'y', 'spud_year', 'elev']).reset_index(drop=True)
rows.append(block('Ohio', o, pd.factorize(o.PadNumber.astype(str))[0],
                  ['lat', 'lon', 'spud_year', 'depth', 'elev'], 'elev'))

# ------------------------------------------------------------------ New Mexico
print('\nNew Mexico (150 m inferred pads; ground elevation from wellhistory)',
      flush=True)
n, _ = le.load_new_mexico()
wh = pd.read_csv(NMS + 'wellhistory.csv', dtype=str, low_memory=False,
                 usecols=['api_st_cde', 'api_cnty_cde', 'api_well_idn',
                          'rec_termn_dte', 'elev_gl_num'])
wh = wh[wh.rec_termn_dte.str.startswith('9999', na=False)]
wh['api10'] = (wh.api_st_cde.str.zfill(2) + wh.api_cnty_cde.str.zfill(3)
               + wh.api_well_idn.str.zfill(5))
wh['gelev'] = pd.to_numeric(wh.elev_gl_num, errors='coerce')
n['api10'] = n.api10.astype(str)
n = n.merge(wh[['api10', 'gelev']].drop_duplicates('api10'), on='api10', how='left')
n['tvd'] = pd.to_numeric(n.elev, errors='coerce')     # loader's `elev` IS tvd
n = n.dropna(subset=['gelev']).reset_index(drop=True)
rows.append(block('New Mexico', n, le.infer_pads(n.lat.to_numpy(), n.lon.to_numpy()),
                  ['lat', 'lon', 'spud_year', 'depth', 'tvd', 'gelev'], 'gelev'))

# -------------------------------------------------------------------- Colorado
print('\nColorado (150 m inferred pads)', flush=True)
c = pd.read_csv(CO, low_memory=False)
c['y'] = np.log10(pd.to_numeric(c.first365_G, errors='coerce').where(lambda s: s > 0))
c['spud_year'] = pd.to_datetime(c.spud_dte, errors='coerce').dt.year
c['depth'] = pd.to_numeric(c.max_md, errors='coerce')
c['tvd'] = pd.to_numeric(c.max_tvd, errors='coerce')
c['gelev'] = pd.to_numeric(c.ground_elev, errors='coerce')
c = c.replace([np.inf, -np.inf], np.nan)
c = c.dropna(subset=['lat', 'lon', 'y', 'spud_year', 'gelev']).reset_index(drop=True)
rows.append(block('Colorado', c, le.infer_pads(c.lat.to_numpy(), c.lon.to_numpy()),
                  ['lat', 'lon', 'spud_year', 'depth', 'tvd', 'gelev'], 'gelev'))

out = pd.DataFrame(rows)
out.to_csv(P.out('fig5_data.csv'), index=False)
pd.DataFrame(SEED_ROWS).to_csv(P.out('fig5_seeds.csv'), index=False)
print('\nwrote fig5_data.csv')
print(out[['state', 'n_wells', 'full_infl', 'nocoord_infl',
           'elev_random', 'elev_pad', 'elev_infl',
           'pad_const', 'uniq_share']].round(3).to_string(index=False))
