"""Rebuild the Ohio well table from the RBDMS Access database + quarterly xlsx.

Produces oh_well_summary.csv (all wells with 2020-2026 production) and
oh_analysis.csv (the subset whose first production is 2020 or later, so the
first four reported quarters really are the well's first four).

TWO STEPS
    1. Export three tables out of the Access files. On Linux:

         mdb-export Rbdmsd972.mdb tblLocational > loc.csv
         mdb-export Rbdmsd97.mdb  Well          > well.csv
         mdb-export Rbdmsd97.mdb  tblPadWells   > padwells.csv

       On Windows, run with --from-access instead and this script will pull the
       same three tables through pyodbc using the Microsoft Access driver
       (needs the 64-bit Access Database Engine redistributable installed).

    2. python oh_build.py

WHY tblPadWells MATTERS
    It is Ohio's published pad register: 4,620 rows linking 4,619 wells to 1,071
    pads. Together with Pennsylvania's well_pad_id it gives the paper two
    independent ground truths rather than one.

Needs pandas and openpyxl.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import glob
import os
import sys

import numpy as np
import pandas as pd

OH = P.OH_DIR
PROD = P.DATA
MDB1 = os.path.join(OH, 'Rbdmsd97.mdb')
MDB2 = os.path.join(OH, 'Rbdmsd972.mdb')

# The quarterly files rename two columns partway through the series.
RENAME = {'Quarter (1, 2, 3, 4, n/a)': 'Quarter', 'Days in Production': 'Days'}


def from_access():
    """Windows path: read the three tables straight out of the .mdb files."""
    import pyodbc
    drv = '{Microsoft Access Driver (*.mdb, *.accdb)}'
    for mdb, tables in ((MDB2, ['tblLocational']),
                        (MDB1, ['Well', 'tblPadWells'])):
        con = pyodbc.connect(r'DRIVER=%s;DBQ=%s;' % (drv, mdb))
        for t in tables:
            out = os.path.join(OH, {'tblLocational': 'loc.csv', 'Well': 'well.csv',
                                    'tblPadWells': 'padwells.csv'}[t])
            print('  %s -> %s' % (t, os.path.basename(out)))
            pd.read_sql('SELECT * FROM [%s]' % t, con).to_csv(out, index=False)
        con.close()


def load_locations():
    loc = pd.read_csv(os.path.join(OH, 'loc.csv'), dtype=str, low_memory=False,
                      usecols=['LOCATION_ID', 'WH_LAT83', 'WH_LONG83',
                               'WH_LAT', 'WH_LONG', 'ELEV_GR', 'SLANT'])
    loc['api14'] = loc.LOCATION_ID.str.strip().str.zfill(14)
    for c in ('WH_LAT83', 'WH_LONG83', 'WH_LAT', 'WH_LONG', 'ELEV_GR'):
        loc[c] = pd.to_numeric(loc[c], errors='coerce')
    # prefer NAD83, fall back to the NAD27 pair
    loc['lat'] = loc.WH_LAT83.where(loc.WH_LAT83.between(38, 42.5), loc.WH_LAT)
    loc['lon'] = loc.WH_LONG83.where(loc.WH_LONG83.between(-85, -80), loc.WH_LONG)
    return loc[['api14', 'lat', 'lon', 'ELEV_GR', 'SLANT']]


def load_wells():
    w = pd.read_csv(os.path.join(OH, 'well.csv'), dtype=str, low_memory=False,
                    usecols=['API_WELLNO', 'OPNO', 'DT_SPUD', 'DTD', 'TVD',
                             'WELL_NM'])
    w['api14'] = w.API_WELLNO.str.strip().str.zfill(14)
    return w.drop_duplicates('api14')


def load_pads():
    p = pd.read_csv(os.path.join(OH, 'padwells.csv'), dtype=str)
    p['api14'] = p.ApiWellNo.str.strip().str.zfill(14)
    return p.drop_duplicates('api14')[['api14', 'PadNumber']]


def load_quarterly():
    frames = []
    files = sorted(glob.glob(os.path.join(PROD, '*AllQtrs*.xlsx')))
    if not files:
        sys.exit('No *AllQtrs*.xlsx found in %s' % PROD)
    for f in files:
        x = pd.ExcelFile(f)
        df = x.parse(x.sheet_names[0], dtype={'API Number': str}).rename(columns=RENAME)
        df['api14'] = df['API Number'].astype(str).str.strip().str.zfill(14)
        df['yr'] = pd.to_numeric(df['Production Year'], errors='coerce')
        df['q'] = pd.to_numeric(df['Quarter'], errors='coerce')
        df['gas'] = pd.to_numeric(df['Gas (Mcf)'], errors='coerce')
        df['oil'] = pd.to_numeric(df['Oil (Bbls)'], errors='coerce')
        df['fp'] = pd.to_datetime(df['Date of First Production'], errors='coerce')
        frames.append(df[['api14', 'yr', 'q', 'gas', 'oil', 'fp']])
        print('  %-44s %6d rows' % (os.path.basename(f), len(df)))
    p = pd.concat(frames, ignore_index=True).dropna(subset=['yr', 'q'])
    p['yq'] = p.yr.astype(int) * 4 + (p.q.astype(int) - 1)

    # DE-DUPLICATION, and why it is spelled out.
    #
    # The sixteen spreadsheets are not disjoint: ODNR reissues quarters, so the
    # same (well, quarter) turns up in more than one file. This used to be
    # `sort_values('yq').drop_duplicates(['api14','yq'])`, which has two faults.
    # `sort_values` defaults to quicksort, which is NOT stable, so when two
    # files disagreed about a quarter's volume the surviving row was whichever
    # the sort happened to leave first -- not determined by the code, and not
    # necessarily reproducible between pandas versions. And sorting on `yq`
    # alone does nothing to order the duplicates against each other.
    #
    # Colorado turned out to have the same problem with real consequences
    # (§S2.4: 262,437 duplicated rows, inflating the target for 10% of wells),
    # which is why this one is no longer left to chance. The rule here: keep the
    # LAST file to report a quarter, files being read in sorted filename order,
    # and say how many were dropped.
    p['src'] = range(len(p))                       # read order, files sorted
    n0 = len(p)
    p = (p.sort_values(['api14', 'yq', 'src'], kind='stable')
           .drop_duplicates(['api14', 'yq'], keep='last')
           .drop(columns='src'))
    dropped = n0 - len(p)
    if dropped:
        print('  %d duplicate (well, quarter) rows dropped; the latest file '
              'reporting a quarter wins' % dropped)
    return p


def main():
    if '--from-access' in sys.argv:
        print('reading the Access tables ...')
        from_access()

    print('quarterly production:')
    p = load_quarterly()
    print('  %d rows, %d wells, quarters %d..%d'
          % (len(p), p.api14.nunique(), p.yq.min(), p.yq.max()))

    first_prod = p.groupby('api14').fp.min()
    first_seen = p.groupby('api14').yq.min()
    start = (first_prod.dt.year * 4 + (first_prod.dt.quarter - 1))
    start = start.fillna(first_seen)
    start = np.maximum(start, first_seen)    # never before the data begins
    p['start'] = p.api14.map(start)

    w4 = p[(p.yq >= p.start) & (p.yq < p.start + 4)]
    agg = w4.groupby('api14').agg(first4_gas=('gas', 'sum'),
                                  first4_oil=('oil', 'sum'),
                                  n_q=('yq', 'size'))
    cum = p.groupby('api14').agg(cum_gas=('gas', 'sum'),
                                 cum_oil=('oil', 'sum'),
                                 n_q_total=('yq', 'size'))
    d = agg.join(cum).reset_index()
    d['start_yq'] = d.api14.map(start)
    d['first_prod'] = d.api14.map(first_prod)
    d = (d.merge(load_locations(), on='api14', how='left')
           .merge(load_wells()[['api14', 'OPNO', 'DT_SPUD', 'DTD', 'TVD',
                                'WELL_NM']], on='api14', how='left')
           .merge(load_pads(), on='api14', how='left'))
    d['complete4'] = d.n_q == 4

    out = os.path.join(OH, 'oh_well_summary.csv')
    d.to_csv(out, index=False)
    geo = d.lat.between(38, 42.5) & d.lon.between(-85, -80)
    print('\nwrote %s' % out)
    print('  %d wells | %d with coordinates | %d with a published pad | %d with 4 quarters'
          % (len(d), int(geo.sum()), int(d.PadNumber.notna().sum()),
             int(d.complete4.sum())))

    # the clean subset: first production inside the quarterly series, so the
    # first four reported quarters really are the first four
    a = d[geo & d.complete4 & d.PadNumber.notna() & (d.first4_gas > 0)]
    a = a[a.first_prod.dt.year >= 2020]
    out2 = os.path.join(OH, 'oh_analysis.csv')
    a.to_csv(out2, index=False)
    sz = a.groupby('PadNumber').size()
    print('\nwrote %s' % out2)
    print('  %d wells on %d published pads, median %d wells/pad, max %d'
          % (len(a), a.PadNumber.nunique(), int(sz.median()), int(sz.max())))


if __name__ == '__main__':
    main()
