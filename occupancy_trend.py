"""Pad occupancy: overall, and how it has moved across spud eras.

TWO AVERAGES, AND WHY THE PAPER DISTINGUISHES THEM
    Wells per pad can be averaged over PADS or over WELLS, and the two differ
    by a factor of about two in these datasets. A validation split assigns
    *wells* to folds, so the occupancy that governs the leak is the one a
    typical well experiences — the well-weighted average — while the figure a
    dataset description usually quotes is the pad-weighted one, which is
    smaller and reassuring. §5.2 makes that distinction and this script
    supplies both numbers for it.

    Eras are cut on spud year and pads are counted WITHIN each era, so a pad
    drilled out across two eras contributes to both. The alternative — assign
    each pad to the era of its first well — measures something else: the final
    size of pads started in a period, which is not knowable at the time.

    python3 occupancy_trend.py      -> occupancy_trend.csv
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

ERAS = [(2008, 2012), (2013, 2017), (2018, 2021), (2022, 2026)]


def summarise(state, d, pad, source):
    d = d.assign(_pad=np.asarray(pad).astype(str))
    rows = []
    for lo, hi, label in [(0, 9999, 'all')] + [(a, b, '%d-%d' % (a, b)) for a, b in ERAS]:
        s = d[(d.spud_year >= lo) & (d.spud_year <= hi)]
        if len(s) < 100:
            continue
        size = s.groupby('_pad')._pad.transform('size')
        rows.append(dict(state=state, pad_source=source, era=label, wells=len(s),
                         pads=int(s._pad.nunique()),
                         per_pad=len(s) / s._pad.nunique(),
                         per_well_mean=float(size.mean()),
                         per_well_median=float(size.median()),
                         largest=int(size.max())))
    return rows


def main():
    rows = []

    pa, _ = le.load_pennsylvania()
    rows += summarise('Pennsylvania', pa, pa.pad_true.astype(str), 'register')

    o = pd.read_csv(P.oh('oh_analysis.csv'), dtype={'PadNumber': str}, low_memory=False)
    o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
    o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
    o['spud_year'] = (pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed')
                      .dt.year.fillna(o.first_prod.dt.year))
    o = (o.replace([np.inf, -np.inf], np.nan)
          .dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True))
    rows += summarise('Ohio', o, o.PadNumber.astype(str), 'register')

    n, _ = le.load_new_mexico()
    rows += summarise('New Mexico', n,
                      le.infer_pads(n.lat.to_numpy(), n.lon.to_numpy()), 'inferred 150 m')

    c = pd.read_csv(P.co('co_analysis.csv'), low_memory=False)
    c['y'] = np.log10(pd.to_numeric(c.first365_G, errors='coerce').where(lambda s: s > 0))
    c['spud_year'] = pd.to_datetime(c.spud_dte, errors='coerce').dt.year
    c = c.dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True)
    rows += summarise('Colorado', c,
                      le.infer_pads(c.lat.to_numpy(), c.lon.to_numpy()), 'inferred 150 m')

    out = pd.DataFrame(rows)
    out.to_csv(P.out('occupancy_trend.csv'), index=False)
    print(out.round(2).to_string(index=False))
    print('\nwrote occupancy_trend.csv')


if __name__ == '__main__':
    main()
