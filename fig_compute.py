"""Per-seed inflation for the figure: paired random/placebo/pad within each seed."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, os, numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le=importlib.util.module_from_spec(spec); sys.modules['le']=le; spec.loader.exec_module(le)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit
# 24 seeds, not six. At six the pooled inflations were not reproducible
# to the three decimals the manuscript printed: re-running the same data
# under a different labelling of the SAME pad partition moved Colorado's
# grouped score by 0.011, and Pennsylvania's and New Mexico's
# coordinate-removal effects did not resolve at all. The data is public,
# so a replicator who lands 0.02 away must be able to see that as
# agreement rather than contradiction; that needs seeds and intervals.
SEEDS, SPLITS, TEST = 24, 5, 0.20
OH = P.oh() + os.sep

def fit(X,y,sp,groups,seed):
    out=[]
    it = sp.split(X,y) if groups is None else sp.split(X,y,groups=groups)
    for tr,te in it:
        if len(te)<20 or len(tr)<50: continue
        m=HistGradientBoostingRegressor(max_iter=300,learning_rate=0.06,random_state=seed,early_stopping=False)
        m.fit(X[tr],y[tr]); p=m.predict(X[te])
        sst=float(((y[te]-y[te].mean())**2).sum())
        if sst>0: out.append(1-float(((y[te]-p)**2).sum())/sst)
    return float(np.mean(out)) if out else np.nan

def cellrows(df,feats,padcol,state,lab):
    X=df[feats].to_numpy(float); y=df['y'].to_numpy(float)
    pad=pd.factorize(df[padcol].astype(str))[0]
    sizes=np.bincount(pad); sizes=sizes[sizes>0]
    rows=[]
    for s in range(SEEDS):
        rng=np.random.default_rng(1000+s)
        plac=np.repeat(np.arange(len(sizes)),sizes); rng.shuffle(plac)
        r=fit(X,y,ShuffleSplit(SPLITS,test_size=TEST,random_state=s),None,s)
        g=fit(X,y,GroupShuffleSplit(SPLITS,test_size=TEST,random_state=s),pad,s)
        q=fit(X,y,GroupShuffleSplit(SPLITS,test_size=TEST,random_state=s),plac,s)
        rows.append({'state':state,'bin':lab,'seed':s,'wells':len(df),
                     'mean_wells_per_pad':float(df.groupby(padcol)[padcol].transform('size').mean()),
                     'random':r,'pad':g,'placebo':q,
                     'inflation':r-g,'placebo_effect':r-q})
    print('  %-14s %-10s n=%5d  infl %+0.3f'%(state,lab,len(df),
          np.mean([x['inflation'] for x in rows])), flush=True)
    return rows
# --- END OF REUSABLE HELPERS --- radius_fine.py / co_fig.py split here

# Ohio drops n_stim (= n_q_total, partly downstream of the target)
FE=['lat','lon','spud_year','depth','elev']
allrows=[]
# Pennsylvania
d,feats=le.load_pennsylvania()
d['pad_size']=d.groupby(d.pad_true.astype(str)).pad_true.transform('size').values
for lo,hi,lab in [(1,1,'1'),(2,3,'2-3'),(4,5,'4-5'),(6,99,'6+')]:
    s=d[(d.pad_size>=lo)&(d.pad_size<=hi)]
    if len(s)>=400: allrows+=cellrows(s,feats,'pad_true','Pennsylvania',lab)
# Ohio
o=pd.read_csv(OH+'oh_analysis.csv',dtype={'PadNumber':str,'OPNO':str},low_memory=False)
o['first_prod']=pd.to_datetime(o.first_prod,errors='coerce')
o['y']=np.log10(pd.to_numeric(o.first4_gas,errors='coerce'))
o['spud_year']=pd.to_datetime(o.DT_SPUD,errors='coerce',format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth']=pd.to_numeric(o.DTD,errors='coerce'); o['elev']=pd.to_numeric(o.ELEV_GR,errors='coerce')
o['pad_true']=o.PadNumber.astype(str)
o=o.replace([np.inf,-np.inf],np.nan).dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
o['pad_size']=o.groupby('pad_true').pad_true.transform('size').values
for lo,hi,lab in [(1,1,'1'),(2,3,'2-3'),(4,5,'4-5'),(6,99,'6+')]:
    s=o[(o.pad_size>=lo)&(o.pad_size<=hi)]
    if len(s)>=250: allrows+=cellrows(s,FE,'pad_true','Ohio',lab)
# New Mexico
n,featsn=le.load_new_mexico()
n['pad_true']=le.infer_pads(n.lat.to_numpy(),n.lon.to_numpy()).astype(str)
n['pad_size']=n.groupby('pad_true').pad_true.transform('size').values
for lo,hi,lab in [(1,1,'1'),(2,3,'2-3'),(4,5,'4-5'),(6,7,'6-7'),(8,99,'8+')]:
    s=n[(n.pad_size>=lo)&(n.pad_size<=hi)]
    if len(s)>=400: allrows+=cellrows(s,featsn,'pad_true','New Mexico',lab)

pd.DataFrame(allrows).to_csv(P.out('fig_data.csv'),index=False)
print('wrote fig_data.csv')
