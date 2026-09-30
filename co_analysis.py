"""Build co_analysis.csv, the Colorado modelling table, from co_well_summary.csv.

    python3 co_analysis.py

WHY THIS FILE EXISTS
    `co_build.py` writes `co_well_summary.csv`: one row per Colorado well that
    ever reported production, 66,930 of them. The modelling table is a subset
    of that with five derived columns, and until now the step that produced it
    lived nowhere -- twelve scripts read `co_analysis.csv` and nothing in the
    repository said how it was made. New Mexico, Ohio and Pennsylvania each
    have their selection in code; Colorado did not, so Colorado's sample was
    the one part of the study a reader could not audit. This is that step,
    written out.

THE SELECTION, and why each rule is there
    in_shapefile == 1        the well is in the ECMC well shapefile, which is
                             where its coordinates come from; without it there
                             is nothing to cluster on
    lat, lon present         same reason, belt and braces
    Deviation == Horizontal  horizontal wells only, matching the other three
                             states. This is the regulator's own
                             classification, read from the directional
                             bottomhole shapefile, not a proxy. An earlier
                             version of this study believed Colorado
                             published no directional flag and used
                             `max_md - max_tvd > 1000 ft` instead. That proxy
                             agrees with the flag on modern wells -- 97.2% of
                             the wells it selected are flagged Horizontal --
                             but is unreliable elsewhere. Correcting the
                             month counter would, under the proxy, have
                             admitted 6,827 further wells; only 34% of those
                             appear in the directional file at all and only
                             62% of those are horizontal. The flag is
                             authoritative and the proxy is retired.
    well_class not CBM, CO2  the study is of unconventional shale wells, and
                             the other three states are the Marcellus, the
                             Utica and the Permian. Coalbed methane is not
                             shale and a CO2 injector is not a producer, so
                             neither belongs in a sample the paper describes
                             as four shale plays. This rule used to be applied
                             by accident (see the note below) rather than
                             stated; it is stated now.
    n_months_in_window == 12 a complete first year of production, so the
                             target is comparable across wells

THE DERIVED COLUMNS
    md       max_md, the measured depth
    tvd      max_tvd, the true vertical depth
    lateral  md - tvd
    spud     spud_dte, kept under a shorter name
    fy       the calendar year of first_prod_ym

A NOTE ON `n_months_in_window`, AND WHY THE POPULATION IS NOW EXPLICIT
    `co_build.py` used to increment this once per production ROW, and Colorado
    files one row per well-month per formation, so a well producing from two
    formations for a full twelve months counted 24 and was silently dropped.
    It now counts distinct months.

    That accident was doing more work than anyone intended. Of the 7,389 wells
    the corrected counter admits, 51% are gas wells against 4% in the old
    sample, 534 are coalbed methane, 29 are CO2, four in ten are plugged and
    abandoned, and only 64% lie in the DJ Basin against 96% before. Their
    median first production year is 2010 against 2017. In other words the row
    counter was, by coincidence, selecting modern DJ Basin horizontal Niobrara
    oil wells -- a reasonable population, and the one the paper describes, but
    selected by a bug rather than by a rule.

    So the counter is fixed and the population is now stated: the well-class
    exclusion above keeps Colorado a sample of shale wells. Piceance and San
    Juan gas wells that meet the lateral test are kept, as tight-gas
    completions of the same kind, and the paper says so in section S2.4.

    The corrected counter also drops one well the old rule admitted, api8
    12348939, which filed twelve rows but only eleven distinct months in its
    window -- eleven months of gas reported as a full year.
"""
import os
import struct
import sys
import zipfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

SRC = os.path.join(P.CO_DIR, 'co_well_summary.csv')
OUT = os.path.join(P.CO_DIR, 'co_analysis.csv')

WINDOW_MONTHS = 12
BH_ZIP = 'DIRECTIONAL_BOTTOMHOLE_LOCATIONS_SHP.ZIP'
EXCLUDE_CLASS = ('CBM', 'CO2')   # coalbed methane and CO2 injectors


def deviation_table():
    """api8 -> the ECMC's directional classification, from the bottomhole
    shapefile's dBASE table. Values: Horizontal, Directional, Drifted,
    Vertical, High angle. Read directly out of the zip so the raw download is
    the input and nothing has to be unpacked by hand."""
    path = os.path.join(P.DATA, BH_ZIP)
    if not os.path.exists(path):
        return None
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith('.dbf'))
        raw = z.read(name)
    n_rec, hdr_len, rec_len = struct.unpack('<xxxxIHH20x', raw[:32])
    fields, o = [], 32
    while raw[o:o + 1] not in (b'\r', b''):
        fields.append((raw[o:o + 11].split(b'\x00')[0].decode('latin-1').strip(),
                       raw[o + 16]))
        o += 32
    out = {}
    pos = hdr_len
    for _ in range(n_rec):
        rec = raw[pos:pos + rec_len]
        pos += rec_len
        if not rec or rec[0:1] == b'*':
            continue
        off, row = 1, {}
        for nm, ln in fields:
            row[nm] = rec[off:off + ln].decode('latin-1').strip()
            off += ln
        api = row.get('API', '')[:8]
        if api and api not in out:
            out[api] = row.get('Deviation', '')
    return out


def main():
    if not os.path.exists(SRC):
        print('%s not found. Run co_build.py first; it needs the annual '
              'production files listed in SOURCES.md.' % SRC)
        return 1

    d = pd.read_csv(SRC, low_memory=False)
    n0 = len(d)
    print('%d wells in co_well_summary.csv' % n0)

    for c in ('lat', 'lon', 'max_md', 'max_tvd', 'n_months_in_window',
              'in_shapefile'):
        d[c] = pd.to_numeric(d[c], errors='coerce')

    d['md'] = d.max_md
    d['tvd'] = d.max_tvd
    d['lateral'] = d.md - d.tvd
    dev = deviation_table()
    if dev is None:
        print('%s not found; it is a raw input listed in SOURCES.md' % BH_ZIP)
        return 1
    d['deviation'] = d.api8.astype(str).str.zfill(8).map(dev)
    d['spud'] = d.spud_dte
    d['fy'] = pd.to_numeric(d.first_prod_ym.astype(str).str[:4], errors='coerce')

    # A coordinate sanity box, as `leakage_experiment.tidy` applies to
    # Pennsylvania and New Mexico. Colorado is loaded directly by seven scripts,
    # none of which applies one, so the guarantee belongs here where the table
    # is written rather than in each reader. On this vintage nothing is caught
    # -- the wells span 37.00 to 41.00 N and -109.05 to -102.36 E, all inside
    # Colorado -- but the (0, 0) placeholder that `pod_check.py` documents for
    # New Mexico would otherwise pass straight through and cluster eight wells
    # into one spurious pad in the Gulf of Guinea.
    IN_STATE = ((d.lat.between(36.0, 42.0)) & (d.lon.between(-110.0, -101.0)))

    steps = [
        ('in the well shapefile', d.in_shapefile == 1),
        ('coordinates present', d.lat.notna() & d.lon.notna()),
        ('coordinates inside Colorado', IN_STATE),
        ('flagged Horizontal', d.deviation == 'Horizontal'),
        ('not %s' % ', '.join(EXCLUDE_CLASS),
         ~d.well_class.isin(EXCLUDE_CLASS)),
        ('a full %d-month window' % WINDOW_MONTHS,
         d.n_months_in_window == WINDOW_MONTHS),
    ]
    keep = pd.Series(True, index=d.index)
    for label, rule in steps:
        before = int(keep.sum())
        keep &= rule.fillna(False)
        print('  %-26s %6d -> %6d' % (label, before, int(keep.sum())))

    d = d[keep].copy()
    d.to_csv(OUT, index=False)
    print('\nwrote %s  (%d wells of %d)' % (OUT, len(d), n0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
