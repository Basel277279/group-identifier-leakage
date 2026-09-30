"""Figure 5 data: every validation scheme, scored against the pad reference.

Same model, same features, same data; only the partition changes. Reported as
the difference from the pad-grouped score, so zero means "agrees with correct
validation", positive means optimistic and negative means over-conservative.

Twenty seeds x five splits, 20% of ROWS held out.

WHY NOT GroupShuffleSplit
    GroupShuffleSplit(test_size=0.20) holds out 20% of GROUPS. With pads that
    is nearly the same thing, because pads are small and numerous. With
    operators it is not: Pennsylvania has 31 of them and they are wildly
    unequal, so a 20%-of-groups split held out between 0.6% and 55.3% of the
    rows across the thirty folds, and the arm being compared to the pad
    reference therefore differed from it in training-set size and in the
    variance of the test fold -- the R2 denominator -- as well as in the
    partition. A scheme cannot be blamed for a score that a 45% training set
    produced.

    `group_row_split` instead walks a random permutation of the groups and
    takes each one whose addition brings the held-out row count closer to the
    target than stopping would, so every scheme holds out about the same share
    of rows while still never splitting a group. The achieved fraction is
    reported per scheme so the reader can see how close each one gets; with
    very few, very unequal groups it cannot always get close, and that is a
    property of the scheme, not an artefact of the measurement.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le=importlib.util.module_from_spec(spec); sys.modules['le']=le; spec.loader.exec_module(le)
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
SEEDS,SPLITS,TEST=24,5,0.20
T95=2.068658  # t(0.975, df=23)
# The alternatives here are compared against the pad reference as a
# DIFFERENCE, and with few groups a single seed moves that difference a long
# way: six seeds left Pennsylvania's operator interval at +-0.79, wide enough
# to swallow the result, and flipped the sign of its spud-year cell. At
# twenty-four that interval is +-0.26. The reference tightens too, so Table 6's
# random row and the state inflation of section 5 -- the same quantity on
# different fold schedules -- can be seen to agree.

def group_row_split(groups, test_size, n_splits, seed):
    """Hold out whole groups until about `test_size` of the ROWS are held out."""
    uniq, inv = np.unique(groups, return_inverse=True)
    sizes = np.bincount(inv)
    n = len(inv)
    target = test_size * n
    rng = np.random.default_rng(seed)
    for _ in range(n_splits):
        cum, chosen = 0, []
        for gi in rng.permutation(len(uniq)):
            if cum >= target:
                break
            # take this group only if it lands nearer the target than stopping
            if abs(cum + sizes[gi] - target) > abs(cum - target) and chosen:
                continue
            chosen.append(gi)
            cum += sizes[gi]
        te = np.isin(inv, chosen)
        yield np.flatnonzero(~te), np.flatnonzero(te)


def fit(X,y,sp,g,seed):
    out=[]; frac=[]
    it=sp.split(X,y) if g is None else sp
    for tr,te in it:
        if len(te)<20 or len(tr)<50: continue
        frac.append(len(te)/len(y))
        m=HistGradientBoostingRegressor(max_iter=300,learning_rate=0.06,random_state=seed,early_stopping=False)
        m.fit(X[tr],y[tr]); p=m.predict(X[te])
        sst=float(((y[te]-y[te].mean())**2).sum())
        if sst>0: out.append(1-float(((y[te]-p)**2).sum())/sst)
    return (float(np.mean(out)) if out else np.nan,
            float(np.mean(frac)) if frac else np.nan)

def per_seed(X,y,g):
    v,f=[],[]
    for s in range(SEEDS):
        sp=(ShuffleSplit(SPLITS,test_size=TEST,random_state=s) if g is None
            else group_row_split(g,TEST,SPLITS,s))
        r,fr=fit(X,y,sp,g,s)
        v.append(r); f.append(fr)
    return np.array(v,dtype=float), float(np.nanmean(f))

def run(name,d,feats,padcol,pad_kind):
    X=d[feats].to_numpy(float); y=d['y'].to_numpy(float)
    pad=pd.factorize(d[padcol].astype(str))[0]
    ref,ref_f=per_seed(X,y,pad)
    schemes=[('random',None),
             ('operator',pd.factorize(d.operator.astype(str))[0]),
             ('spud year',d.spud_year.astype(int).to_numpy()),
             ('spatial 10 km',le.grid_block(d.lat.to_numpy(),d.lon.to_numpy(),10)),
             ('spatial 25 km',le.grid_block(d.lat.to_numpy(),d.lon.to_numpy(),25))]
    rows=[{'state':name,'scheme':'pad (%s)'%pad_kind,'mean':float(ref.mean()),
           'delta':0.0,'ci':0.0,'groups':len(set(pad)),'held_out':ref_f}]
    print('\n%s -- pad reference R2 %.3f (%s), %.1f%% of rows held out'
          %(name,ref.mean(),pad_kind,100*ref_f))
    for lab,g in schemes:
        v,fr=per_seed(X,y,g)
        dlt=v-ref
        # Student t on SEEDS observations, not the normal 1.96
        ci=T95*dlt.std(ddof=1)/np.sqrt(len(dlt))
        n=len(d) if g is None else len(set(g))
        print('  %-14s R2 %7.3f   delta %+7.3f +-%.3f   groups %6d   held out %.1f%%'
              %(lab,v.mean(),dlt.mean(),ci,n,100*fr), flush=True)
        rows.append({'state':name,'scheme':lab,'mean':float(v.mean()),
                     'delta':float(dlt.mean()),'ci':float(ci),'groups':n,
                     'held_out':fr})
    return rows

# Ohio drops n_stim (= n_q_total, partly downstream of the target)
FE=['lat','lon','spud_year','depth','elev']
rows=[]
d,feats=le.load_pennsylvania(); rows+=run('Pennsylvania',d,feats,'pad_true','register')
o=pd.read_csv(OH+'oh_analysis.csv',dtype={'PadNumber':str,'OPNO':str},low_memory=False)
o['first_prod']=pd.to_datetime(o.first_prod,errors='coerce')
o['y']=np.log10(pd.to_numeric(o.first4_gas,errors='coerce'))
o['spud_year']=pd.to_datetime(o.DT_SPUD,errors='coerce',format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth']=pd.to_numeric(o.DTD,errors='coerce'); o['elev']=pd.to_numeric(o.ELEV_GR,errors='coerce')
o['pad_true']=o.PadNumber.astype(str)
o['operator']=o.OPNO.astype(str)
o=o.replace([np.inf,-np.inf],np.nan).dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
rows+=run('Ohio',o,FE,'pad_true','register')
n,fn=le.load_new_mexico()
n['pad_inf']=le.infer_pads(n.lat.to_numpy(),n.lon.to_numpy()).astype(str)
rows+=run('New Mexico',n,fn,'pad_inf','inferred')
pd.DataFrame(rows).to_csv(P.out('proxy_compare.csv'),index=False)
print('\nwrote proxy_compare.csv')
