"""A worked example: run the paper's diagnostic on your own well table.

    python3 example_diagnostic.py            # on built-in synthetic wells, ~30 s
    python3 example_diagnostic.py <csv>      # on a CSV of your own

WHAT THIS IS FOR

    The paper's claim is a procedure rather than a number: score one model
    twice on the same table, changing only how the rows are assigned to folds.
    The gap between the two scores is the accuracy a random split reports and
    a grouped split does not reproduce. Everything else in this repository is
    that procedure applied to four state datasets. This file is the procedure
    in isolation, short enough to be read and adapted to another study.

    It requires nothing from `Data/`. The default run builds a synthetic
    table whose pads are known by construction: the wells are generated with a
    pad effect, so the gap reported is the gap that pad effect produces.

YOUR OWN DATA

    Pass a CSV with, at minimum:

        lat, lon     wellhead coordinates in decimal degrees
        y            the target, one row per well

    Every other numeric column is used as a feature. Give the file a `pad`
    column and it is used as the grouping; leave it out and the grouping is
    recovered from the coordinates by single-link clustering at 150 m, which
    is what the paper does where no register exists (§3).

READING THE OUTPUT

    Two R2 scores and their difference. A large positive difference means the
    random-split score is inflated: the model is being tested on wells whose
    pad-mates it was trained on. That is the finding the paper reports, and it
    is a property of the data, not of the learner -- §5 shows it for four
    states and §7 shows that operator, spud year and spatial blocks do not
    stand in for the pad.

    The synthetic table's pad component is deliberately strong, so the gap
    reported is around 1.1 R2, larger than the 0.39 the paper reports at its
    maximum. It demonstrates that the diagnostic responds to a pad effect of a
    size set by the fixture; it is not a result. The paper's figures come from
    the state tables, through `run_all.sh`.

    The per-feature audit that follows is recommendation 3 of §9: score each
    feature alone, both ways. A feature whose grouped score collapses to
    around zero while its random score is substantial is acting as a pad
    label, whatever it is named. Report it; do not delete it (§6.1 -- deleting
    the coordinates makes the inflation worse in all four states).
"""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, KFold

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    'le', os.path.join(HERE, 'leakage_experiment.py'))
le = importlib.util.module_from_spec(_spec)
sys.modules['le'] = le
_spec.loader.exec_module(le)

N_SPLITS = 5
PAD_RADIUS_M = 150.0


def synthetic_wells(n_pads=260, seed=0):
    """Wells on pads, with a per-pad component in the target.

    Each pad draws an offset and every well on it carries that offset. The
    features include pad-constant values of the kind a regulator's table
    contains -- an elevation, a formation top, a completion date -- alongside
    one genuinely per-well covariate.
    """
    rng = np.random.default_rng(seed)
    lat0, lon0 = 36.0, -103.5
    mlat = 1.0 / 111320.0
    mlon = 1.0 / (111320.0 * np.cos(np.radians(lat0)))

    rows = []
    for p in range(n_pads):
        k = int(rng.integers(1, 9))                  # wells on this pad
        cy = lat0 + rng.uniform(-0.35, 0.35)
        cx = lon0 + rng.uniform(-0.35, 0.35)
        theta = rng.uniform(0, np.pi)
        pad_effect = rng.normal(0, 0.45)             # the group component
        elev = rng.normal(1100, 120)                 # recorded once per pad
        top = rng.normal(2400, 180)                  # ditto
        spud = rng.integers(2012, 2023)              # ditto
        for w in range(k):
            off = (w - (k - 1) / 2) * 6.0            # 6 m wellhead spacing
            rows.append({
                'pad': p,
                'lat': cy + off * np.sin(theta) * mlat,
                'lon': cx + off * np.cos(theta) * mlon,
                'elevation': elev,
                'formation_top': top,
                'spud_year': float(spud),
                'lateral_m': rng.normal(2800, 600),  # genuinely per-well
                'y': 3.9 + pad_effect
                     + 0.00028 * rng.normal(2800, 600)
                     + rng.normal(0, 0.18),
            })
    return pd.DataFrame(rows)


def two_ways(d, feats, groups):
    """The whole diagnostic: one learner, two splitters, same rows."""
    rand = le.score(d, feats, KFold(N_SPLITS, shuffle=True, random_state=0),
                    None, 'random')
    grp = le.score(d, feats, GroupKFold(N_SPLITS), groups, 'grouped by pad')
    if rand is None or grp is None:
        raise SystemExit('too few wells for %d folds' % N_SPLITS)
    return rand, grp


def main(argv):
    if argv:
        path = argv[0]
        d = pd.read_csv(path, low_memory=False)
        print('%s: %d rows' % (path, len(d)))
        for need in ('lat', 'lon', 'y'):
            if need not in d.columns:
                raise SystemExit('the CSV needs a %r column' % need)
        d = d.dropna(subset=['lat', 'lon', 'y']).reset_index(drop=True)
    else:
        d = synthetic_wells()
        print('synthetic: %d wells on %d pads'
              % (len(d), d.pad.nunique()))

    if 'pad' in d.columns:
        groups = d['pad'].to_numpy()
        how = 'the pad column as given'
    else:
        groups = le.infer_pads(d.lat.to_numpy(), d.lon.to_numpy(),
                               radius_m=PAD_RADIUS_M)
        how = 'single-link clustering of wellheads at %g m' % PAD_RADIUS_M
    print('grouping: %s -- %d groups over %d wells (median occupancy %.1f)'
          % (how, len(set(np.asarray(groups).tolist())), len(d),
             float(pd.Series(groups).value_counts().median())))

    feats = [c for c in d.columns
             if c not in ('y', 'pad') and pd.api.types.is_numeric_dtype(d[c])]
    print('features: %s\n' % ', '.join(feats))

    rand, grp = two_ways(d, feats, groups)
    print('%-22s %8s %8s' % ('', 'R2', 'MAE'))
    for r in (rand, grp):
        print('%-22s %8.3f %8.3f' % (r['scheme'], r['r2'], r['mae']))
    gap = rand['r2'] - grp['r2']
    print('%-22s %8.3f' % ('inflation', gap))
    print('\n  The random split reports %.3f R2 that grouping by pad does not\n'
          '  reproduce. %s' % (gap, 'That is leakage.' if gap > 0.05 else
                               'On this table the effect is small.'))

    print('\nper-feature audit (recommendation 3 of section 9)')
    print('%-16s %8s %8s %8s   %s'
          % ('feature', 'random', 'grouped', 'gap', 'reading'))
    for f in feats:
        a, b = two_ways(d, [f], groups)
        g = a['r2'] - b['r2']
        # The reading is deliberately coarse and only three-valued. A feature
        # that predicts nothing on its own is not evidence either way -- it
        # cannot be shown to be a pad label by a test it fails under both
        # splits -- and calling it "partly pad-constant" on a gap of 0.06
        # between two near-zero scores would be reading noise.
        if a['r2'] < 0.15:
            note = 'no signal alone; this test says nothing about it'
        elif b['r2'] < 0.05:
            note = 'pad label'
        elif g < 0.05:
            note = 'per-well'
        else:
            note = 'partly pad-constant'
        print('%-16s %8.3f %8.3f %8.3f   %s'
              % (f, a['r2'], b['r2'], g, note))
    print('\nDo not delete the features named as pad labels: section 6.1 shows\n'
          'that removing the coordinates increases the inflation in all four\n'
          'states. Report the audit and group the folds correctly instead.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
