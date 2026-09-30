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

# reuse cellrows without re-running the whole module
src=_helpers_only(P.out('fig_compute.py'))
import types; fc=types.ModuleType('fc')
# fig_compute.py's own header does sys.path.insert(..., dirname(abspath(__file__))),
# and a bare module dict has no __file__, so give it the real one.
fc.__dict__['__file__'] = P.out('fig_compute.py')
exec(compile(src, P.out('fig_compute.py'), 'exec'), fc.__dict__)
le=sys.modules.get('le') or fc.le
d=pd.read_csv(P.co('co_analysis.csv'),dtype={'api8':str,'operator':str},low_memory=False)
d['y']=np.log10(pd.to_numeric(d.first365_G,errors='coerce').where(lambda s:s>0))
d['spud_year']=pd.to_datetime(d.spud_dte,errors='coerce').dt.year
d['depth']=pd.to_numeric(d.max_md,errors='coerce'); d['elev']=pd.to_numeric(d.ground_elev,errors='coerce')
d['n_stim']=pd.to_numeric(d.max_tvd,errors='coerce')
d=d.dropna(subset=['lat','lon','y','spud_year']).reset_index(drop=True)
d['pad_true']=le.infer_pads(d.lat.to_numpy(),d.lon.to_numpy()).astype(str)
d['pad_size']=d.groupby('pad_true').pad_true.transform('size').values
F=['lat','lon','spud_year','depth','elev','n_stim']
rows=[]
for lo,hi,lab in [(1,1,'1'),(2,3,'2-3'),(4,5,'4-5'),(6,7,'6-7'),(8,11,'8-11'),(12,999,'12+')]:
    s=d[(d.pad_size>=lo)&(d.pad_size<=hi)]
    if len(s)>=250: rows+=fc.cellrows(s,F,'pad_true','Colorado',lab)
old=pd.read_csv(P.out('fig_data.csv'))
old=old[old.state!='Colorado']
pd.concat([old,pd.DataFrame(rows)],ignore_index=True).to_csv(P.out('fig_data.csv'),index=False)
print('appended Colorado to fig_data.csv')
