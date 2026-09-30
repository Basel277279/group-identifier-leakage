import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
spec=importlib.util.spec_from_file_location('g',P.out('pad_size_gradient.py'))
g=importlib.util.module_from_spec(spec); sys.modules['g']=g; spec.loader.exec_module(g)
le=sys.modules['le']
d=pd.read_csv(P.co('co_analysis.csv'),dtype={'api8':str,'operator':str},low_memory=False)
d['y']=np.log10(pd.to_numeric(d.first365_G,errors='coerce').where(lambda s:s>0))
d['spud_year']=pd.to_datetime(d.spud_dte,errors='coerce').dt.year
d['depth']=pd.to_numeric(d.max_md,errors='coerce'); d['elev']=pd.to_numeric(d.ground_elev,errors='coerce')
d['n_stim']=pd.to_numeric(d.max_tvd,errors='coerce')
d=d.dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
d['pad_true']=le.infer_pads(d.lat.to_numpy(),d.lon.to_numpy()).astype(str)
d['pad_size']=d.groupby('pad_true').pad_true.transform('size').values
sz=d.groupby('pad_true').size()
print('COLORADO: %d wells, %d inferred pads'%(len(d),d.pad_true.nunique()))
print('  wells/pad median %d mean %.2f max %d'%(sz.median(),sz.mean(),sz.max()))
print('  pad size distribution:'); print(sz.value_counts().sort_index().head(20).to_string())
F=['lat','lon','spud_year','depth','elev','n_stim']
print('\n%-12s %7s   %-15s %-15s %-15s %11s %12s'%('pad size','wells','random','placebo','pad','inflation','placebo eff'))
rows=[]
for lo,hi,lab in [(1,1,'1'),(2,3,'2-3'),(4,5,'4-5'),(6,7,'6-7'),(8,11,'8-11'),(12,999,'12+')]:
    s=d[(d.pad_size>=lo)&(d.pad_size<=hi)]
    if len(s)<250: print('%-12s %7d   (too few)'%(lab,len(s))); continue
    c=g.cell(s,F,'pad_true'); r,p,q=c['random'],c['placebo'],c['pad']
    mw=float(s.pad_size.mean())
    print('%-12s %7d   %6.3f +-%.3f   %6.3f +-%.3f   %6.3f +-%.3f  %+10.3f %+12.3f  (mean %.1f)'
          %(lab,len(s),r[0],r[1],p[0],p[1],q[0],q[1],r[0]-q[0],r[0]-p[0],mw), flush=True)
    rows.append({'state':'Colorado','bin':lab,'wells':len(s),'mean_wells_per_pad':mw,
                 'random':r[0],'placebo':p[0],'pad':q[0],'inflation':r[0]-q[0],'placebo_effect':r[0]-p[0]})
pd.DataFrame(rows).to_csv(P.out('co_gradient.csv'),index=False)
