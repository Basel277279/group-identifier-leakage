"""How much did New Mexico's missing first-year completeness rule inflate the
measurement?  Section S2.3 of the supplement.

THE DEFECT
    New Mexico's target is the first 365 days of gas.  The OCD record ends in
    August 2026, so a well first producing after September 2025 has a window
    that has not elapsed and `first365_G` is a partial sum.  The original build
    imposed no completeness rule -- unlike Ohio, which requires four complete
    quarters, and Colorado, which requires twelve monthly filings -- so 1,964 of
    15,911 wells (12.3%) carried a partial-year target.

WHY IT MATTERS HERE AND NOT ONLY IN GENERAL
    The truncation is PAD-CONSTANT.  Wells on a pad come online in one
    campaign, so pad-mates share the same partial window; a random split hands
    the model pad-mates from which the partial-ness can be read off, and a
    pad-grouped split does not.  A missing completeness rule therefore presents
    to the measurement as leakage, and the paper would have over-reported New
    Mexico.  This script measures by how much.

WHAT IT DOES
    Runs the two New Mexico sets -- every well the old rule admitted, and the
    13,947 that have twelve months of filings inside their window -- through
    three of the paper's measurements, on the paper's own seed schedule so the
    before and after are comparable:

      state inflation   random-split R2 minus pad-grouped R2 at 150 m, the
                        quantity section 5 reports, group-balanced folds
      8+ bin            the same on wells whose pad holds eight or more,
                        the largest occupancy cell of Table 2
      pad-grouped R2    the pad reference of Table 6, well-balanced folds

    python3 nm_rule_effect.py      -> nm_rule_effect.csv
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P                          # noqa: E402

import numpy as np                            # noqa: E402
import pandas as pd                           # noqa: E402

spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le = importlib.util.module_from_spec(spec)
sys.modules['le'] = le
spec.loader.exec_module(le)

# The helpers below are the paper's, taken from the scripts that produce the
# numbers being compared against, so that nothing but the input set differs.
_fc = open(P.out('fig_compute.py')).read()
_fc = _fc[:_fc.index('# --- END OF REUSABLE HELPERS ---')]
_m = {'__name__': 'fc_helpers', '__file__': P.out('fig_compute.py')}
exec(compile(_fc, P.out('fig_compute.py'), 'exec'), _m)
fit, SEEDS, SPLITS, TEST = _m['fit'], _m['SEEDS'], _m['SPLITS'], _m['TEST']

_pc = open(P.out('proxy_compare.py')).read()
_pc = _pc[:_pc.index('def fit(')]
_n = {'__name__': 'pc_helpers', '__file__': P.out('proxy_compare.py')}
exec(compile(_pc, P.out('proxy_compare.py'), 'exec'), _n)
group_row_split = _n['group_row_split']

from sklearn.ensemble import HistGradientBoostingRegressor   # noqa: E402
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit   # noqa: E402

T95 = 2.068658        # t(0.975, 23): SEEDS = 24


def ci_of(v):
    return float(T95 * np.asarray(v).std(ddof=1) / np.sqrt(len(v)))


def inflation(d, feats, pad):
    """Paired per-seed random-minus-grouped R2, group-balanced folds."""
    X = d[feats].to_numpy(float)
    y = d['y'].to_numpy(float)
    rv, pv = [], []
    for s in range(SEEDS):
        rv.append(fit(X, y, ShuffleSplit(SPLITS, test_size=TEST, random_state=s),
                      None, s))
        pv.append(fit(X, y, GroupShuffleSplit(SPLITS, test_size=TEST,
                                              random_state=s), pad, s))
    iv = np.array(rv) - np.array(pv)
    return float(iv.mean()), ci_of(iv), float(np.mean(rv)), float(np.mean(pv))


def well_balanced_pad(d, feats, pad):
    """Table 6's pad reference: whole groups held out until 20% of WELLS are."""
    X = d[feats].to_numpy(float)
    y = d['y'].to_numpy(float)
    out = []
    for s in range(SEEDS):
        v = []
        for tr, te in group_row_split(pad, TEST, SPLITS, s):
            if len(te) < 20 or len(tr) < 50:
                continue
            m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                              random_state=s, early_stopping=False)
            m.fit(X[tr], y[tr])
            p = m.predict(X[te])
            sst = float(((y[te] - y[te].mean()) ** 2).sum())
            if sst > 0:
                v.append(1 - float(((y[te] - p) ** 2).sum()) / sst)
        out.append(float(np.mean(v)))
    return float(np.mean(out)), ci_of(out)


def prepare(complete_only):
    """The New Mexico analysis set, with and without the completeness rule."""
    d = pd.read_csv(P.nmcsv('nm_well_summary.csv'), low_memory=False)
    if 'n_months_in_window' not in d.columns:
        raise SystemExit('nm_well_summary.csv has no n_months_in_window column; '
                         're-run nm_build.py.')
    d = d[d.directional_status == 'H']
    if complete_only:
        d = d[pd.to_numeric(d.n_months_in_window, errors='coerce') == 12]
    d = d.copy()
    d['lat'] = pd.to_numeric(d.lat, errors='coerce')
    d['lon'] = pd.to_numeric(d.lon, errors='coerce')
    d['spud_year'] = pd.to_datetime(d.spud_dte, errors='coerce').dt.year
    d = d[(d.spud_year >= 2010) & (d.spud_year <= 2026)]
    d['y_raw'] = pd.to_numeric(d.first365_G, errors='coerce')
    d['depth'] = pd.to_numeric(d.md, errors='coerce')
    d['elev'] = pd.to_numeric(d.tvd, errors='coerce')
    d['n_stim'] = pd.to_numeric(d.n_pools, errors='coerce')
    feats = ['lat', 'lon', 'spud_year', 'depth', 'elev', 'n_stim']
    d = le.tidy(d, feats)
    d['pad_true'] = le.infer_pads(d.lat.to_numpy(), d.lon.to_numpy()).astype(str)
    d['pad_size'] = d.groupby('pad_true').pad_true.transform('size').values
    return d.reset_index(drop=True), feats


rows = []
for complete_only, label in ((False, 'no completeness rule'),
                             (True, 'twelve months required')):
    d, feats = prepare(complete_only)
    pad = pd.factorize(d.pad_true.astype(str))[0]
    print('\n%s -- %d wells on %d inferred pads'
          % (label, len(d), len(set(pad))), flush=True)

    infl, ci, rnd, grp = inflation(d, feats, pad)
    print('  state inflation   %+.4f +- %.4f   (random %.4f, pad %.4f)'
          % (infl, ci, rnd, grp), flush=True)
    rows.append({'rule': label, 'measure': 'state inflation', 'wells': len(d),
                 'pads': len(set(pad)), 'value': infl, 'ci': ci,
                 'random': rnd, 'pad_grouped': grp})

    s = d[d.pad_size >= 8]
    spad = pd.factorize(s.pad_true.astype(str))[0]
    i8, c8, r8, g8 = inflation(s, feats, spad)
    print('  8+ occupancy bin  %+.4f +- %.4f   (%d wells)'
          % (i8, c8, len(s)), flush=True)
    rows.append({'rule': label, 'measure': '8+ occupancy bin', 'wells': len(s),
                 'pads': len(set(spad)), 'value': i8, 'ci': c8,
                 'random': r8, 'pad_grouped': g8})

    wb, wbci = well_balanced_pad(d, feats, pad)
    print('  pad-grouped R2     %.4f +- %.4f   (Table 6 schedule)'
          % (wb, wbci), flush=True)
    rows.append({'rule': label, 'measure': 'pad-grouped R2 (Table 6)',
                 'wells': len(d), 'pads': len(set(pad)), 'value': wb,
                 'ci': wbci, 'random': float('nan'), 'pad_grouped': wb})

pd.DataFrame(rows).to_csv(P.out('nm_rule_effect.csv'), index=False)
print('\nwrote nm_rule_effect.csv')
