"""Recompute §2.4's New Mexico provenance figures from the deposited table.

WHY THIS EXISTS
    §2.4 states how large the OCD extract is and how well it joins. Those
    numbers were measured during the build, from a 20 GB intermediate that is
    not deposited, so on the face of it a reader cannot check them. Most of
    them, it turns out, survive in `nm_well_summary.csv` itself: the row count
    is the well count, `n_prod_rows` sums to the production-record count, and
    `in_wellhistory` and the coordinates give the join rates. This script
    recovers them, so §2.4 rests on something a reader holds.

WHAT IT CANNOT RECOVER
    The amendment audit — 2,339,711 keys at (well, pool, month, product) grain
    in the first twelve months, of which 2,715 carried more than one filing and
    856 differed in value — was computed over individual production rows and
    cannot be recovered from a well-level summary. §2.4 and §10 say so.

    python3 nm_provenance.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

import pandas as pd

CLAIMS = [
    ('production records', 48254734),
    ('producing wells', 89406),
    ('joined to well history', 89405),
    ('with usable coordinates', 89397),
    ('horizontal wells', 17688),
]


def main():
    d = pd.read_csv(P.nmcsv('nm_well_summary.csv'), low_memory=False)
    lat = pd.to_numeric(d.lat, errors='coerce')
    lon = pd.to_numeric(d.lon, errors='coerce')

    got = {
        'production records': int(pd.to_numeric(d.n_prod_rows, errors='coerce').sum()),
        'producing wells': len(d),
        'joined to well history': int(d.in_wellhistory.astype(str)
                                      .isin(['True', 'true', '1']).sum()),
        'with usable coordinates': int((lat.between(24, 50) & lon.between(-125, -65)).sum()),
        'horizontal wells': int((d.directional_status == 'H').sum()),
    }

    ok = True
    for name, claimed in CLAIMS:
        hit = got[name] == claimed
        ok &= hit
        print('%-26s %12s  manuscript %12s  %s'
              % (name, format(got[name], ','), format(claimed, ','),
                 'ok' if hit else 'MISMATCH'))

    print('reporting period %s to %s' % (d.first_prod_ym.min(), d.last_prod_ym.max()))
    print()
    print('The amendment audit of §2.4 is not recoverable from this table: it '
          'counted filings at (well, pool, month, product) grain in the raw '
          'production records.')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
