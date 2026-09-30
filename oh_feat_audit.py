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
SEEDS = 24      # the paper's schedule; at six the difference this script
                # measures was smaller than its own between-seed spread
def sc(X,y,g,S=SEEDS):
    return np.array([fit(X,y,(ShuffleSplit(5,test_size=.2,random_state=s) if g is None
                     else GroupShuffleSplit(5,test_size=.2,random_state=s)),g,s) for s in range(S)])
o=pd.read_csv(OH+'oh_analysis.csv',dtype={'PadNumber':str},low_memory=False)
o['first_prod']=pd.to_datetime(o.first_prod,errors='coerce')
o['y']=np.log10(pd.to_numeric(o.first4_gas,errors='coerce'))
o['spud_year']=pd.to_datetime(o.DT_SPUD,errors='coerce',format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth']=pd.to_numeric(o.DTD,errors='coerce'); o['elev']=pd.to_numeric(o.ELEV_GR,errors='coerce')
o['n_stim']=pd.to_numeric(o.n_q_total,errors='coerce')
o=o.replace([np.inf,-np.inf],np.nan).dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
o['pad_size']=o.groupby(o.PadNumber.astype(str)).PadNumber.transform('size').values
pad=pd.factorize(o.PadNumber.astype(str))[0]; y=o.y.to_numpy(float)
T95 = 2.068658      # t(0.975, 23)
rows=[]
for lab,F in [('with n_q_total',['lat','lon','spud_year','depth','elev','n_stim']),
              ('WITHOUT it',['lat','lon','spud_year','depth','elev'])]:
    X=o[F].to_numpy(float); r=sc(X,y,None); g=sc(X,y,pad)
    iv=r-g; ci=T95*iv.std(ddof=1)/np.sqrt(len(iv))
    print('%-16s all wells: random %.3f  pad %.3f  inflation %+.4f +-%.4f'
          %(lab,r.mean(),g.mean(),iv.mean(),ci),flush=True)
    rows.append({'features':lab,'bin':'all','wells':len(o),'random':float(r.mean()),
                 'pad':float(g.mean()),'inflation':float(iv.mean()),'ci':float(ci)})
    for lo,hi,t in [(2,3,'2-3'),(4,5,'4-5'),(6,99,'6+')]:
        s=o[(o.pad_size>=lo)&(o.pad_size<=hi)]
        if len(s)<150: continue
        rr=sc(s[F].to_numpy(float),s.y.to_numpy(float),None)
        gg=sc(s[F].to_numpy(float),s.y.to_numpy(float),pd.factorize(s.PadNumber.astype(str))[0])
        jv=rr-gg; jci=T95*jv.std(ddof=1)/np.sqrt(len(jv))
        print('    %-5s n=%4d random %.3f pad %.3f inflation %+.4f +-%.4f'
              %(t,len(s),rr.mean(),gg.mean(),jv.mean(),jci),flush=True)
        rows.append({'features':lab,'bin':t,'wells':len(s),'random':float(rr.mean()),
                     'pad':float(gg.mean()),'inflation':float(jv.mean()),'ci':float(jci)})
pd.DataFrame(rows).to_csv(P.out('oh_feat_audit.csv'),index=False)
print('wrote oh_feat_audit.csv')
