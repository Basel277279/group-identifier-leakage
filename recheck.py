"""Targeted re-checks after the clustering fix.
A: PA radius sweep at 150 m / 300 m / 1 km -- where the fix changed most.
B: Ohio without the contaminated n_q_total feature."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le=importlib.util.module_from_spec(spec); sys.modules['le']=le; spec.loader.exec_module(le)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit
OH = P.oh() + os.sep
S=6
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

d,feats=le.load_pennsylvania()
X=d[feats].to_numpy(float); y=d.y.to_numpy(float)
r=sc(X,y,None)
print('A. PENNSYLVANIA, fixed clustering (random %.3f)'%r.mean(), flush=True)
print('   %-8s %7s %8s %10s   %s'%('radius','groups','score','inflation','was (buggy)'), flush=True)
OLD={150:(1016,0.553,0.099),300:(1011,0.584,0.067),1000:(783,0.583,0.068)}
for rad in (150,300,1000):
    g=le.infer_pads(d.lat.to_numpy(),d.lon.to_numpy(),radius_m=float(rad))
    v=sc(X,y,g)
    o=OLD[rad]
    print('   %-8d %7d %8.3f %+10.3f   %d groups, %.3f, %+.3f'
          %(rad,len(set(g)),v.mean(),r.mean()-v.mean(),o[0],o[1],o[2]), flush=True)

o=pd.read_csv(OH+'oh_analysis.csv',dtype={'PadNumber':str},low_memory=False)
o['first_prod']=pd.to_datetime(o.first_prod,errors='coerce')
o['y']=np.log10(pd.to_numeric(o.first4_gas,errors='coerce'))
o['spud_year']=pd.to_datetime(o.DT_SPUD,errors='coerce',format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth']=pd.to_numeric(o.DTD,errors='coerce'); o['elev']=pd.to_numeric(o.ELEV_GR,errors='coerce')
o=o.replace([np.inf,-np.inf],np.nan).dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
pad=pd.factorize(o.PadNumber.astype(str))[0]; yo=o.y.to_numpy(float)
F=['lat','lon','spud_year','depth','elev']
Xo=o[F].to_numpy(float)
ro=sc(Xo,yo,None); go=sc(Xo,yo,pad)
print('\nB. OHIO without n_q_total: random %.3f  pad %.3f  inflation %+.3f'
      %(ro.mean(),go.mean(),(ro-go).mean()), flush=True)
print('   with it, for comparison:  random 0.905  pad 0.804  inflation +0.101', flush=True)
