"""One covariate at a time: what it encodes, and whether that is the pad.

WHAT §6 CLAIMS AND WHERE THE NUMBERS COME FROM
    §6.2 scores ground elevation alone; §6.3 scores spud year alone and
    contrasts the two; §6.3 reports a pad-ICC for elevation and shows it does
    not predict the leak. Those three sets of numbers were for a time spread
    across `fig5_compute.py` and a working note. This script produces all of
    them in one place, for both covariates and all four states, so §6 rests on
    a released file.

FOR EACH state x covariate IT REPORTS
    random      R2 under a random 80/20 split, that covariate as the only feature
    pad         R2 under the pad grouping (register in PA and OH, 150 m
                inferred in NM and CO)
    inflation   random - pad
    pad_const   share of MULTI-WELL pads whose wells all share one value
    uniq_share  share of wells whose value occurs on exactly one pad
    pad_icc     share of the covariate's variance lying between pads

    Group labels are factorized to integers and values rounded to three
    decimals before the descriptive counts, both matching `fig5_compute.py`:
    `GroupShuffleSplit` shuffles the unique group labels, so integer and string
    labels give different folds from the same seed, and Table 5 would not
    reproduce if this script differed on that detail.

    The wellhead COORDINATE PAIR is profiled too, for its descriptive columns
    only. §6.4 claims coordinates can always identify the pad; that claim needs
    a measured uniqueness share, and it had none. A pair is not scored as a
    single feature — the model already has both columns — so its R2 cells are
    left empty.

    A high single-feature random R2 with a near-zero or negative pad R2 means
    the covariate is a pad label: it identifies the group without carrying
    transferable information about the outcome.

WHICH ELEVATION
    Pennsylvania  elevation_ft   Ohio  ELEV_GR
    New Mexico    elev_gl_num from `wellhistory` — the loader's `elev` is TVD,
                  which is not a surface attribute
    Colorado      ground_elev

    python3 covariate_audit.py      -> covariate_audit.csv
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
SEEDS, SPLITS, TEST = 24, 5, 0.20
NMS = P.nmcsv() + os.sep


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
    return float(np.mean(out)) if out else np.nan


def score(X, y, g):
    v = [fit(X, y, (ShuffleSplit(SPLITS, test_size=TEST, random_state=s) if g is None
                    else GroupShuffleSplit(SPLITS, test_size=TEST, random_state=s)), g, s)
         for s in range(SEEDS)]
    return float(np.nanmean(v)), float(np.nanstd(v))


def descriptives(v, pad):
    """pad_const, uniq_share and pad_icc for one covariate.

    Values are rounded to three decimals before the constancy and uniqueness
    counts, matching `fig5_compute.py`, so Table 5's descriptive columns
    reproduce here rather than nearly reproducing.

    `pad_icc` is the one-way ICC(1) for unequal group sizes,

        (MSB - MSW) / (MSB + (k0 - 1) * MSW),

    computed over MULTI-WELL PADS ONLY. Both details matter, and neither is
    cosmetic. The raw between-group variance share SSB/SST is not an ICC and
    runs far higher — 0.46 against 0.08 for Pennsylvania. And including
    singleton pads inflates whichever measure is used, because a pad holding
    one well contributes no within-pad variance at all; Pennsylvania's ICC(1)
    is 0.08 over every pad and 0.25 over the multi-well ones. Table S4 reports
    the multi-well ICC(1) and so does this, so the two agree.
    """
    f = pd.DataFrame({'v': np.round(np.asarray(v, dtype=float), 3),
                      'p': np.asarray(pad)})
    f = f.dropna()
    size = f.groupby('p').v.size()
    multi = size[size > 1].index
    const = float((f[f.p.isin(multi)].groupby('p').v.nunique() == 1).mean()) if len(multi) else np.nan
    pads_per_value = f.groupby('v').p.nunique()
    uniq = float(f.v.map(pads_per_value).eq(1).mean())

    m = f[f.p.isin(multi)]
    icc = np.nan
    if len(m) and m.p.nunique() > 1:
        grand = m.v.mean()
        gm = m.groupby('p').v.agg(['mean', 'size'])
        n, k = len(m), len(gm)
        ssb = float((gm['size'] * (gm['mean'] - grand) ** 2).sum())
        sst = float(((m.v - grand) ** 2).sum())
        if k > 1 and n > k:
            msb, msw = ssb / (k - 1), (sst - ssb) / (n - k)
            k0 = (n - (gm['size'] ** 2).sum() / n) / (k - 1)
            denom = msb + (k0 - 1) * msw
            icc = (msb - msw) / denom if denom != 0 else np.nan
    return const, uniq, float(icc)


def coordinate_row(state, d, pad):
    """Descriptives for the (lat, lon) pair: is a coordinate unique to one pad?"""
    v = list(zip(np.round(pd.to_numeric(d.lat, errors='coerce'), 6),
                 np.round(pd.to_numeric(d.lon, errors='coerce'), 6)))
    f = pd.DataFrame({'v': v, 'p': np.asarray(pad)}).dropna()
    size = f.groupby('p').v.size()
    multi = size[size > 1].index
    const = float((f[f.p.isin(multi)].groupby('p').v.nunique() == 1).mean()) if len(multi) else np.nan
    pads_per_value = f.groupby('v').p.nunique()
    uniq = float(f.v.map(pads_per_value).eq(1).mean())
    print('  %-12s %-10s %-34s uniq %.4f' % (state, 'coordinates', '', uniq), flush=True)
    return dict(state=state, covariate='coordinates', n=len(f),
                random=np.nan, random_sd=np.nan, pad=np.nan, pad_sd=np.nan,
                inflation=np.nan, pad_const=const, uniq_share=uniq, pad_icc=np.nan)


def block(state, d, pad, cov):
    """cov: {name: series}. d must carry 'y'."""
    y = d['y'].to_numpy(dtype=float)
    out = []
    for name, series in cov.items():
        v = pd.to_numeric(series, errors='coerce')
        keep = v.notna().to_numpy()
        X = v.to_numpy(dtype=float)[keep].reshape(-1, 1)
        yy, gg = y[keep], np.asarray(pad)[keep]
        r, r_sd = score(X, yy, None)
        p, p_sd = score(X, yy, gg)
        const, uniq, icc = descriptives(v, pad)
        out.append(dict(state=state, covariate=name, n=int(keep.sum()),
                        random=r, random_sd=r_sd, pad=p, pad_sd=p_sd,
                        inflation=r - p, pad_const=const, uniq_share=uniq,
                        pad_icc=icc))
        print('  %-12s %-10s random %+.4f  pad %+.4f  infl %+.4f  const %.3f '
              'uniq %.3f  icc %.3f'
              % (state, name, r, p, r - p, const, uniq, icc), flush=True)
    return out


def main():
    rows = []

    print('Pennsylvania (register)')
    pa, _ = le.load_pennsylvania()
    pa_pad = pd.factorize(pa.pad_true.astype(str))[0]
    rows += block('Pennsylvania', pa, pa_pad,
                  {'elevation': pa.elev, 'spud_year': pa.spud_year})
    rows.append(coordinate_row('Pennsylvania', pa, pa_pad))

    print('Ohio (register)')
    o = pd.read_csv(P.oh('oh_analysis.csv'), dtype={'PadNumber': str}, low_memory=False)
    o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
    o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
    o['spud_year'] = (pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed')
                      .dt.year.fillna(o.first_prod.dt.year))
    o['elev'] = pd.to_numeric(o.ELEV_GR, errors='coerce')
    o = (o.replace([np.inf, -np.inf], np.nan)
          .dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True))
    o_pad = pd.factorize(o.PadNumber.astype(str))[0]
    rows += block('Ohio', o, o_pad, {'elevation': o.elev, 'spud_year': o.spud_year})
    rows.append(coordinate_row('Ohio', o, o_pad))

    print('New Mexico (150 m inferred; ground elevation from wellhistory)')
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
    n = n.dropna(subset=['gelev']).reset_index(drop=True)
    n_pad = le.infer_pads(n.lat.to_numpy(), n.lon.to_numpy())
    rows += block('New Mexico', n, n_pad,
                  {'elevation': n.gelev, 'spud_year': n.spud_year})
    rows.append(coordinate_row('New Mexico', n, n_pad))

    print('Colorado (150 m inferred)')
    c = pd.read_csv(P.co('co_analysis.csv'), low_memory=False)
    c['y'] = np.log10(pd.to_numeric(c.first365_G, errors='coerce').where(lambda s: s > 0))
    c['spud_year'] = pd.to_datetime(c.spud_dte, errors='coerce').dt.year
    c['gelev'] = pd.to_numeric(c.ground_elev, errors='coerce')
    c = (c.replace([np.inf, -np.inf], np.nan)
          .dropna(subset=['lat', 'lon', 'y', 'spud_year', 'gelev']).reset_index(drop=True))
    c_pad = le.infer_pads(c.lat.to_numpy(), c.lon.to_numpy())
    rows += block('Colorado', c, c_pad,
                  {'elevation': c.gelev, 'spud_year': c.spud_year})
    rows.append(coordinate_row('Colorado', c, c_pad))

    out = pd.DataFrame(rows)
    out.to_csv(P.out('covariate_audit.csv'), index=False)
    print()
    print(out.round(4).to_string(index=False))

    e = out[out.covariate == 'elevation']
    rho = e.pad_icc.rank().corr(e.inflation.rank())
    rho2 = e.uniq_share.rank().corr(e.inflation.rank())
    print()
    print('elevation: rank corr(pad_icc, inflation) = %+.2f' % rho)
    print('elevation: rank corr(uniq_share, inflation) = %+.2f' % rho2)
    print('wrote covariate_audit.csv')


if __name__ == '__main__':
    main()
