"""Mechanism test on New Mexico and Colorado: is ground elevation a pad label there too?

New Mexico's ground elevation (elev_gl_num) is joined back from wellhistory;
Colorado's (Ground_Ele) comes from the shapefile. Both are surveyed per surface
location, so the prediction is the same as Ohio and Pennsylvania: near-constant
within pads, and leaking on its own.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le=importlib.util.module_from_spec(spec); sys.modules['le']=le; spec.loader.exec_module(le)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit
NMS = P.nmcsv() + os.sep
SEEDS=4
def fit(X,y,sp,g,seed):
    out=[]
    it=sp.split(X,y) if g is None else sp.split(X,y,groups=g)
    for tr,te in it:
        if len(te)<20 or len(tr)<50: continue
        m=HistGradientBoostingRegressor(max_iter=300,learning_rate=0.06,random_state=seed,early_stopping=False)
        m.fit(X[tr],y[tr]); p=m.predict(X[te])
        sst=float(((y[te]-y[te].mean())**2).sum())
        if sst>0: out.append(1-float(((y[te]-p)**2).sum())/sst)
    return float(np.mean(out))
def sc(X,y,g):
    return np.array([fit(X,y,(ShuffleSplit(5,test_size=.2,random_state=s) if g is None
                     else GroupShuffleSplit(5,test_size=.2,random_state=s)),g,s) for s in range(SEEDS)])

def constancy(name,d,padcol,cols):
    multi=d.groupby(padcol).filter(lambda g: len(g)>1)
    print('  within-pad constancy (%d wells on multi-well pads):'%len(multi))
    for c in cols:
        v=pd.to_numeric(multi[c],errors='coerce'); t=multi.assign(_v=v)
        const=100*(t.groupby(padcol)._v.nunique(dropna=False)<=1).mean()
        vc=t.groupby('_v')[padcol].nunique(); uniq=100*(t._v.map(vc)==1).mean()
        print('    %-14s identical in %5.1f%% of pads;  %4.1f%% of wells have a pad-unique value'%(c,const,uniq))

def leak(name,d,pad,sets):
    y=d['y'].to_numpy(float)
    print('  %-22s %8s %8s %11s'%('features','random','pad','inflation'))
    for lab,F in sets:
        X=d[F].to_numpy(float); r=sc(X,y,None); g=sc(X,y,pad)
        print('  %-22s %8.3f %8.3f %+11.3f'%(lab,r.mean(),g.mean(),(r-g).mean()), flush=True)

# ---- New Mexico, with ground elevation joined back ----
n,fn=le.load_new_mexico()
wh=pd.read_csv(NMS+'wellhistory.csv',dtype=str,low_memory=False,
               usecols=['api_st_cde','api_cnty_cde','api_well_idn','rec_termn_dte','elev_gl_num'])
wh=wh[wh.rec_termn_dte.str.startswith('9999',na=False)]
wh['api10']=wh.api_st_cde.str.zfill(2)+wh.api_cnty_cde.str.zfill(3)+wh.api_well_idn.str.zfill(5)
wh['gelev']=pd.to_numeric(wh.elev_gl_num,errors='coerce')
n['api10']=n.api10.astype(str)
n=n.merge(wh[['api10','gelev']].drop_duplicates('api10'),on='api10',how='left')
n['pad']=le.infer_pads(n.lat.to_numpy(),n.lon.to_numpy()).astype(str)
n=n.dropna(subset=['gelev']).reset_index(drop=True)
print('\nNEW MEXICO -- %d wells with ground elevation, %d inferred pads'%(len(n),n.pad.nunique()))
constancy('NM',n,'pad',['lat','spud_year','depth','gelev'])
leak('NM',n,pd.factorize(n.pad)[0],
     [('full + gelev',['lat','lon','spud_year','depth','tvd','gelev']),
      ('ground elevation alone',['gelev'])])

# ---- Colorado ----
c=pd.read_csv(P.co('co_analysis.csv'),low_memory=False)
c['y']=np.log10(pd.to_numeric(c.first365_G,errors='coerce').where(lambda s:s>0))
c['spud_year']=pd.to_datetime(c.spud_dte,errors='coerce').dt.year
c['depth']=pd.to_numeric(c.max_md,errors='coerce'); c['gelev']=pd.to_numeric(c.ground_elev,errors='coerce')
c['tvd']=pd.to_numeric(c.max_tvd,errors='coerce')
c=c.replace([np.inf,-np.inf],np.nan).dropna(subset=['lat','lon','y','spud_year','gelev']).reset_index(drop=True)
c['pad']=le.infer_pads(c.lat.to_numpy(),c.lon.to_numpy()).astype(str)
print('\nCOLORADO -- %d wells, %d inferred pads'%(len(c),c.pad.nunique()))
constancy('CO',c,'pad',['lat','spud_year','depth','gelev'])
leak('CO',c,pd.factorize(c.pad)[0],
     [('full + gelev',['lat','lon','spud_year','depth','tvd','gelev']),
      ('ground elevation alone',['gelev'])])
