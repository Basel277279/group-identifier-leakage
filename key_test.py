"""Is the leak carried by pad-IDENTIFYING covariates rather than by space?

If so, a feature that is constant within a pad should leak on its own, and
removing it should reduce the leak. Ground elevation is identical within 87% of
Ohio pads and 74% of Pennsylvania pads -- wells on one pad share a surface
location, so they share an elevation.

Prediction: elevation alone leaks; dropping it reduces the leak.
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
def sc(X,y,g,S=6):
    return np.array([fit(X,y,(ShuffleSplit(5,test_size=.2,random_state=s) if g is None
                     else GroupShuffleSplit(5,test_size=.2,random_state=s)),g,s) for s in range(S)])
def block(name,d,pad,sets):
    y=d['y'].to_numpy(float)
    print('\n%s -- %d wells'%(name,len(d)))
    print('  %-26s %8s %8s %11s   %s'%('features','random','pad','inflation','within-pad constancy'))
    for lab,F,note in sets:
        X=d[F].to_numpy(float)
        r=sc(X,y,None); g=sc(X,y,pad)
        print('  %-26s %8.3f %8.3f %+11.3f   %s'%(lab,r.mean(),g.mean(),(r-g).mean(),note), flush=True)

d,feats=le.load_pennsylvania()
pad=pd.factorize(d.pad_true.astype(str))[0]
block('Pennsylvania',d,pad,[
  ('all 6',['lat','lon','spud_year','depth','elev','n_stim'],''),
  ('elevation alone',['elev'],'74% of pads share one value'),
  ('spud year alone',['spud_year'],'70%'),
  ('depth alone',['depth'],'0.2%'),
  ('no elev, no coords',['spud_year','depth','n_stim'],''),
])
o=pd.read_csv(OH+'oh_analysis.csv',dtype={'PadNumber':str},low_memory=False)
o['first_prod']=pd.to_datetime(o.first_prod,errors='coerce')
o['y']=np.log10(pd.to_numeric(o.first4_gas,errors='coerce'))
o['spud_year']=pd.to_datetime(o.DT_SPUD,errors='coerce',format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth']=pd.to_numeric(o.DTD,errors='coerce'); o['elev']=pd.to_numeric(o.ELEV_GR,errors='coerce')
o=o.replace([np.inf,-np.inf],np.nan).dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
padO=pd.factorize(o.PadNumber.astype(str))[0]
block('Ohio',o,padO,[
  ('all 5',['lat','lon','spud_year','depth','elev'],''),
  ('elevation alone',['elev'],'87% of pads share one value'),
  ('spud year alone',['spud_year'],'78%'),
  ('depth alone',['depth'],'3.5%'),
  ('no elev, no coords',['spud_year','depth'],''),
])
