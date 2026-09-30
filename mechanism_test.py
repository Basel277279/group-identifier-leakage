"""Is the leak carried by the coordinate features?

STATED BEFORE RUNNING
    The radius sweep showed the whole effect appearing at 3-15 m and little
    added out to 300 m. One explanation: the model reconstructs the regional
    trend from lat/lon, so removing wells within 300 m costs nothing it cannot
    interpolate back, while the pad-specific offset is the one thing it cannot.

    If that is right, then with lat/lon REMOVED the model can no longer
    identify which training wells are a test well's neighbours, and inflation
    should collapse toward zero at every radius, pad scale included.

    If inflation survives without coordinates, the pad signal is carried by
    other pad-constant covariates -- depth, spud year -- and the leak is not a
    memorisation-of-location effect.

    Three feature sets, same model, same splits:
        full          lat, lon, spud_year, depth, elev [, n_stim]
        no-coords     spud_year, depth, elev [, n_stim]
        coords-only   lat, lon

Six seeds x five splits, 20% held out.

ALL FOUR STATES
    Pennsylvania and Ohio are swept across five radii and their registers.
    New Mexico and Colorado are run at the transferred 150 m radius only:
    the radius question is settled in §5 and the point here is the feature
    set, so five more radii on 15,911 and 12,101 wells would buy nothing.
    Both use the substituted surface elevation of §S5 -- New Mexico's summary
    carries none, so `elev_gl_num` is joined back from `wellhistory` -- because
    the comparison is meaningless without an elevation in every state.
    `nocoord_nmco.py` did this first at four seeds and is superseded by it.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le = importlib.util.module_from_spec(spec); sys.modules['le'] = le; spec.loader.exec_module(le)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit

OH = P.oh() + os.sep
# 24 seeds, not six. At six the pooled inflations were not reproducible
# to the three decimals the manuscript printed: re-running the same data
# under a different labelling of the SAME pad partition moved Colorado's
# grouped score by 0.011, and Pennsylvania's and New Mexico's
# coordinate-removal effects did not resolve at all. The data is public,
# so a replicator who lands 0.02 away must be able to see that as
# agreement rather than contradiction; that needs seeds and intervals.
SEEDS, SPLITS, TEST = 24, 5, 0.20
RADII = [10, 25, 100, 300, 1000]


def fit(X, y, sp, g, seed):
    out = []
    it = sp.split(X, y) if g is None else sp.split(X, y, groups=g)
    for tr, te in it:
        if len(te) < 20 or len(tr) < 50:
            continue
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06,
                                          random_state=seed, early_stopping=False)
        m.fit(X[tr], y[tr]); p = m.predict(X[te])
        sst = float(((y[te] - y[te].mean()) ** 2).sum())
        if sst > 0:
            out.append(1 - float(((y[te] - p) ** 2).sum()) / sst)
    return float(np.mean(out))


def sc(X, y, g):
    return np.array([fit(X, y, (ShuffleSplit(SPLITS, test_size=TEST, random_state=s)
                                if g is None else
                                GroupShuffleSplit(SPLITS, test_size=TEST, random_state=s)),
                         g, s) for s in range(SEEDS)])


def run(name, d, full, padcol, radii=None):
    nocoord = [f for f in full if f not in ('lat', 'lon')]
    sets = [('full', full), ('no-coords', nocoord), ('coords-only', ['lat', 'lon'])]
    y = d['y'].to_numpy(float)
    lat, lon = d.lat.to_numpy(), d.lon.to_numpy()
    groupings = [('random', None)]
    if padcol is not None:
        groupings.append(('pad register', pd.factorize(d[padcol].astype(str))[0]))
    for r in (RADII if radii is None else radii):
        groupings.append(('%d m' % r, le.infer_pads(lat, lon, radius_m=float(r))))

    print('\n' + '=' * 78)
    print('%s -- %d wells' % (name.upper(), len(d)))
    print('=' * 78)
    print('%-14s %12s %12s %12s' % ('grouping', 'full', 'no-coords', 'coords-only'))
    rows = []
    base = {}
    for lab, feats in sets:
        base[lab] = sc(d[feats].to_numpy(float), y, None).mean()
    print('%-14s %12.3f %12.3f %12.3f   <- random split R2'
          % ('(baseline)', base['full'], base['no-coords'], base['coords-only']), flush=True)
    for gl, g in groupings:
        if g is None:
            continue
        vals = {}
        for lab, feats in sets:
            v = sc(d[feats].to_numpy(float), y, g).mean()
            vals[lab] = base[lab] - v
        print('%-14s %+12.3f %+12.3f %+12.3f' % (gl, vals['full'], vals['no-coords'],
                                                 vals['coords-only']), flush=True)
        rows.append({'state': name, 'grouping': gl, **{'infl_' + k: v for k, v in vals.items()}})
    return rows


rows = []
d, feats = le.load_pennsylvania()
rows += run('Pennsylvania', d, feats, 'pad_true')

o = pd.read_csv(OH + 'oh_analysis.csv', dtype={'PadNumber': str}, low_memory=False)
o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
o['spud_year'] = pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth'] = pd.to_numeric(o.DTD, errors='coerce'); o['elev'] = pd.to_numeric(o.ELEV_GR, errors='coerce')
o = o.replace([np.inf, -np.inf], np.nan).dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True)
rows += run('Ohio', o, ['lat', 'lon', 'spud_year', 'depth', 'elev'], 'PadNumber')

# New Mexico: ground elevation is not in the well summary, so join elev_gl_num
# from wellhistory, exactly as covariate_audit.py does (§S5).
NMS = P.nmcsv() + os.sep
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
rows += run('New Mexico', n, ['lat', 'lon', 'spud_year', 'depth', 'tvd', 'gelev'],
            None, radii=[150])

c = pd.read_csv(P.co('co_analysis.csv'), low_memory=False)
c['y'] = np.log10(pd.to_numeric(c.first365_G, errors='coerce').where(lambda s: s > 0))
c['spud_year'] = pd.to_datetime(c.spud_dte, errors='coerce').dt.year
c['depth'] = pd.to_numeric(c.max_md, errors='coerce')
c['tvd'] = pd.to_numeric(c.max_tvd, errors='coerce')
c['gelev'] = pd.to_numeric(c.ground_elev, errors='coerce')
c = (c.replace([np.inf, -np.inf], np.nan)
      .dropna(subset=['lat', 'lon', 'y', 'spud_year', 'gelev']).reset_index(drop=True))
rows += run('Colorado', c, ['lat', 'lon', 'spud_year', 'depth', 'tvd', 'gelev'],
            None, radii=[150])

pd.DataFrame(rows).to_csv(P.out('mechanism_test.csv'), index=False)
print('\nwrote mechanism_test.csv')
