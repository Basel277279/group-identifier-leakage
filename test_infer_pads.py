"""Equivalence test for the grid-accelerated pad clustering.

WHAT IS BEING TESTED AND WHY

    `leakage_experiment.infer_pads` groups wells by single-link clustering
    within a radius. For speed it does not compare all pairs: it bins wells
    into a coarse grid and compares each well only with the nine cells around
    it. That is an optimisation, and an optimisation of a clustering is exactly
    the kind of code that fails silently -- it returns a partition either way,
    and a partition that is 2% wrong looks entirely normal downstream.

    An earlier implementation used the same cell size in degrees for latitude
    and longitude. A degree of longitude spans only cos(phi) of a
    degree of latitude in metres, so the longitude cells were too narrow by a
    factor of 1/cos(phi) -- about 1.24 at 36 deg N, the Permian -- and a
    plus/minus-one-cell search missed pairs that were genuinely inside the
    radius. Pads were split. Every downstream number was slightly wrong, and
    nothing announced it.

    This file is the test that would have caught it the day it was written.

WHAT IT CHECKS

    1. equivalence      the grid partition equals the brute-force O(n^2)
                        partition, exactly, on all four state datasets at
                        every radius from 10 m to 10 km
    2. regression       a synthetic case built to fail under the old
                        single-cell-size bug, so the bug cannot return
    3. synthetic        random clustered points at several latitudes,
                        including 60 deg N where the cosine correction is
                        largest
    4. edge cases       empty input, one well, coincident wells, wells
                        straddling the prime meridian and the equator
    5. invariants       single-link is transitive and order-independent:
                        shuffling the input permutes the labels and nothing
                        else

    The brute force uses the identical distance expression as the code under
    test (equirectangular, mid-latitude cosine). This test is about the grid
    search, not about the earth model: substituting haversine would test two
    things at once and tell you which neither.

USAGE

    python3 test_infer_pads.py                 # all of it, ~4 min
    python3 test_infer_pads.py --quick         # synthetic + edges only, ~5 s
    pytest test_infer_pads.py                  # same, as test functions

    The state datasets are found through p3_paths, under Data/ beside this
    file. Any state whose table is absent is skipped with a printed notice,
    not a failure, so the synthetic tests still run for someone who has the
    code but not the data.
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    'le', os.path.join(HERE, 'leakage_experiment.py'))
le = importlib.util.module_from_spec(_spec)
sys.modules['le'] = le
_spec.loader.exec_module(le)

sys.path.insert(0, HERE)
import p3_paths as P  # noqa: E402

R_EARTH_M = le.R_EARTH_M
RADII = [10, 25, 50, 100, 150, 200, 300, 500, 1000, 3000, 10000]

# Brute force is O(n^2). Above this many wells a state is deterministically
# subsampled, so the test stays a test rather than an overnight job. 6,000
# wells is 18 million pairs, a few seconds in numpy, and is far more than
# enough to expose a neighbourhood-search bug: the earlier longitude bug is
# visible on 200 wells.
BRUTE_MAX = 6000
SUBSAMPLE_SEED = 0


# ----------------------------------------------------------------- reference
def brute_force_pads(lat, lon, radius_m):
    """The definition, computed the slow honest way.

    Single-link clustering: join every pair within the radius, then take
    connected components. No grid, no neighbourhood, no assumptions.
    """
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    n = len(lat)
    if n == 0:
        return np.empty(0, dtype=np.int64)

    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    la = np.radians(lat)
    lo = np.radians(lon)

    # Blocked so memory stays bounded; the arithmetic is the same expression
    # infer_pads uses, elementwise.
    block = max(1, int(4e6 // max(n, 1)))
    for start in range(0, n, block):
        stop = min(start + block, n)
        rows = np.arange(start, stop)
        x = (lo[None, :] - lo[rows, None]) * np.cos(
            0.5 * (la[rows, None] + la[None, :]))
        y = la[None, :] - la[rows, None]
        d = R_EARTH_M * np.hypot(x, y)
        ii, jj = np.nonzero(d <= radius_m)
        for i_local, j in zip(ii, jj):
            i = rows[i_local]
            if j <= i:
                continue
            a, b = find(i), find(j)
            if a != b:
                parent[a] = b

    return canonical(np.array([find(i) for i in range(n)]))


def canonical(labels):
    """Relabel a partition by first appearance, so two partitions that are the
    same grouping under different label names compare equal."""
    labels = np.asarray(labels)
    seen, out = {}, np.empty(len(labels), dtype=np.int64)
    for i, v in enumerate(labels):
        v = int(v)
        if v not in seen:
            seen[v] = len(seen)
        out[i] = seen[v]
    return out


def same_partition(a, b):
    return np.array_equal(canonical(a), canonical(b))


def disagreement(lat, lon, a, b, radius_m):
    """A readable account of the first difference, for the failure message."""
    a, b = canonical(a), canonical(b)
    ga, gb = {}, {}
    for i, (x, y) in enumerate(zip(a, b)):
        ga.setdefault(int(x), []).append(i)
        gb.setdefault(int(y), []).append(i)
    lines = ['%d groups from the grid, %d from brute force' % (len(ga), len(gb))]
    for i in range(len(a)):
        if set(ga[int(a[i])]) != set(gb[int(b[i])]):
            ca, cb = sorted(ga[int(a[i])]), sorted(gb[int(b[i])])
            lines.append('first difference at well %d (%.6f, %.6f), r = %g m'
                         % (i, lat[i], lon[i], radius_m))
            lines.append('  grid group  %s' % ca[:8])
            lines.append('  brute group %s' % cb[:8])
            extra = sorted(set(cb) - set(ca))
            if extra:
                j = extra[0]
                d = separation_m(lat[i], lon[i], lat[j], lon[j])
                lines.append('  grid MISSED well %d at %.3f m (radius %g m)'
                             % (j, d, radius_m))
            break
    return '\n'.join(lines)


def separation_m(lat1, lon1, lat2, lon2):
    la, lb = np.radians(lat1), np.radians(lat2)
    x = (np.radians(lon2) - np.radians(lon1)) * np.cos(0.5 * (la + lb))
    return float(R_EARTH_M * np.hypot(x, lb - la))


# ------------------------------------------------------------------ fixtures
def synthetic_pads(n_pads=120, per_pad=(1, 8), lat0=36.0, lon0=-103.5,
                   spread_deg=0.35, spacing_m=6.0, seed=0):
    """Clustered points that look like pads: tight rows of wellheads,
    scattered across a few tens of kilometres."""
    rng = np.random.default_rng(seed)
    lat, lon = [], []
    mlat = 1.0 / 111320.0
    mlon = 1.0 / (111320.0 * np.cos(np.radians(lat0)))
    for _ in range(n_pads):
        k = int(rng.integers(per_pad[0], per_pad[1] + 1))
        cy = lat0 + rng.uniform(-spread_deg, spread_deg)
        cx = lon0 + rng.uniform(-spread_deg, spread_deg)
        theta = rng.uniform(0, np.pi)
        for w in range(k):
            off = (w - (k - 1) / 2) * spacing_m
            lat.append(cy + off * np.sin(theta) * mlat)
            lon.append(cx + off * np.cos(theta) * mlon)
    return np.array(lat), np.array(lon)


def longitude_bug_case(lat0=36.0, radius_m=150.0, lon_offset_deg=0.0,
                       n_filler=300, seed=0):
    """A pair the OLD code missed and the corrected code finds.

    Two wells separated almost entirely in longitude, at 0.97 of the radius --
    inside it, but far enough out that a grid whose longitude cells are
    cos(phi) too narrow can place them two cells apart and never compare them.

    `lon_offset_deg` slides the pair within the grid cell. This matters: the
    old bug only bites when the pair happens to straddle a cell boundary with
    a two-cell gap, which depends on where the pair sits relative to the grid
    origin. At 36 deg N the pair is 1.2 cells apart under the buggy grid, so
    it is missed for only about a fifth of offsets. A regression test fixed at
    one offset therefore passes against the buggy code at exactly the
    latitudes this study uses -- which is why the caller sweeps the offset
    instead of trusting one.
    """
    rng = np.random.default_rng(seed)
    coslat = np.cos(np.radians(lat0))
    d_deg = 0.97 * radius_m / (111320.0 * coslat)
    base = -100.0 + lon_offset_deg
    lat = [lat0, lat0]
    lon = [base, base + d_deg]
    # filler, deliberately far from the pair and from each other
    lat += list(lat0 + rng.uniform(0.05, 0.4, n_filler))
    lon += list(base + rng.uniform(0.05, 0.4, n_filler))
    return np.array(lat), np.array(lon)


def load_states():
    """Yield (name, lat, lon) for whichever state tables are reachable."""
    import pandas as pd
    out = []

    try:
        d, _ = le.load_pennsylvania()
        out.append(('Pennsylvania', d.lat.to_numpy(), d.lon.to_numpy()))
    except Exception as e:                                   # noqa: BLE001
        print('  skip Pennsylvania: %s' % e)

    try:
        d, _ = le.load_new_mexico()
        out.append(('New Mexico', d.lat.to_numpy(), d.lon.to_numpy()))
    except Exception as e:                                   # noqa: BLE001
        print('  skip New Mexico: %s' % e)

    for name, path in (('Ohio', P.oh('oh_analysis.csv')),
                       ('Colorado', P.co('co_analysis.csv'))):
        try:
            d = pd.read_csv(path, low_memory=False).dropna(subset=['lat', 'lon'])
            out.append((name, d.lat.to_numpy(), d.lon.to_numpy()))
        except Exception as e:                               # noqa: BLE001
            print('  skip %s: %s' % (name, e))

    return out


def subsample(lat, lon, limit=BRUTE_MAX, seed=SUBSAMPLE_SEED):
    if len(lat) <= limit:
        return lat, lon, False
    idx = np.random.default_rng(seed).choice(len(lat), limit, replace=False)
    idx.sort()
    return lat[idx], lon[idx], True


# --------------------------------------------------------------------- tests
def check(lat, lon, radius_m, label):
    got = le.infer_pads(lat, lon, radius_m=float(radius_m))
    want = brute_force_pads(lat, lon, float(radius_m))
    assert same_partition(got, want), (
        '%s at r = %g m\n%s' % (label, radius_m,
                                disagreement(lat, lon, got, want, radius_m)))
    return len(set(canonical(got).tolist()))


def test_regression_longitude_cell_size():
    """The pair the old grid missed must now be joined -- at every latitude
    this study touches AND at every position within the grid cell.

    This is the important test in the file. The offset sweep is not padding:
    with a single fixed offset the test passes against the buggy code at 31,
    36 and 41 deg N, which are precisely the latitudes of the four states, and
    would have certified the bug as fixed while it was still there. Sweeping
    33 offsets across one cell width catches it at all five latitudes.
    """
    radius_m = 150.0
    for lat0 in (31.0, 36.0, 41.0, 48.0, 60.0):
        cell_deg = radius_m / 111320.0          # the OLD, wrong, cell width
        for k in range(33):
            off = (k / 33.0) * cell_deg
            lat, lon = longitude_bug_case(lat0=lat0, radius_m=radius_m,
                                          lon_offset_deg=off)
            d = separation_m(lat[0], lon[0], lat[1], lon[1])
            assert d < radius_m, 'fixture is wrong: pair is %.1f m apart' % d
            got = le.infer_pads(lat, lon, radius_m=radius_m)
            assert got[0] == got[1], (
                'at %.0f deg N, cell offset %.3f, two wells %.1f m apart were'
                ' NOT joined at r = %g m -- the longitude cell size is wrong'
                ' again' % (lat0, k / 33.0, d, radius_m))
        # and the full partition, at one offset, against brute force
        lat, lon = longitude_bug_case(lat0=lat0, radius_m=radius_m)
        check(lat, lon, radius_m, 'longitude regression at %.0f N' % lat0)


def test_synthetic_all_radii():
    for lat0 in (28.0, 36.0, 41.0, 60.0, -5.0):
        lat, lon = synthetic_pads(lat0=lat0, lon0=-103.5, seed=int(abs(lat0)))
        for r in RADII:
            check(lat, lon, r, 'synthetic at %.0f deg' % lat0)


def test_edge_cases():
    # empty
    e = le.infer_pads(np.array([]), np.array([]), radius_m=150.0)
    assert len(e) == 0

    # one well
    one = le.infer_pads(np.array([36.0]), np.array([-103.0]), radius_m=150.0)
    assert len(one) == 1 and one[0] == 0

    # coincident wells: must be one group, at any radius
    lat = np.array([36.0, 36.0, 36.0, 40.0])
    lon = np.array([-103.0, -103.0, -103.0, -103.0])
    for r in (10, 150, 1000):
        g = le.infer_pads(lat, lon, radius_m=float(r))
        assert g[0] == g[1] == g[2], 'coincident wells split at r = %g' % r
        assert g[3] != g[0], 'wells 440 km apart joined at r = %g' % r
        check(lat, lon, r, 'coincident')

    # straddling the prime meridian and the equator -- not US data, but the
    # grid truncates toward zero, so these are the coordinates where an index
    # scheme is most likely to be wrong
    for lat0, lon0 in ((0.0, 0.0), (0.0, -0.0005), (51.5, 0.0)):
        lat, lon = synthetic_pads(n_pads=40, lat0=lat0, lon0=lon0,
                                  spread_deg=0.01, seed=7)
        for r in (10, 150, 1000):
            check(lat, lon, r, 'origin-straddling at (%.1f, %.1f)' % (lat0, lon0))


def test_order_independence():
    """Shuffling the wells must permute the labels and change nothing else."""
    lat, lon = synthetic_pads(seed=3)
    rng = np.random.default_rng(11)
    for r in (10, 150, 1000):
        base = canonical(le.infer_pads(lat, lon, radius_m=float(r)))
        perm = rng.permutation(len(lat))
        shuf = canonical(le.infer_pads(lat[perm], lon[perm], radius_m=float(r)))
        # same grouping, read back through the permutation
        back = np.empty_like(base)
        back[perm] = shuf
        assert same_partition(base, back), \
            'clustering depends on input order at r = %g m' % r


def test_transitivity():
    """A chain of wells each within r of the next is one pad, however long."""
    n, step_m = 40, 5.0
    lat = 36.0 + np.arange(n) * step_m / 111320.0
    lon = np.full(n, -103.0)
    g = le.infer_pads(lat, lon, radius_m=6.0)
    assert len(set(g.tolist())) == 1, 'single link is not transitive'
    g = le.infer_pads(lat, lon, radius_m=4.0)
    assert len(set(g.tolist())) == n, 'wells 5 m apart joined at r = 4 m'


def test_states_all_radii():
    states = load_states()
    if not states:
        print('  no state data reachable; synthetic tests still ran')
        return
    for name, lat, lon in states:
        lat, lon, cut = subsample(lat, lon)
        note = ' (subsampled to %d)' % len(lat) if cut else ''
        print('\n  %s -- %d wells%s' % (name, len(lat), note))
        for r in RADII:
            k = check(lat, lon, r, name)
            print('    r = %6g m   %5d groups   identical' % (r, k), flush=True)


# ---------------------------------------------------------------------- main
def main():
    quick = '--quick' in sys.argv
    tests = [test_regression_longitude_cell_size,
             test_synthetic_all_radii,
             test_edge_cases,
             test_order_independence,
             test_transitivity]
    if not quick:
        tests.append(test_states_all_radii)

    failed = 0
    for t in tests:
        name = t.__name__
        print('\n== %s ==' % name, flush=True)
        try:
            t()
        except AssertionError as e:
            failed += 1
            print('  FAIL\n%s' % e)
        else:
            print('  pass')
    print('\n%d/%d passed' % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
