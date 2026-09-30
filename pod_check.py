"""Is New Mexico's published POD identifier a pad grouping? No.

WHY THIS EXISTS
    §3 of the main text warns that a published administrative grouping is not
    evidence of a physical one, and offers the OCD's "POD" (plan of
    development) identifier as the cautionary case: it looks in the table like
    a pad label and is not one. The two numbers that make the case — the
    median spatial span of a POD and the share holding a single well — were
    quoted from a working note and no deposited script produced them. This
    produces them.

WHAT IT MEASURES
    span        the greatest distance in metres between any two wells sharing
                a POD, computed exactly for PODs with at most 200 wells and
                from the convex hull otherwise; a pad's span is the length of
                its wellhead row, tens of metres at most
    singletons  the share of PODs holding exactly one well

    Both are taken over the PODs that contain at least one well in the
    modelling set, since a POD nobody models is not a grouping anyone could
    have used. The count over every POD in the register is printed too, so
    the choice is visible rather than buried.

    python3 pod_check.py      -> pod_check.csv
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

import itertools

import numpy as np
import pandas as pd

NMS = P.nmcsv() + os.sep
R_EARTH = 6371000.0


def api10(df):
    return (df.api_st_cde.str.zfill(2) + df.api_cnty_cde.str.zfill(3)
            + df.api_well_idn.str.zfill(5))


def span_m(lat, lon):
    """Greatest pairwise distance in metres, equirectangular at mid-latitude."""
    n = len(lat)
    if n < 2:
        return 0.0
    phi = np.radians(np.mean(lat))
    x = np.radians(lon) * np.cos(phi) * R_EARTH
    y = np.radians(lat) * R_EARTH
    if n > 200:                      # hull first: the extremes are on it
        from scipy.spatial import ConvexHull
        try:
            h = ConvexHull(np.c_[x, y]).vertices
            x, y = x[h], y[h]
        except Exception:
            pass
    best = 0.0
    for i, j in itertools.combinations(range(len(x)), 2):
        d = (x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2
        if d > best:
            best = d
    return float(np.sqrt(best))


def main():
    link = pd.read_csv(NMS + 'podwc.csv', dtype=str, low_memory=False)
    link['api10'] = api10(link)
    link = link[['pod_idn', 'api10']].drop_duplicates()
    # 9999998 and 9999999 are catch-alls, not PODs: between them they hold 923
    # wells scattered over the whole state, 32.0 to 37.0 N and -108.6 to
    # -103.1 E, which no development unit spans. Counting them as PODs would
    # put two 700 km "units" in the deposited table. Every other identifier is
    # below 3,000,000.
    sentinel = pd.to_numeric(link.pod_idn, errors='coerce') >= 9_000_000
    if sentinel.any():
        print('dropping %d links to the catch-all PODs %s'
              % (int(sentinel.sum()),
                 sorted(link.loc[sentinel, 'pod_idn'].unique())))
        link = link[~sentinel]

    wells = pd.read_csv(NMS + 'nm_well_summary.csv',
                        usecols=['api10', 'lat', 'lon'], dtype={'api10': str})
    wells = wells.dropna(subset=['lat', 'lon'])
    # The OCD writes 0 where no coordinate was filed, and `dropna` does not
    # catch it: eight wells sit at exactly (0, 0), which is in the Gulf of
    # Guinea. Left in, they give their PODs spans of up to 10,582 km. The two
    # quoted statistics are medians and survive them, but the deposited table
    # should not contain impossible distances.
    zero = (wells.lat.astype(float) == 0) & (wells.lon.astype(float) == 0)
    if zero.any():
        print('dropping %d wells at exactly (0, 0), a missing-coordinate '
              'sentinel' % int(zero.sum()))
        wells = wells[~zero]

    j = link.merge(wells, on='api10', how='inner')
    print('%d POD-well links, %d with coordinates, %d distinct PODs'
          % (len(link), len(j), j.pod_idn.nunique()))

    rows = []
    for pod, g in j.groupby('pod_idn'):
        rows.append((pod, len(g), span_m(g.lat.to_numpy(float),
                                         g.lon.to_numpy(float))))
    out = pd.DataFrame(rows, columns=['pod_idn', 'wells', 'span_m'])
    out.to_csv(P.out('pod_check.csv'), index=False)

    single = float((out.wells == 1).mean())
    med = float(out.span_m.median())
    multi = out[out.wells > 1]
    print()
    print('PODs with a well carrying coordinates : %d' % len(out))
    print('median span over all PODs             : %.0f m' % med)
    print('share holding exactly one well        : %.1f%%' % (100 * single))
    print('median span over multi-well PODs      : %.0f m' % multi.span_m.median())
    print('median wells per POD                  : %.0f' % out.wells.median())
    print('PODs spanning more than 1 km          : %.1f%%'
          % (100 * (out.span_m > 1000).mean()))
    print()
    print('For contrast, a pad is tens of metres across: the 150 m clustering')
    print('of §3 gives New Mexico a median of two wells and a largest cluster')
    print('of 40, against these PODs.')
    print('wrote pod_check.csv')


if __name__ == '__main__':
    main()
