"""How much of Ohio's multi-operator problem is an artefact of pad age?

§3 reports that the operator constraint splits real pads because a pad whose
wells changed hands carries more than one operator code, and §8.2 argues that
this hazard is invisible on a recent sample. Both rest on a pair of shares —
the multi-operator fraction over the full register against the fraction among
recent pads — which were quoted from a working note whose filter ("still
producing 2020-2026") does not match the wording either section used, and
which no deposited script computed. This computes them from
`oh_register.csv`, which is deposited.

    python3 operator_vintage.py      -> operator_vintage.csv
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

import pandas as pd

CUTOFFS = [2016, 2018, 2020, 2022]


def main():
    # PadNumber and OPNO are read as STRINGS, matching `recovery_sweep.py`.
    # Left to pandas they come back as int64 on this file, which happens to
    # group identically -- but a rebuilt register with a blank or a leading
    # zero would group differently in the two scripts and only one of them
    # would be right. Pinning the dtype is what keeps them the same register.
    r = pd.read_csv(P.oh('oh_register.csv'),
                    dtype={'PadNumber': str, 'OPNO': str}, low_memory=False)
    r['yr'] = pd.to_numeric(r.yr, errors='coerce')
    # A pad with any unfiled spud year cannot be called "spudded entirely from
    # YYYY": `min` skips NaN, so without this such a pad would be admitted on
    # the strength of the years it does have.
    per_pad = r.groupby('PadNumber').agg(operators=('OPNO', 'nunique'),
                                         wells=('api14', 'size'),
                                         first=('yr', 'min'),
                                         last=('yr', 'max'),
                                         no_year=('yr', lambda v: v.isna().any()))
    rows = [dict(sample='full register, all vintages', pads=len(per_pad),
                 multi=int((per_pad.operators > 1).sum()),
                 share=float((per_pad.operators > 1).mean()))]
    for c in CUTOFFS:
        s = per_pad[(per_pad['first'] >= c) & ~per_pad['no_year']]
        if len(s) < 50:
            continue
        rows.append(dict(sample='pads spudded entirely from %d' % c, pads=len(s),
                         multi=int((s.operators > 1).sum()),
                         share=float((s.operators > 1).mean())))

    out = pd.DataFrame(rows)
    out['share_pct'] = (100 * out.share).round(1)
    out.to_csv(P.out('operator_vintage.csv'), index=False)
    print(out[['sample', 'pads', 'multi', 'share_pct']].to_string(index=False))
    print()
    full = out.iloc[0]
    recent = out[out['sample'].str.endswith('2020')]
    if len(recent):
        recent = recent.iloc[0]
        print('full register %.1f%% multi-operator against %.1f%% for pads spudded '
              'entirely from 2020 — a factor of %.1f'
              % (full.share_pct, recent.share_pct, full.share / recent.share))
    print('wrote operator_vintage.csv')


if __name__ == '__main__':
    main()
