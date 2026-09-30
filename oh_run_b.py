import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import importlib.util, sys, numpy as np, pandas as pd
spec=importlib.util.spec_from_file_location('g',P.out('pad_size_gradient.py'))
g=importlib.util.module_from_spec(spec); sys.modules['g']=g; spec.loader.exec_module(g)
OH = P.oh() + os.sep
d=pd.read_csv(OH+'oh_well_summary.csv',dtype={'api14':str,'PadNumber':str,'OPNO':str},low_memory=False)
d['first_prod']=pd.to_datetime(d.first_prod,errors='coerce')
d=d[d.lat.between(38,42.5)&d.lon.between(-85,-80)]
d=d[d.PadNumber.notna()]
d=d[pd.to_numeric(d.cum_gas,errors='coerce')>0].copy()
d['y']=np.log10(pd.to_numeric(d.cum_gas,errors='coerce'))
d['spud_year']=pd.to_datetime(d.DT_SPUD,errors='coerce',format='mixed').dt.year
d['spud_year']=d.spud_year.fillna(d.first_prod.dt.year)
d['depth']=pd.to_numeric(d.DTD,errors='coerce'); d['elev']=pd.to_numeric(d.ELEV_GR,errors='coerce')
d['n_stim']=pd.to_numeric(d.n_q_total,errors='coerce'); d['pad_true']=d.PadNumber.astype(str)
d=d.dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
d['pad_size']=d.groupby('pad_true').pad_true.transform('size').values
F=['lat','lon','spud_year','depth','elev','n_stim']
print('OHIO B: cumulative 2020-2026 gas -- %d wells, %d pads'%(len(d),d.pad_true.nunique()))
print('%-12s %7s   %-15s %-15s %-15s %11s %12s'%('pad size','wells','random','placebo','pad','inflation','placebo eff'))
for lo,hi,lab in [(1,1,'1 well'),(2,3,'2-3 wells'),(4,5,'4-5 wells'),(6,7,'6-7 wells'),(8,99,'8+ wells')]:
    s=d[(d.pad_size>=lo)&(d.pad_size<=hi)]
    if len(s)<150: print('%-12s %7d   (too few)'%(lab,len(s))); continue
    c=g.cell(s,F,'pad_true'); r,p,q=c['random'],c['placebo'],c['pad']
    print('%-12s %7d   %6.3f +-%.3f   %6.3f +-%.3f   %6.3f +-%.3f  %+10.3f %+12.3f'
          %(lab,len(s),r[0],r[1],p[0],p[1],q[0],q[1],r[0]-q[0],r[0]-p[0]), flush=True)
