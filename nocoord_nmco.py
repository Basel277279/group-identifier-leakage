"""Does removing coordinates worsen the leak in New Mexico and Colorado too,
or is that a Pennsylvania/Ohio effect driven by their pad-constant elevation?"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le=importlib.util.module_from_spec(spec); sys.modules['le']=le; spec.loader.exec_module(le)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit
NMS = P.nmcsv() + os.sep
S=4
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
                     else GroupShuffleSplit(5,test_size=.2,random_state=s)),g,s) for s in range(S)])
def block(name,d,pad,full):
    nocoord=[f for f in full if f not in ('lat','lon')]
    y=d['y'].to_numpy(float)
    print('\n%s -- %d wells'%(name,len(d)))
    print('  %-14s %8s %8s %11s'%('features','random','pad','inflation'))
    for lab,F in [('full',full),('no coordinates',nocoord)]:
        X=d[F].to_numpy(float); r=sc(X,y,None); g=sc(X,y,pad)
        print('  %-14s %8.3f %8.3f %+11.3f'%(lab,r.mean(),g.mean(),(r-g).mean()), flush=True)

n,_=le.load_new_mexico()
wh=pd.read_csv(NMS+'wellhistory.csv',dtype=str,low_memory=False,
   usecols=['api_st_cde','api_cnty_cde','api_well_idn','rec_termn_dte','elev_gl_num'])
wh=wh[wh.rec_termn_dte.str.startswith('9999',na=False)]
wh['api10']=wh.api_st_cde.str.zfill(2)+wh.api_cnty_cde.str.zfill(3)+wh.api_well_idn.str.zfill(5)
wh['gelev']=pd.to_numeric(wh.elev_gl_num,errors='coerce')
n['api10']=n.api10.astype(str)
n=n.merge(wh[['api10','gelev']].drop_duplicates('api10'),on='api10',how='left')
n=n.dropna(subset=['gelev']).reset_index(drop=True)
n['pad']=le.infer_pads(n.lat.to_numpy(),n.lon.to_numpy()).astype(str)
block('New Mexico',n,pd.factorize(n.pad)[0],['lat','lon','spud_year','depth','tvd','gelev'])

c=pd.read_csv(P.co('co_analysis.csv'),low_memory=False)
c['y']=np.log10(pd.to_numeric(c.first365_G,errors='coerce').where(lambda s:s>0))
c['spud_year']=pd.to_datetime(c.spud_dte,errors='coerce').dt.year
c['depth']=pd.to_numeric(c.max_md,errors='coerce'); c['gelev']=pd.to_numeric(c.ground_elev,errors='coerce')
c['tvd']=pd.to_numeric(c.max_tvd,errors='coerce')
c=c.replace([np.inf,-np.inf],np.nan).dropna(subset=['lat','lon','y','spud_year','gelev']).reset_index(drop=True)
c['pad']=le.infer_pads(c.lat.to_numpy(),c.lon.to_numpy()).astype(str)
block('Colorado',c,pd.factorize(c.pad)[0],['lat','lon','spud_year','depth','tvd','gelev'])
