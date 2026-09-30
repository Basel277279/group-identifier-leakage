import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le=importlib.util.module_from_spec(spec); sys.modules['le']=le; spec.loader.exec_module(le)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit

d,feats=le.load_pennsylvania()
print('=== 1. duplicate wells and coincident coordinates ===')
for name,df,key in [('Pennsylvania',d,'api10')]:
    if key in df.columns:
        print('  %s: %d rows, %d distinct %s'%(name,len(df),df[key].nunique(),key))
    xy=df[['lat','lon']].round(6).astype(str).agg('_'.join,axis=1)
    print('  exactly coincident coordinate pairs: %d rows in %d locations'
          %((xy.duplicated(keep=False)).sum(), xy.nunique()))

print('\n=== 2. target distribution ===')
y=d.y.to_numpy()
print('  log10 first-365 gas: min %.2f  p1 %.2f  median %.2f  p99 %.2f  max %.2f'
      %(y.min(),np.percentile(y,1),np.median(y),np.percentile(y,99),y.max()))
print('  values below 10^2 mcf: %d   above 10^7: %d'%((y<2).sum(),(y>7).sum()))

print('\n=== 3. do grouped splits leave smaller training sets? ===')
X=d[feats].to_numpy(float)
pad=pd.factorize(d.pad_true.astype(str))[0]
inf150=le.infer_pads(d.lat.to_numpy(),d.lon.to_numpy())
for lab,g in [('random',None),('pad register',pad),('inferred 150 m',inf150)]:
    tr_sz=[]
    for s in range(6):
        sp=(ShuffleSplit(5,test_size=.2,random_state=s) if g is None
            else GroupShuffleSplit(5,test_size=.2,random_state=s))
        it=sp.split(X,d.y.to_numpy()) if g is None else sp.split(X,d.y.to_numpy(),groups=g)
        for tr,te in it: tr_sz.append(len(tr))
    tr_sz=np.array(tr_sz)
    print('  %-15s train n: mean %6.0f  min %5d  max %5d  (of %d)'
          %(lab,tr_sz.mean(),tr_sz.min(),tr_sz.max(),len(d)))

print('\n=== 4. contribution 4 re-verified: inferred vs true pads, through the model ===')
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
def sc(g,S=8):
    return np.array([fit(X,d.y.to_numpy(),GroupShuffleSplit(5,test_size=.2,random_state=s),g,s)
                     for s in range(S)])
a=sc(pad); b=sc(inf150)
print('  pad register    R2 %.3f +-%.3f'%(a.mean(),a.std(ddof=1)))
print('  inferred 150 m  R2 %.3f +-%.3f'%(b.mean(),b.std(ddof=1)))
print('  difference      %+.3f  (95%% CI %+.3f to %+.3f)'
      %((b-a).mean(),(b-a).mean()-1.96*(b-a).std(ddof=1)/np.sqrt(len(a)),
        (b-a).mean()+1.96*(b-a).std(ddof=1)/np.sqrt(len(a))))
