"""Locate the step: radii below 10 m, where clusters break down into singletons."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import sys, numpy as np, pandas as pd
def _helpers_only(path):
    """The part of `path` above its sentinel, compiled but not run past it.

    This file needs another script's helper functions without triggering its
    experiment. It used to split the source on a literal (`"FE = ["`), so a
    reformat of that one line would have made `split` return the WHOLE file --
    which is then exec'd, re-running the experiment and overwriting its result
    CSV, silently and slowly. The marker is now an explicit sentinel and its
    absence is an error rather than a no-op.
    """
    sentinel = '# --- END OF REUSABLE HELPERS ---'
    src = open(path).read()
    head, sep, _tail = src.partition(sentinel)
    if not sep:
        raise SystemExit('%s no longer carries the line "%s". Restore it: this '
                         'script reuses the helpers above it and must not run '
                         'the experiment below it.' % (path, sentinel))
    return head

# reuse helpers without re-running the sweep
src=_helpers_only(P.out('radius_sweep.py'))
import types; m=types.ModuleType('rs')
# radius_sweep.py's header does sys.path.insert(..., dirname(abspath(__file__))),
# and a bare module dict has no __file__, so give it the real one. Without this
# the exec dies with NameError -- which it did, silently, for as long as this
# script went un-re-run: co_fig.py carried the identical bug and was fixed in
# isolation rather than in both places.
m.__dict__['__file__'] = P.out('radius_sweep.py')
exec(compile(src, P.out('radius_sweep.py'), 'exec'), m.__dict__)
le=sys.modules['le']
OH = P.oh() + os.sep
FINE=[1,2,3,5,7,10,15,20]
# Ohio drops n_stim (= n_q_total, partly downstream of the target)
FE=['lat','lon','spud_year','depth','elev']

def block(name,d,feats,padcol):
    X=d[feats].to_numpy(float); y=d['y'].to_numpy(float)
    lat,lon=d.lat.to_numpy(),d.lon.to_numpy()
    r0,_=m.score(X,y,None)
    print('\n%s -- %d wells, random %.3f'%(name,len(d),r0))
    g=pd.factorize(d[padcol].astype(str))[0]
    s,_=m.score(X,y,g)
    print('  %-10s %8d groups  mean %.2f  score %.3f  inflation %+.3f'
          %('register',len(set(g)),len(d)/len(set(g)),s,r0-s), flush=True)
    rows=[{'state':name,'radius_m':-1,'grouping':'pad register','groups':len(set(g)),
           'mean_size':len(d)/len(set(g)),'score':s,'inflation':r0-s,'random':r0}]
    for r in FINE:
        gg=le.infer_pads(lat,lon,radius_m=float(r)); n=len(set(gg))
        s,_=m.score(X,y,gg)
        print('  %-10s %8d groups  mean %.2f  score %.3f  inflation %+.3f'
              %('%d m'%r,n,len(d)/n,s,r0-s), flush=True)
        rows.append({'state':name,'radius_m':r,'grouping':'%d m'%r,'groups':n,
                     'mean_size':len(d)/n,'score':s,'inflation':r0-s,'random':r0})
    return rows

rows=[]
d,feats=le.load_pennsylvania(); rows+=block('Pennsylvania',d,feats,'pad_true')
o=pd.read_csv(OH+'oh_analysis.csv',dtype={'PadNumber':str,'OPNO':str},low_memory=False)
o['first_prod']=pd.to_datetime(o.first_prod,errors='coerce')
o['y']=np.log10(pd.to_numeric(o.first4_gas,errors='coerce'))
o['spud_year']=pd.to_datetime(o.DT_SPUD,errors='coerce',format='mixed').dt.year.fillna(o.first_prod.dt.year)
o['depth']=pd.to_numeric(o.DTD,errors='coerce'); o['elev']=pd.to_numeric(o.ELEV_GR,errors='coerce')
o['pad_true']=o.PadNumber.astype(str)
o=o.replace([np.inf,-np.inf],np.nan).dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
rows+=block('Ohio',o,FE,'pad_true')
pd.DataFrame(rows).to_csv(P.out('radius_fine.csv'),index=False)
print('\nwrote radius_fine.csv')
