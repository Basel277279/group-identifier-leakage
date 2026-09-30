"""How the inferred clusters grow as the radius is widened.

§3.6 argues that the 150 m radius carried over from Pennsylvania and Ohio is
safe in New Mexico and Colorado, and the evidence is the shape of the cluster
structure: the count falls smoothly while the largest cluster holds, and only
past 150 m does one cluster start chaining across pads. Those numbers were
quoted from a working note whose own counts predated the grid correction of
§3.2. This script recomputes them, for every state and every radius, from the
deposited tables.

    python3 cluster_structure.py      -> cluster_structure.csv
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

import importlib.util
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
le = importlib.util.module_from_spec(spec)
sys.modules['le'] = le
spec.loader.exec_module(le)

RADII = [10, 25, 50, 100, 150, 200, 300, 500, 1000]


def states():
    pa, _ = le.load_pennsylvania()
    yield 'Pennsylvania', pa, pa.pad_true.astype(str)

    o = pd.read_csv(P.oh('oh_analysis.csv'), dtype={'PadNumber': str}, low_memory=False)
    o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
    o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
    o['spud_year'] = (pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed')
                      .dt.year.fillna(o.first_prod.dt.year))
    o = (o.replace([np.inf, -np.inf], np.nan)
          .dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True))
    yield 'Ohio', o, o.PadNumber.astype(str)

    n, _ = le.load_new_mexico()
    yield 'New Mexico', n, None

    c = pd.read_csv(P.co('co_analysis.csv'), low_memory=False)
    c['y'] = np.log10(pd.to_numeric(c.first365_G, errors='coerce').where(lambda s: s > 0))
    c['spud_year'] = pd.to_datetime(c.spud_dte, errors='coerce').dt.year
    c = c.dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True)
    yield 'Colorado', c, None


def row(state, radius, labels, n_wells):
    s = pd.Series(np.asarray(labels).astype(str))
    size = s.map(s.value_counts())
    return dict(state=state, radius_m=radius, wells=n_wells,
                clusters=int(s.nunique()),
                per_cluster=n_wells / s.nunique(),
                median_cluster=float(s.value_counts().median()),
                per_well_mean=float(size.mean()),
                per_well_median=float(size.median()),
                largest=int(size.max()))


def main():
    rows = []
    for name, d, register in states():
        lat, lon = d.lat.to_numpy(), d.lon.to_numpy()
        if register is not None:
            r = row(name, -1, register, len(d))
            r['radius_m'] = np.nan          # the register has no radius
            rows.append(r)
        for rad in RADII:
            rows.append(row(name, rad, le.infer_pads(lat, lon, radius_m=rad), len(d)))

    out = pd.DataFrame(rows)
    out.to_csv(P.out('cluster_structure.csv'), index=False)
    print(out.round(2).to_string(index=False))
    print('\nwrote cluster_structure.csv')


if __name__ == '__main__':
    main()
