"""Re-derive every table in the manuscript from the result files and fail on drift.

    python3 verify_manuscript.py          check everything
    python3 verify_manuscript.py -v       print every cell, not just the bad ones

WHY THIS EXISTS

    Four rounds of checking this paper found errors every time, and the reason
    was always the same shape: a number was written down in one place and
    recomputed in another, and the two drifted when the data was rebuilt. Six
    tables in the main text, seven in the supplement, an abstract, five
    captions and five highlights is roughly four hundred numbers. Manual
    re-checking at that scale is not reliable.

    So this does not check that the numbers are *right* -- nothing can do that
    -- it checks that they are the numbers the deposited result files actually
    contain. That is the mechanisable failure mode. What it cannot catch is
    listed at the bottom, so that the scope of the check is explicit.

HOW IT WORKS

    Each table in the markdown is parsed out by its caption, and a function
    below rebuilds the same table from the CSV that produced it. The two are
    compared cell by cell at the precision the manuscript prints. A cell the
    manuscript leaves as an em dash is skipped; a cell that exists in one and
    not the other is an error.

    Add a table by writing one function and one entry in CHECKS. Add a prose
    number by adding a line to PROSE.
"""
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

MAIN = P.out('P3_main.md')
SUP = P.out('P3_supplement.md')
ASM = P.out('assemble_manuscript.py')

T95_10 = 2.262157      # t(0.975, 9): ten seeds
# Student t, two-sided 95%, keyed by the number of seeds a result file holds.
# Keyed rather than hard-coded so that a file run at a different schedule is
# reported as unrecognised instead of being scored against the wrong quantile.
T95_OF = {6: 2.570582, 10: 2.262157, 20: 2.093024, 24: 2.068658, 30: 2.045230}
DASH = {'—', '-', '–', ''}


# ----------------------------------------------------------------- utilities

def read(path):
    return open(path, encoding='utf-8').read()


def table_after(text, caption_start):
    """The markdown table following a caption that begins with `caption_start`.

    Returns a list of rows, each a list of stripped cell strings, header and
    separator dropped.
    """
    i = text.find(caption_start)
    if i == -1:
        raise LookupError('caption not found: %r' % caption_start)
    rest = text[i:]
    rows, started = [], False
    for line in rest.splitlines():
        line = line.strip()
        if line.startswith('|'):
            started = True
            cells = [c.strip() for c in line.strip('|').split('|')]
            if set(''.join(cells)) <= set('-: '):
                continue                      # the separator row
            rows.append(cells)
        elif started:
            break
    if not rows:
        raise LookupError('no table under: %r' % caption_start)
    return rows[1:], rows[0]                  # body, header


def num(s):
    """A manuscript cell as a float, or None if it is a dash or unparseable."""
    s = s.strip().replace('−', '-').replace(',', '')
    s = re.sub(r'\s*\(.*\)\s*$', '', s)       # drop a parenthesised second value
    if s in DASH:
        return None
    m = re.match(r'^[+-]?\d*\.?\d+', s)
    return float(m.group(0)) if m else None


def paren(s):
    """The parenthesised value in a cell like `+0.192 (-0.002)`."""
    m = re.search(r'\(([^)]*)\)', s)
    return num(m.group(1)) if m else None


def dp(x):
    """Round like the manuscript prints: to the decimals the cell shows."""
    return x


class Report:
    def __init__(self, verbose):
        self.verbose, self.bad, self.n = verbose, [], 0

    def cell(self, where, said, got, places=3):
        """Compare one printed value against one recomputed value."""
        self.n += 1
        if said is None and got is None:
            return
        if said is None or got is None:
            self.bad.append('%s: manuscript %s, recomputed %s'
                            % (where, said, got))
            return
        if round(got, places) != round(said, places):
            self.bad.append('%s: manuscript %+.*f, recomputed %+.*f'
                            % (where, places, said, places, got))
        elif self.verbose:
            print('   ok  %-46s %+.*f' % (where, places, said))

    def note(self, where, ok, detail=''):
        self.n += 1
        if not ok:
            self.bad.append('%s: %s' % (where, detail))
        elif self.verbose:
            print('   ok  %-46s %s' % (where, detail))


# -------------------------------------------------------------- table checks

def check_table1(r, main):
    body, _ = table_after(main, 'Table 1. The four state datasets')
    row = {c[0].lower(): c[1:] for c in body}
    modelled = [int(x.replace(',', '')) for x in row['wells modelled']]
    import leakage_experiment as le
    pa, _ = le.load_pennsylvania()
    nm, _ = le.load_new_mexico()
    oh = pd.read_csv(P.oh('oh_analysis.csv'), low_memory=False)
    co = pd.read_csv(P.co('co_analysis.csv'), low_memory=False)
    oh = _tidy_ohio(oh)
    co = _tidy_colorado(co)
    got = [len(pa), len(oh), len(nm), len(co)]
    for name, said, g in zip(('Pennsylvania', 'Ohio', 'New Mexico', 'Colorado'),
                             modelled, got):
        r.note('Table 1 wells modelled, %s' % name, said == g,
               'manuscript %d, recomputed %d' % (said, g))
    m = re.search(r'Total: ([\d,]+) wells', main)
    r.note('Table 1 total', int(m.group(1).replace(',', '')) == sum(got),
           'manuscript %s, recomputed %d' % (m.group(1), sum(got)))


def _tidy_ohio(o):
    o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
    o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
    o['spud_year'] = pd.to_datetime(o.DT_SPUD, errors='coerce',
                                    format='mixed').dt.year.fillna(o.first_prod.dt.year)
    for a, b in (('depth', 'DTD'), ('elev', 'ELEV_GR')):
        o[a] = pd.to_numeric(o[b], errors='coerce')
    return (o.replace([np.inf, -np.inf], np.nan)
             .dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True))


def _tidy_colorado(c):
    c['y'] = np.log10(pd.to_numeric(c.first365_G, errors='coerce')
                      .where(lambda s: s > 0))
    c['spud_year'] = pd.to_datetime(c.spud_dte, errors='coerce').dt.year
    return (c.replace([np.inf, -np.inf], np.nan)
             .dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True))


def check_table2(r, main):
    """Occupancy gradient and placebo, from fig_data.csv's ten seeds."""
    body, head = table_after(main, 'Table 2. Validation inflation by pad occupancy')
    states = head[1:]
    d = pd.read_csv(P.out('fig_data.csv'))
    g = d.groupby(['state', 'bin']).agg(infl=('inflation', 'mean'),
                                        plac=('placebo_effect', 'mean'))
    for row in body:
        label = row[0].split('(')[0].strip().replace('–', '-')
        for st, cell in zip(states, row[1:]):
            key = (st, label)
            if cell.strip() in DASH:
                r.note('Table 2 %s %s' % (st, label), key not in g.index,
                       'manuscript shows a dash but fig_data.csv has the cell')
                continue
            if key not in g.index:
                r.bad.append('Table 2 %s %s: not in fig_data.csv' % (st, label))
                continue
            r.cell('Table 2 %s %s' % (st, label), num(cell), g.loc[key, 'infl'])
            r.cell('Table 2 %s %s placebo' % (st, label),
                   paren(cell), g.loc[key, 'plac'])


def check_table3(r, main):
    """Inflation by radius, from radius_fine.csv (1-20 m) and radius_sweep.csv."""
    body, head = table_after(main, 'Table 3.')
    states = head[1:]
    fine = pd.read_csv(P.out('radius_fine.csv'))
    swp = pd.read_csv(P.out('radius_sweep.csv'))
    got = {}
    for _, x in fine.iterrows():
        got[(x.state, int(x.radius_m))] = x.inflation
    for _, x in swp.iterrows():
        if x.grouping != 'random':
            got.setdefault((x.state, int(x.radius_m)), x.inflation)
    for row in body:
        rad = row[0].strip()
        m = re.match(r'([\d.]+)\s*(m|km)', rad)
        if not m:
            continue
        rm = int(float(m.group(1)) * (1000 if m.group(2) == 'km' else 1))
        for st, cell in zip(states, row[1:]):
            if cell.strip() in DASH:
                continue
            key = (st, rm)
            if key not in got:
                r.bad.append('Table 3 %s %s: no result row' % (st, rad))
                continue
            r.cell('Table 3 %s %s' % (st, rad), num(cell), got[key])


def check_table4(r, main):
    """Full vs no-coordinate inflation, from fig5_data.csv.

    Sourced from fig5_data.csv rather than mechanism_test.csv because only the
    former keeps the per-seed pairing the interval column needs.
    `check_mechanism_agreement` then holds the two files to each other.
    """
    body, head = table_after(main, 'Table 4. Inflation with the full feature set')
    f = pd.read_csv(P.out('fig5_data.csv')).set_index('state')
    cols = [h.strip().lower() for h in head]
    for row in body:
        st = row[0].strip()
        x = f.loc[st]
        r.cell('Table 4 %s full' % st, num(row[1]), x['full_infl'])
        r.cell('Table 4 %s no coords' % st, num(row[2]), x['nocoord_infl'])
        if 'change' in cols:
            i = cols.index('change')
            r.cell('Table 4 %s change' % st, num(row[i]), x['nocoord_change'])
            m = re.search(r'\u00b1\s*([\d.]+)', row[i])
            if m:
                r.cell('Table 4 %s change interval' % st, float(m.group(1)),
                       x['nocoord_change_ci'])
            else:
                r.bad.append('Table 4 %s: the change column has no interval' % st)
        if 'ratio' in cols:
            i = cols.index('ratio')
            r.cell('Table 4 %s ratio' % st,
                   num(row[i].replace('\u00d7', '')),
                   x['nocoord_infl'] / x['full_infl'], places=1)


def check_mechanism_agreement(r, main):
    """mechanism_test.csv and fig5_data.csv measure the same thing two ways.

    The manuscript cites both. They run different code over the same table, so
    agreement is a real check and disagreement means one of them is stale --
    which is exactly how Table 4 came to mix a 24-seed column with a six-seed
    one during the rebuild.
    """
    try:
        m = pd.read_csv(P.out('mechanism_test.csv'))
        f = pd.read_csv(P.out('fig5_data.csv')).set_index('state')
    except OSError as e:
        r.bad.append('mechanism agreement: %s' % e)
        return
    ref = {'Pennsylvania': 'pad register', 'Ohio': 'pad register',
           'New Mexico': '150 m', 'Colorado': '150 m'}
    for st, grouping in ref.items():
        sub = m[(m.state == st) & (m.grouping == grouping)]
        if sub.empty:
            r.bad.append('mechanism_test.csv has no %s / %s row' % (st, grouping))
            continue
        x = sub.iloc[0]
        tol = 3 * float(f.loc[st, 'full_infl_ci'])
        for a_, b_, lab in ((x['infl_full'], f.loc[st, 'full_infl'], 'full'),
                            (x['infl_no-coords'], f.loc[st, 'nocoord_infl'],
                             'no coords')):
            r.note('mechanism_test vs fig5_data, %s %s' % (st, lab),
                   abs(a_ - b_) <= tol,
                   'mechanism_test %+.4f, fig5_data %+.4f, tolerance %.4f -- '
                   'one of the two is stale' % (a_, b_, tol))


def check_table5(r, main):
    """Elevation alone, from covariate_audit.csv."""
    body, _ = table_after(main, 'Table 5. A model given ground elevation')
    c = pd.read_csv(P.out('covariate_audit.csv'))
    c = c[c.covariate == 'elevation'].set_index('state')
    for row in body:
        st = row[0].strip()
        r.cell('Table 5 %s random' % st, num(row[1]), c.loc[st, 'random'])
        r.cell('Table 5 %s pad' % st, num(row[2]), c.loc[st, 'pad'])
        r.cell('Table 5 %s inflation' % st, num(row[3]), c.loc[st, 'inflation'])
        r.cell('Table 5 %s pad-constant %%' % st, num(row[4]),
               100 * c.loc[st, 'pad_const'], places=1)


def check_table6(r, main):
    """Every scheme against the pad reference, from proxy_compare.csv."""
    body, head = table_after(main, 'Table 6. Every scheme measured against')
    states = head[1:]
    p = pd.read_csv(P.out('proxy_compare.csv'))
    alias = {'pad reference R²': ('pad (register)', 'pad (inferred)'),
             'random': ('random',), 'operator': ('operator',),
             'spud year': ('spud year',),
             'spatial block, 10 km': ('spatial 10 km',),
             'spatial block, 25 km': ('spatial 25 km',)}
    for row in body:
        label = row[0].strip()
        if label not in alias:
            continue
        for st, cell in zip(states, row[1:]):
            sub = p[(p.state == st) & (p.scheme.isin(alias[label]))]
            if sub.empty:
                r.bad.append('Table 6 %s %s: no result row' % (st, label))
                continue
            x = sub.iloc[0]
            val = x['mean'] if label.endswith('R²') else x['delta']
            r.cell('Table 6 %s %s' % (st, label), num(cell), val)
            m = re.search(r'\(([\d,]+)\)', cell)
            if m:
                r.note('Table 6 %s %s groups' % (st, label),
                       int(m.group(1).replace(',', '')) == int(x['groups']),
                       'manuscript %s, recomputed %d' % (m.group(1), x['groups']))


def check_placebo_claim(r, main):
    """§4.1's placebo paragraph, which is four claims and no table.

    This exists because the paragraph asserts things the tables do not: that
    no cell's interval excludes zero, which is the whole point of the control,
    and two extreme values quoted in prose. Both were stated from a six-seed
    run and silently went stale when the schedule changed, and neither is a
    table cell, so nothing else here would have caught them.
    """
    d = pd.read_csv(P.out('fig_data.csv'))
    cells, excludes = {}, []
    for (st, b), g in d.groupby(['state', 'bin']):
        v = g.placebo_effect.to_numpy(float)
        t = T95_OF.get(len(v))
        if t is None:
            r.bad.append('placebo: no t quantile for %d seeds' % len(v))
            return
        ci = t * v.std(ddof=1) / np.sqrt(len(v))
        cells[(st, b)] = v.mean()
        if not (v.mean() - ci <= 0 <= v.mean() + ci):
            excludes.append('%s %s' % (st, b))

    flat = re.sub(r'\s+', ' ', main)
    r.note('§4.1 every placebo interval covers zero', not excludes,
           'these do not: %s' % ', '.join(excludes))

    vals = pd.Series(cells)
    m = re.search(r'the largest\s+effect anywhere is ([−+-][\d.]+)', flat)
    if m:
        biggest = vals[vals.abs().idxmax()]
        r.cell('§4.1 largest placebo effect', num(m.group(1)), biggest)
    else:
        r.bad.append('§4.1: could not find the largest-placebo-effect claim')

    m = re.search(r'(\w+) of the eighteen are within ±([\d.]+)', flat)
    if m:
        words = {'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
                 'fifteen': 15, 'fourteen': 14}
        said_n = words.get(m.group(1).lower())
        bound = float(m.group(2))
        r.note('§4.1 "%s of the eighteen"' % m.group(1), said_n is not None,
               'unrecognised count word %r' % m.group(1))
        r.note('§4.1 eighteen cells exist', len(vals) == 18,
               'fig_data.csv has %d cells' % len(vals))
        if said_n is not None:
            got = int((vals.abs() <= bound + 5e-4).sum())
            r.note('§4.1 count within ±%.3f' % bound, got == said_n,
                   'manuscript %d, recomputed %d' % (said_n, got))
    else:
        r.bad.append('§4.1: could not find the "of the eighteen" claim')

    m = re.search(r'at\s+twenty-four seeds they are ([−+-][\d.]+), '
                  r'([−+-][\d.]+) and ([−+-][\d.]+)', flat)
    if m:
        low = vals.sort_values().head(3).to_numpy()
        for i, said in enumerate(m.groups()):
            r.cell('§4.1 three former outliers, %d' % (i + 1), num(said), low[i])
    else:
        r.bad.append('§4.1: could not find the three re-run placebo cells')


def check_floats_are_cited(r, main, sup, asm):
    """Every figure and table is referred to in the text, and the figures are
    numbered in the order they are first referred to.

    An uncited float is what a journal's technical check bounces a submission
    for, and it is invisible to every other check here: a figure can be
    produced, verified, captioned and deposited without one sentence ever
    pointing at it. Numbering order matters for the same reason -- Elsevier
    numbers figures by first citation, so a figure cited out of sequence is a
    renumbering request at proof stage.
    """
    body = re.sub(r'\s+', ' ', main)
    n_figs = len(re.findall(r'^Figure (\d+)\.', asm, re.M))
    r.note('five figure captions exist', n_figs == 5,
           'found %d in assemble_manuscript.py' % n_figs)

    # P3_main.md carries no captions -- they live in assemble_manuscript.py --
    # so every "Figure N" in it is a citation.
    for n in range(1, n_figs + 1):
        hits = len(re.findall(r'Figure %d\b' % n, body))
        r.note('Figure %d is cited in the text' % n, hits >= 1,
               'no sentence refers to it')

    order, seen = [], set()
    for m in re.finditer(r'Figure (\d+)\b', body):
        k = int(m.group(1))
        if k not in seen:
            seen.add(k)
            order.append(k)
    r.note('figures numbered in order of first citation',
           order == sorted(order), 'first cited in the order %s' % order)

    # A table's own caption is in the markdown, so it is discounted.
    n_tabs = len(re.findall(r'^Table (\d+)\.', main, re.M))
    for n in range(1, n_tabs + 1):
        hits = len(re.findall(r'Table %d\b' % n, body))
        caps = len(re.findall(r'Table %d\.' % n, body))
        r.note('Table %d is cited outside its caption' % n, hits - caps >= 1,
               'it appears only as its own caption')

    sflat = re.sub(r'\s+', ' ', sup)
    n_stabs = len(re.findall(r'^Table S(\d+)\.', sup, re.M))
    for n in range(1, n_stabs + 1):
        hits = (len(re.findall(r'Table S%d\b' % n, sflat))
                - len(re.findall(r'Table S%d\.' % n, sflat))
                + len(re.findall(r'Table S%d\b' % n, body)))
        r.note('Table S%d is cited' % n, hits >= 1,
               'it appears only as its own caption')


def check_captions(r, asm, main):
    """Every number printed in a figure caption, against its result file.

    The captions live in `assemble_manuscript.py`, not in the markdown, so the
    table checks never saw them. Figure 5's caption carried three pre-re-run
    values for a full day after every table had been corrected, which is what
    this exists to stop.
    """
    rs = pd.read_csv(P.out('radius_sweep.csv'))
    rf = pd.read_csv(P.out('radius_fine.csv'))
    pc = pd.read_csv(P.out('proxy_compare.csv'))
    rv = pd.read_csv(P.out('recovery_sweep.csv'))
    flat = re.sub(r'\s+', ' ', asm)

    def sweep(state, radius, col='inflation'):
        return float(rs[(rs.state == state) & (rs.radius_m == radius)][col].iloc[0])

    def placebo_at(state, radius):
        row = rs[(rs.state == state) & (rs.radius_m == radius)].iloc[0]
        rnd = rs[(rs.state == state) & (rs.grouping == 'random')].score.iloc[0]
        return float(rnd - row.placebo)

    # --- Figure 1: the two best distance-only recoveries
    m = re.search(r'F1 ([\d.]+) in Pennsylvania at (\d+) m and ([\d.]+) in '
                  r'Ohio at (\d+) m', flat)
    if m:
        for said_f1, said_r, st in ((m.group(1), m.group(2), 'Pennsylvania'),
                                    (m.group(3), m.group(4), 'Ohio')):
            sub = rv[(rv.state == st) & (rv.constraint == 'distance')]
            best = sub.loc[sub.f1.idxmax()]
            r.cell('Figure 1 %s best F1' % st, float(said_f1), float(best.f1),
                   places=len(said_f1.split('.')[1]))
            r.note('Figure 1 %s best radius' % st,
                   int(said_r) == int(best.radius_m),
                   'caption %s m, recomputed %d m' % (said_r, best.radius_m))
    else:
        r.bad.append('Figure 1 caption: could not find the two best F1 values')

    # --- Figure 3: the four off-axis values, the 20-300 m spans, the 10 km placebo
    m = re.search(r'Pennsylvania \+([\d.]+) and Ohio \+([\d.]+) at 10 km, '
                  r'New Mexico \+([\d.]+) at 3 km and \+([\d.]+) at 10 km', flat)
    if m:
        for said, (st, rad) in zip(m.groups(), (('Pennsylvania', 10000),
                                                ('Ohio', 10000),
                                                ('New Mexico', 3000),
                                                ('New Mexico', 10000))):
            r.cell('Figure 3 off-axis %s at %d m' % (st, rad),
                   float(said), sweep(st, rad))
    else:
        r.bad.append('Figure 3 caption: could not find the four off-axis values')

    # The 20-300 m spans moved out of the caption and into section 5 when the
    # captions were shortened; the check followed them rather than being
    # deleted.
    m = re.search(r'moves by ([\d.]+), Ohio by ([\d.]+) and New Mexico by '
                  r'([\d.]+)', re.sub(r'\s+', ' ', main))
    if m:
        for said, st in zip(m.groups(), ('Pennsylvania', 'Ohio', 'New Mexico')):
            band = rs[(rs.state == st) & rs.radius_m.between(20, 300)].inflation
            r.cell('§5 %s span over 20-300 m' % st, float(said),
                   float(band.max() - band.min()))
    else:
        r.bad.append('§5: could not find the 20-300 m spans')

    # The 10 km placebo values are no longer printed anywhere, so there are no
    # digits to match. What section 4.1 asserts is a SHAPE -- flat out to 1 km,
    # still inside a wider band at 3 km, breaking it at 10 km in all three
    # states -- and that is checked directly instead, which is the better test:
    # it fails if the placebo misbehaves, not merely if a number is mistyped.
    fm = re.search(r'stays within ±([\d.]+) out to 1 km, is still inside '
                   r'±([\d.]+) at 3 km, and breaks the band only at 10 km, '
                   r'in all three states at once, where groups average '
                   r'([\d,]+), ([\d,]+) and ([\d,]+) wells',
                   re.sub(r'\s+', ' ', main))
    if fm:
        near, mid = float(fm.group(1)), float(fm.group(2))
        states = ('Pennsylvania', 'Ohio', 'New Mexico')
        worst_near = max(abs(placebo_at(s, rr)) for s in states
                         for rr in (10, 25, 50, 100, 150, 300, 1000))
        r.note('§4.1 placebo within ±%.3f out to 1 km' % near,
               worst_near <= near + 5e-4,
               'largest is %.4f' % worst_near)
        worst_mid = max(abs(placebo_at(s, 3000)) for s in states)
        r.note('§4.1 placebo within ±%.3f at 3 km' % mid,
               worst_mid <= mid + 5e-4, 'largest is %.4f' % worst_mid)
        outside = [s for s in states if abs(placebo_at(s, 10000)) > mid]
        r.note('§4.1 placebo breaks the band at 10 km in all three',
               len(outside) == 3, 'it does so in %s' % (', '.join(outside) or 'none'))
        for said, st in zip(fm.group(3, 4, 5), states):
            row = rs[(rs.state == st) & (rs.radius_m == 10000)].mean_size.iloc[0]
            r.note('§4.1 mean group size at 10 km, %s' % st,
                   abs(float(said.replace(',', '')) - row) < 1,
                   'manuscript %s, recomputed %.1f' % (said, row))
    else:
        r.bad.append('§4.1: could not find the across-radii placebo sentence')

    # --- Figure 5: the three pad baselines and the off-axis operator value
    m = re.search(r'Pad-grouped baselines are R² (\d\.\d+), (\d\.\d+) and '
                  r'(\d\.\d+)', flat)
    if m:
        for said, st in zip(m.groups(), ('Pennsylvania', 'Ohio', 'New Mexico')):
            ref = pc[(pc.state == st) & pc.scheme.str.startswith('pad')]
            r.cell('Figure 5 pad baseline, %s' % st, float(said),
                   float(ref['mean'].iloc[0]))
    else:
        r.bad.append('Figure 5 caption: could not find the pad baselines')

    m = re.search(r"Pennsylvania's operator value of ([−+-][\d.]+) lies "
                  r'beyond the axis', flat)
    if m:
        op = pc[(pc.state == 'Pennsylvania') & (pc.scheme == 'operator')]
        r.cell('Figure 5 off-axis operator value', num(m.group(1)),
               float(op.delta.iloc[0]))
    else:
        r.bad.append('Figure 5 caption: could not find the off-axis operator value')

    # --- the seed schedule, named in two captions, must be the one the files hold
    seeds = pd.read_csv(P.out('fig_data.csv')).groupby(
        ['state', 'bin']).seed.nunique().max()
    words = {24: 'twenty-four', 20: 'twenty', 10: 'ten', 6: 'six', 30: 'thirty'}
    r.note('captions name the actual seed count',
           ('%s seeds' % words.get(int(seeds), seeds)) in flat,
           'result files hold %d seeds' % seeds)

    # --- section 5's singleton count, which comes from the fine sweep
    m = re.search(r'([\d,]+) for ([\d,]+) Pennsylvania wells',
                  re.sub(r'\s+', ' ', main))
    if m:
        row = rf[(rf.state == 'Pennsylvania') & (rf.radius_m == 3)]
        if row.empty:
            r.bad.append('radius_fine.csv has no Pennsylvania row at 3 m')
        else:
            r.note('§5 singleton clusters at 3 m',
                   int(m.group(1).replace(',', '')) == int(row.groups.iloc[0]),
                   'manuscript %s, recomputed %d' % (m.group(1), row.groups.iloc[0]))
            r.note('§5 Pennsylvania well count beside it',
                   int(m.group(2).replace(',', '')) == int(row.wells.iloc[0])
                   if 'wells' in rf.columns else True,
                   'manuscript %s' % m.group(2))
    else:
        r.bad.append('§5: could not find the singleton-cluster count')


def check_nm_rule_effect(r, sup):
    """§S2.3's before-and-after pair for New Mexico's completeness rule.

    A before-and-after is the easiest thing in the paper to leave stale,
    because the `before` can no longer be recomputed from the deposited table
    -- it belongs to a set the rule removed. `nm_rule_effect.py` therefore
    recomputes both arms on one schedule and this reads its file.
    """
    e = pd.read_csv(P.out('nm_rule_effect.csv'))
    e = e.set_index(['rule', 'measure']).value
    before, after = 'no completeness rule', 'twelve months required'
    flat = re.sub(r'\s+', ' ', sup)

    m = re.search(r'150 m radius from \+([\d.]+) to \+([\d.]+) and its 8\+ '
                  r'occupancy cell from \+([\d.]+) to \+([\d.]+)', flat)
    if m:
        for i, (rule, meas) in enumerate(((before, 'state inflation'),
                                          (after, 'state inflation'),
                                          (before, '8+ occupancy bin'),
                                          (after, '8+ occupancy bin'))):
            r.cell('§S2.3 %s, %s' % (meas, rule),
                   float(m.group(i + 1)), e.loc[(rule, meas)])
    else:
        r.bad.append('§S2.3: could not find the rule-effect before/after pair')

    m = re.search(r'from R² ([\d.]+) to ([\d.]+) in Table 6', flat)
    if m:
        for i, rule in enumerate((before, after)):
            r.cell('§S2.3 pad-grouped R2, %s' % rule, float(m.group(i + 1)),
                   e.loc[(rule, 'pad-grouped R2 (Table 6)')])
    else:
        r.bad.append('§S2.3: could not find the pad-grouped R2 pair')

    # The three after-figures must be the ones the tables report, which is what
    # establishes that the two arms differ in the completeness rule only.
    rs = pd.read_csv(P.out('radius_sweep.csv'))
    nm = rs[(rs.state == 'New Mexico') & (rs.radius_m == 150)].inflation.iloc[0]
    r.cell('§S2.3 after-figure matches Table 3',
           round(float(e.loc[(after, 'state inflation')]), 3), nm)
    fd = pd.read_csv(P.out('fig_data.csv'))
    b8 = fd[(fd.state == 'New Mexico') & (fd.bin == '8+')].inflation.mean()
    r.cell('§S2.3 after-figure matches Table 2',
           round(float(e.loc[(after, '8+ occupancy bin')]), 3), b8)
    pc = pd.read_csv(P.out('proxy_compare.csv'))
    pr = pc[(pc.state == 'New Mexico') & (pc.scheme == 'pad (inferred)')]
    r.cell('§S2.3 after-figure matches Table 6',
           round(float(e.loc[(after, 'pad-grouped R2 (Table 6)')]), 3),
           pr['mean'].iloc[0])


def check_oh_audit(r, main, sup):
    """§2's and §S2.5's figures for the one covariate the audit removed."""
    a = pd.read_csv(P.out('oh_feat_audit.csv'))
    a = a[a.bin == 'all'].set_index('features').inflation
    with_it, without = a.loc['with n_q_total'], a.loc['WITHOUT it']

    m = re.search(r"inflation from \+([\d.]+) to \+([\d.]+)",
                  re.sub(r'\s+', ' ', main))
    if m:
        r.cell('§2 Ohio audit, with the column', float(m.group(1)), with_it)
        r.cell('§2 Ohio audit, without it', float(m.group(2)), without)
    else:
        r.bad.append('§2: could not find the Ohio covariate-audit pair')

    m = re.search(r"removal moved Ohio's inflation by \+([\d.]+)",
                  re.sub(r'\s+', ' ', sup))
    if m:
        r.cell('§S2.5 size of the move', float(m.group(1)), without - with_it)
    else:
        r.bad.append('§S2.5: could not find the size of the move')

    # The audited feature set is the one every Ohio result uses, so the
    # `WITHOUT it` arm must reproduce the state inflation Table 4 prints.
    f5 = pd.read_csv(P.out('fig5_data.csv')).set_index('state')
    r.cell('Ohio audit agrees with Table 4', round(float(without), 3),
           f5.loc['Ohio', 'full_infl'])


def check_coord_verdicts(r, main, asm):
    """The coordinate-removal claim must match the verdict column, not a sign.

    The claim must be read from the verdict column. Reading it from the sign
    of a difference without its interval gives the wrong answer in two cases -- once as "three of four
    states" when New Mexico's point estimate was negative, and once as "all
    four" when it turned positive. Both were readings of noise. `fig5_data.csv`
    now carries a paired interval and a verdict per state, and the text has to
    agree with the verdict.
    """
    f = pd.read_csv(P.out('fig5_data.csv')).set_index('state')
    if 'nocoord_verdict' not in f.columns:
        r.bad.append('fig5_data.csv has no nocoord_verdict column: re-run '
                     'fig5_compute.py before trusting any "all four" claim')
        return
    worse = [st for st in f.index if f.loc[st, 'nocoord_verdict'] == 'worse']
    better = [st for st in f.index if f.loc[st, 'nocoord_verdict'] == 'better']
    unres = [st for st in f.index
             if f.loc[st, 'nocoord_verdict'] == 'indistinguishable']
    r.note('coordinate removal: no state improves', not better,
           'these improve: %s' % ', '.join(better))
    try:
        cover = read(P.out('P3_cover_letter.md'))
    except OSError:
        cover = ''
    for label, text in (('main text', main), ('front matter', asm),
                        ('cover letter', cover)):
        flat = re.sub(r'\s+', ' ', text)
        says_all = ('all four states' in flat) or ('in every state' in flat)
        r.note('%s: "all four states"' % label,
               (not says_all) or (len(worse) == 4),
               'text says all four, but %d of 4 are resolved worse '
               '(%d unresolved)' % (len(worse), len(unres)))
        r.note('%s: no stale "three of four"' % label,
               'three of four states' not in flat,
               'the text still says "three of four"')
    for st in f.index:
        r.note('fig5_data %s interval' % st,
               f.loc[st, 'nocoord_change_ci'] > 0,
               'the paired interval is zero-width, which cannot be right')


def check_tableS5(r, sup):
    """ICC against uniqueness, from covariate_audit.csv."""
    body, _ = table_after(sup, 'Table S5. The measure that failed')
    c = pd.read_csv(P.out('covariate_audit.csv'))
    c = c[c.covariate == 'elevation'].set_index('state')
    order = ['Pennsylvania', 'Ohio', 'New Mexico', 'Colorado']
    want = {'elevation pad-icc': 'pad_icc', 'elevation leak': 'inflation'}
    for row in body:
        key = row[0].strip().lower()
        if key in want:
            for st, cell in zip(order, row[1:]):
                r.cell('Table S5 %s %s' % (st, key), num(cell),
                       c.loc[st, want[key]])
        elif 'unique to one pad' in key:
            for st, cell in zip(order, row[1:]):
                r.cell('Table S5 %s uniqueness' % st, num(cell),
                       100 * c.loc[st, 'uniq_share'], places=1)


def check_tableS6(r, sup):
    """Placeholder zeros recoded, from zero_depth_check.csv."""
    body, _ = table_after(sup, 'Table S6. Recoding the placeholder zeros')
    z = pd.read_csv(P.out('zero_depth_check.csv'))
    for row in body:
        st = row[0].strip()
        g = z[z.state == st].set_index('treatment').inflation
        a, b = float(g['as published']), float(g['zeros recoded NaN'])
        r.cell('Table S6 %s as published' % st, num(row[1]), a, places=4)
        r.cell('Table S6 %s recoded' % st, num(row[2]), b, places=4)
        r.cell('Table S6 %s change' % st, num(row[3]), b - a, places=4)


def check_tableS7(r, sup):
    """Occupancy by era, from occupancy_trend.csv."""
    body, head = table_after(sup, 'Table S7. Mean occupancy of the pad')
    states = head[1:]
    o = pd.read_csv(P.out('occupancy_trend.csv')).set_index(['state', 'era'])
    for row in body:
        era = row[0].strip().replace('–', '-')
        for st, cell in zip(states, row[1:]):
            if cell.strip() in DASH:
                continue
            key = (st, era)
            if key not in o.index:
                r.bad.append('Table S7 %s %s: no result row' % (st, era))
                continue
            r.cell('Table S7 %s %s' % (st, era), num(cell),
                   o.loc[key, 'per_well_mean'], places=1)


def check_tableS2(r, sup):
    """Pad recovery by radius, from recovery_sweep.csv."""
    try:
        body, head = table_after(sup, 'Table S2.')
    except LookupError:
        return
    rec = pd.read_csv(P.out('recovery_sweep.csv'))
    rec = rec[rec.constraint == 'distance'].set_index(['state', 'radius_m'])
    cols = [h.strip().lower() for h in head]
    if 'radius' not in cols[0]:
        return
    for row in body:
        m = re.match(r'([\d.]+)', row[0].strip())
        if not m:
            continue
        rm = int(float(m.group(1)))
        for i, h in enumerate(cols[1:], start=1):
            for st in ('Pennsylvania', 'Ohio'):
                if not h.startswith(st.lower()[:4]):
                    continue
                if (st, rm) in rec.index and num(row[i]) is not None:
                    r.cell('Table S2 %s %s m' % (st, rm), num(row[i]),
                           rec.loc[(st, rm), 'f1'], places=3)


# --------------------------------------------------------------- prose numbers
# (regex over the text, value to compare, how to compute it)

def check_prose(r, main, sup, asm):
    d = pd.read_csv(P.out('fig_data.csv'))
    f5 = pd.read_csv(P.out('fig5_data.csv')).set_index('state')
    p = pd.read_csv(P.out('proxy_compare.csv'))
    cell = d.groupby(['state', 'bin']).inflation.mean()

    # Section 5's pooled inflations, one seed schedule, four states
    flat = re.sub(r'\s+', ' ', main)
    pat = (r'inflation is \+([\d.]+) (?:\u00b1 ([\d.]+) )?\(Pennsylvania\), '
           r'\+([\d.]+) (?:\u00b1 ([\d.]+) )?\(Ohio\), '
           r'\+([\d.]+) (?:\u00b1 ([\d.]+) )?\(New Mexico\) and '
           r'\+([\d.]+) (?:\u00b1 ([\d.]+) )?\(Colorado\)')
    m = re.search(pat, flat)
    if m:
        for i, st in enumerate(('Pennsylvania', 'Ohio', 'New Mexico', 'Colorado')):
            r.cell('§5 pooled %s' % st, float(m.group(2 * i + 1)),
                   f5.loc[st, 'full_infl'])
            ci = m.group(2 * i + 2)
            r.note('§5 pooled %s carries an interval' % st, ci is not None,
                   'the pooled figure is printed without one')
            if ci is not None:
                r.cell('§5 pooled %s interval' % st, float(ci),
                       f5.loc[st, 'full_infl_ci'])
    else:
        r.bad.append('§5: could not find the pooled-inflation sentence')

    # the four occupancy peaks, quoted in §5, the abstract and a highlight
    peaks = [cell.loc[st].max() for st in
             ('Pennsylvania', 'Ohio', 'New Mexico', 'Colorado')]
    for label, text in (('§5', main), ('abstract', asm)):
        m = re.search(r'\+?(\d\.\d+),\s*\+?(\d\.\d+),\s*\+?(\d\.\d+) '
                      r'and \+?(\d\.\d+)', re.sub(r'\s+', ' ', text))
        if m:
            for i, st in enumerate(('Pennsylvania', 'Ohio', 'New Mexico', 'Colorado')):
                r.cell('%s peak %s' % (label, st), float(m.group(i + 1)),
                       peaks[i], places=2)
        else:
            r.bad.append('%s: could not find the four occupancy peaks' % label)

    # "up to 0.NN" wherever it appears must be the largest cell anywhere
    for label, text in (('main', main), ('front matter', asm)):
        for m in re.finditer(r'up to (\d\.\d+)', text):
            r.cell('%s "up to %s"' % (label, m.group(1)), float(m.group(1)),
                   max(peaks), places=2)

    # "all four states" / "three of four" for the no-coordinate result
    worse = sum(1 for st in f5.index
                if f5.loc[st, 'nocoord_infl'] > f5.loc[st, 'full_infl'])
    for label, text in (('main', main), ('front matter', asm)):
        r.note('%s: no-coordinate wording' % label,
               'three of four states' not in text or worse == 3,
               'says "three of four" but %d of 4 states get worse' % worse)
        if worse == 4:
            r.note('%s: says "all four"' % label,
                   ('all four states' in text) or ('every state' in text)
                   or ('all four' in text),
                   'all four states worsen but the text does not say so')

    # "eight of twelve" cells err by more than random splitting
    n = 0
    for st, g in p.groupby('state'):
        rnd = abs(float(g[g.scheme == 'random'].delta.iloc[0]))
        for s in ('operator', 'spud year', 'spatial 10 km', 'spatial 25 km'):
            if abs(float(g[g.scheme == s].delta.iloc[0])) > rnd:
                n += 1
    words = {8: 'eight', 9: 'nine', 10: 'ten', 7: 'seven', 11: 'eleven'}
    r.note('§7 "%s of twelve"' % words.get(n, n),
           ('%s of twelve' % words.get(n, n)) in re.sub(r'\s+', ' ', main)
           or ('%s of the twelve' % words.get(n, n)) in re.sub(r'\s+', ' ', main),
           'recomputed %d of 12; the text does not say so' % n)

    # the manuscript must not still name a retired well count
    for stale in ('15,911', '31,634', '5,693', '10,841', '10,858 analysis'):
        for label, text in (('main', main), ('supplement', sup)):
            hits = text.count(stale)
            allowed = 0
            if stale in ('15,911', '5,693') and label == 'supplement':
                allowed = 3      # §S2.3 quotes the pre-rebuild figures on purpose
            if stale == '10,858' and label == 'supplement':
                allowed = 2
            r.note('%s: retired figure %s' % (label, stale), hits <= allowed,
                   'appears %d times, %d expected' % (hits, allowed))


# ------------------------------------------------------------------- driver

CHECKS = [
    ('Table 1', check_table1, 'main'),
    ('Table 2', check_table2, 'main'),
    ('§4.1 placebo paragraph', check_placebo_claim, 'main'),
    ('Table 3', check_table3, 'main'),
    ('Table 4', check_table4, 'main'),
    ('Table 4 vs mechanism_test', check_mechanism_agreement, 'main'),
    ('Table 5', check_table5, 'main'),
    ('Table 6', check_table6, 'main'),
    ('§S2.3 New Mexico completeness rule', check_nm_rule_effect, 'sup'),
    ('Table S2', check_tableS2, 'sup'),
    ('Table S5', check_tableS5, 'sup'),
    ('Table S6', check_tableS6, 'sup'),
    ('Table S7', check_tableS7, 'sup'),
]

LIMITS = """
WHAT THIS DOES NOT CHECK, and must not be trusted to
  * whether the result files themselves are right. It compares the manuscript
    to the CSVs; if an experiment is wrong, both agree and both are wrong.
  * the source data. Two defects found on 26 September -- New Mexico's missing
    first-year rule and Colorado's duplicated production filings -- lived below
    this layer entirely and were found by reading the raw regulator files.
  * prose that describes a number without printing it ("rises steeply",
    "the mildest", "saturates"). A handful of superlatives are checked in
    `check_prose`; the rest are not.
  * the supplement's Section S1, which quotes twenty other papers. Those can
    only be checked against the papers.
  * anything in the .docx build. `build_manuscript.sh` runs its own checks.
"""


NOT_IN_DEPOSIT = """
This script compares the MANUSCRIPT against the result files, and the
manuscript sources are deliberately not deposited -- the published article is
the article, and `make_deposit.py` records that exclusion in EXCLUDED. So there
is nothing here for it to check, and that is the expected state of the deposit,
not a fault in it.

Everything this script would verify is already verified against the same files
in `MANIFEST.sha256`: the result CSVs beside it are the ones the tables were
printed from. To run this check you need P3_main.md, P3_supplement.md and
assemble_manuscript.py from the authors' working copy.
"""


def main(argv):
    verbose = '-v' in argv
    absent = [os.path.basename(p) for p in (MAIN, SUP, ASM)
              if not os.path.exists(p)]
    if absent:
        # A replicator running run_all.sh in the deposit reached this with a
        # FileNotFoundError traceback at the final stage, which reads as a
        # broken deposit. It is not: say so and succeed.
        print('verify_manuscript.py: nothing to check -- %s not present'
              % ', '.join(absent))
        print(NOT_IN_DEPOSIT)
        return 0
    main_t, sup_t, asm_t = read(MAIN), read(SUP), read(ASM)
    r = Report(verbose)
    for name, fn, which in CHECKS:
        try:
            fn(r, {'main': main_t, 'sup': sup_t}[which])
        except LookupError as e:
            r.bad.append('%s: %s' % (name, e))
        except Exception as e:                        # noqa: BLE001
            r.bad.append('%s: check itself failed -- %s: %s'
                         % (name, type(e).__name__, e))
    try:
        check_floats_are_cited(r, main_t, sup_t, asm_t)
    except Exception as e:                            # noqa: BLE001
        r.bad.append('figure/table citations: check failed -- %s: %s'
                     % (type(e).__name__, e))
    try:
        check_captions(r, asm_t, main_t)
    except Exception as e:                            # noqa: BLE001
        r.bad.append('figure captions: check failed -- %s: %s'
                     % (type(e).__name__, e))
    try:
        check_oh_audit(r, main_t, sup_t)
    except Exception as e:                            # noqa: BLE001
        r.bad.append('Ohio covariate audit: check failed -- %s: %s'
                     % (type(e).__name__, e))
    try:
        check_coord_verdicts(r, main_t, asm_t)
    except Exception as e:                            # noqa: BLE001
        r.bad.append('coordinate verdicts: check failed -- %s: %s'
                     % (type(e).__name__, e))
    try:
        check_prose(r, main_t, sup_t, asm_t)
    except Exception as e:                            # noqa: BLE001
        r.bad.append('prose: check itself failed -- %s: %s' % (type(e).__name__, e))

    print('%d values compared' % r.n)
    if r.bad:
        print('\n%d DISAGREE with the result files:\n' % len(r.bad))
        for b in r.bad:
            print('  ' + b)
        print(LIMITS)
        return 1
    print('every table cell and checked prose figure matches the result files')
    print(LIMITS)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
