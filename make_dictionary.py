"""Build DATA_DICTIONARY.md for the five tables the experiments read.

    python3 make_dictionary.py > DATA_DICTIONARY.md

WHICH TABLES, AND WHY NOT ALL TEN
    The deposit ships ten derived tables; this documents the five the
    experiments fit models on. The other five are inputs to those five, or
    checks on them, and are deposited so the derivation can be followed rather
    than to be read directly:

        Colorado/co_well_summary.csv    every producing Colorado well;
                                        `co_analysis.py` selects co_analysis.csv
                                        out of it
        Ohio/oh_well_summary.csv        the same relation for Ohio
        NewMexico/csv/wellhistory.csv   the OCD well-history table; Sec. 6 joins
                                        `elev_gl_num` from it for Tables 4 and 5
        NewMexico/csv/pod.csv, podwc.csv  the OCD "POD" register, used only by
                                        `pod_check.py` for Sec. 3's negative result

    They carry the agencies' own column names and the agencies' own meanings;
    `SOURCES.md` gives their provenance and the OCD data dictionary shipped with
    the download defines their fields.

WHAT IS MACHINE-MEASURED AND WHAT IS NOT
    The row counts, column order, types, null shares and ranges below are read
    off the files every time this script runs, so they cannot drift from the
    data. The *meaning* of each column — its source field, its units, whether
    it is the agency's value or ours — is written by hand in COLUMNS and has to
    be maintained here. A dictionary whose statistics are stale is worse than
    none; a dictionary whose prose is stale is merely unhelpful, so the split
    is deliberate.

WHY IT MATTERS WHOSE COLUMN IT IS
    Every deposited table is a *derived join*, not a verbatim agency file. A
    reader checking the pad-recovery result needs to know which columns came
    from the regulator untouched and which were computed here, because only
    the second kind can carry processing errors. Each column is therefore
    tagged:

        agency    copied from the source record, unchanged
        derived   computed by one of the build scripts
        key       an identifier used to join the sources together

USED / CARRIED
    A column is marked **used** when a script in this project reads it, and
    *carried* when it is present in the table but not read. Carried columns
    are kept because they cost nothing and a reader may want them; they are
    flagged so nobody assumes a column is part of the analysis because it
    exists.

"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P

# column kinds, used by TABLES below and by COLUMNS further down
A, D, K = 'agency', 'derived', 'key'

# --------------------------------------------------------------- the tables
TABLES = [
    dict(
        key='pa', title='Pennsylvania — `Data/Pennsylvania/P2_wells_with_logs.csv`',
        path=P.pa('P2_wells_with_logs.csv'),
        agency='Pennsylvania Department of Environmental Protection',
        note='Compiled for the companion study of wellhead-to-bottomhole '
             'displacement and reused here unchanged; this paper reads nine of '
             'its 67 columns. The pad identifier is the agency\'s own. Rows '
             'are wells; 2,499 of them carry a pad identifier, over 1,044 '
             'registered pads, and 2,464 of those pass the production and '
             'covariate filters and enter the analysis, on 1,014 pads.',
        used=['well_pad_id', 'lat_index', 'lon_index', 'gas_first365_mcf',
              'spud_date', 'operator_permit', 'total_depth_ft', 'elevation_ft',
              'n_stimulations', 'api10'],
        # The 51 columns this paper does not read belong to the companion
        # study, which documents them. Saying so once is more use than
        # repeating "not read by this project" fifty-one times.
        default=(A, '—', 'Companion-study column; documented in that study\'s '
                 'deposit, not read here.'),
    ),
    dict(
        key='oh', title='Ohio, modelling set — `Data/Ohio/oh_analysis.csv`',
        path=P.oh('oh_analysis.csv'),
        agency='Ohio Department of Natural Resources (RBDMS + quarterly production)',
        note='Built by `oh_build.py` from `tblLocational`, `Well`, '
             '`tblPadWells` and the quarterly `*AllQtrs*.xlsx` files. One row '
             'per well with a complete first four reported quarters.',
        used=['PadNumber', 'first4_gas', 'DT_SPUD', 'first_prod', 'DTD',
              'ELEV_GR', 'TVD', 'lat', 'lon', 'api14', 'OPNO'],
    ),
    dict(
        key='ohr', title='Ohio, full pad register — `Data/Ohio/oh_register.csv`',
        path=P.oh('oh_register.csv'),
        agency='Ohio Department of Natural Resources (RBDMS)',
        note='The complete published register — every vintage, not only wells '
             'still producing — reduced to the six columns the pad-recovery '
             'test needs. Built once by `recovery_sweep.py` from the three '
             'RBDMS exports (245 MB together) and reused; delete it to force a '
             'rebuild. Used for §3 only; it carries no production.',
        used=['api14', 'PadNumber', 'lat', 'lon', 'OPNO', 'yr'],
    ),
    dict(
        key='nm', title='New Mexico — `Data/NewMexico/csv/nm_well_summary.csv`',
        path=P.nmcsv('nm_well_summary.csv'),
        agency='New Mexico Oil Conservation Division',
        note='Built by `nm_build.py` from 48,254,734 production records in '
             '`wcproduction` joined to `wellhistory`. One row per producing '
             'well, all vintages and orientations; the analysis takes the '
             'horizontal wells spudded from 2010 with a positive first-365-day '
             'gas volume. Ground elevation is **not** in this table — §6 reads '
             '`elev_gl_num` from `wellhistory.csv` directly.',
        used=['api10', 'lat', 'lon', 'spud_dte', 'directional_status',
              'first365_G', 'md', 'tvd', 'n_pools'],
    ),
    dict(
        key='co', title='Colorado — `Data/Colorado/co_analysis.csv`',
        path=P.co('co_analysis.csv'),
        agency='Colorado Energy and Carbon Management Commission',
        note='Built by `co_build.py` from `WELLS_SHP` joined to the annual '
             '`prod_reports` series 2010–2025 and `monthly_prod.csv`. One row '
             'per horizontal well with twelve reported months.',
        used=['lat', 'lon', 'first365_G', 'spud_dte', 'max_md', 'max_tvd',
              'ground_elev'],
    ),
]

# ------------------------------------------------- hand-written column notes
# column -> (kind, units, meaning). Kinds: agency | derived | key
COLUMNS = {
    # ---- shared names, any table
    'lat': (A, 'degrees, WGS84', 'Wellhead latitude as published.'),
    'lon': (A, 'degrees, WGS84', 'Wellhead longitude as published; negative west.'),
    'api10': (K, '—', 'Ten-digit API well number, zero-padded.'),
    'api14': (K, '—', 'Fourteen-digit API well number, zero-padded.'),
    'api8': (K, '—', 'Eight-digit Colorado API (county + sequence).'),
    'operator': (A, '—', 'Operator of record at extraction.'),
    'well_name': (A, '—', 'Operator\'s well name.'),

    # ---- Pennsylvania
    'well_pad_id': (A, '—', '**The agency\'s pad identifier.** Ground truth for §3.'),
    'well_pad': (A, '—', 'Agency pad name.'),
    'lat_index': (A, 'degrees', 'Wellhead latitude; the coordinate used here.'),
    'lon_index': (A, 'degrees', 'Wellhead longitude; the coordinate used here.'),
    'lat_inv': (A, 'degrees', 'Latitude from the inventory record; carried for comparison.'),
    'lon_inv': (A, 'degrees', 'Longitude from the inventory record; carried for comparison.'),
    'gas_first365_mcf': (D, 'Mcf', '**Target.** Gas over the first 365 days of production.'),
    'spud_date': (A, 'date', 'Date drilling began.'),
    'operator_permit': (A, '—', 'Operator named on the permit; used for the operator grouping in §7.'),
    'total_depth_ft': (A, 'ft', 'Total measured depth.'),
    'elevation_ft': (A, 'ft', '**Ground elevation.** The pad-label covariate of §6.'),
    'n_stimulations': (A, 'count', 'Stimulation records for the well.'),
    'coord_diff_m': (D, 'm', 'Distance between the two published coordinate pairs.'),
    'analysis_ready': (D, 'bool', 'Companion-study flag; not used here.'),

    # ---- Ohio
    'PadNumber': (A, '—', '**The agency\'s pad identifier** (`tblPadWells`). Ground truth for §3.'),
    'first4_gas': (D, 'Mcf', '**Target.** Gas over the first four reported quarters.'),
    'first4_oil': (D, 'bbl', 'Oil over the same four quarters.'),
    'n_q': (D, 'count', 'Quarters contributing to `first4_gas`.'),
    'n_q_total': (D, 'count', '**Excluded from every model, deliberately.** Quarters '
                  'the well has reported, which is downstream of the outcome: it '
                  'correlates +0.26 with the target because a well that produces '
                  'more is reported for longer. See §2.'),
    'cum_gas': (D, 'Mcf', 'Cumulative gas to the extraction date.'),
    'cum_oil': (D, 'bbl', 'Cumulative oil to the extraction date.'),
    'start_yq': (D, '—', 'First reported year-quarter.'),
    'first_prod': (D, 'date', 'First production date; fills a missing spud year.'),
    'ELEV_GR': (A, 'ft', '**Ground elevation.** Surveyed once per surface location in '
                'Ohio, which is why §6 finds it identical within 87% of pads.'),
    'SLANT': (A, '—', 'Wellbore orientation code; used when filtering to horizontals.'),
    'OPNO': (A, '—', 'Operator number; the operator grouping in §7.'),
    'DT_SPUD': (A, 'date', 'Spud date.'),
    'DTD': (A, 'ft', 'Total measured depth.'),
    'TVD': (A, 'ft', 'True vertical depth.'),
    'WELL_NM': (A, '—', 'Well name.'),
    'complete4': (D, 'bool', 'Whether four consecutive quarters were reported.'),
    'yr': (D, 'year', 'Spud year, parsed from `DT_SPUD`.'),

    # ---- New Mexico
    'spud_dte': (A, 'date', 'Spud date.'),
    'directional_status': (A, '—', '`H` marks a horizontal well; the analysis filter.'),
    'well_typ_cde': (A, '—', 'Well type code.'),
    'tvd': (A, 'ft', 'True vertical depth.'),
    'md': (A, 'ft', 'Measured depth.'),
    'first_prod_ym': (D, 'YYYYMM', 'First reporting month.'),
    'last_prod_ym': (D, 'YYYYMM', 'Last reporting month.'),
    'months_span': (D, 'count', 'Months between first and last report.'),
    'n_pools': (D, 'count', 'Distinct pools the well reports into.'),
    'n_prod_rows': (D, 'count', 'Production records collapsed into this row.'),
    'in_wellhistory': (D, 'bool', 'Whether the well joined to `wellhistory`.'),
    'first365_G': (D, 'Mcf', '**Target.** Gas over the first 365 days.'),
    'first365_O': (D, 'bbl', 'Oil over the first 365 days.'),
    'first365_W': (D, 'bbl', 'Water over the first 365 days.'),
    'first365_C': (D, 'bbl', 'Condensate over the first 365 days.'),
    'cum_G': (D, 'Mcf', 'Cumulative gas, all filings.'),
    'cum_O': (D, 'bbl', 'Cumulative oil, all filings.'),
    'cum_W': (D, 'bbl', 'Cumulative water, all filings.'),
    'cum_C': (D, 'bbl', 'Cumulative condensate, all filings.'),
    'cumNoAmend_G': (D, 'Mcf', 'Cumulative gas excluding rows flagged `amend_ind = Y`. '
                     'Carried as evidence: excluding them discards about a third of '
                     'reported volume, which is why the analysis does not (§2).'),
    'cumNoAmend_O': (D, 'bbl', 'As above, oil.'),
    'cumNoAmend_W': (D, 'bbl', 'As above, water.'),
    'cumNoAmend_C': (D, 'bbl', 'As above, condensate.'),

    # ---- Colorado
    'operator_name': (A, '—', 'Operator name.'),
    'loc_qual': (A, '—', '**Location quality.** `ACTUAL LatLong` against planned '
                 'footages — a published, per-well measure of the wellhead-position '
                 'uncertainty the clustering depends on (§2).'),
    'field': (A, '—', 'Field name.'),
    'well_class': (A, '—', 'Well class.'),
    'status': (A, '—', 'Well status.'),
    'ground_elev': (A, 'ft', '**Ground elevation.** Recorded per well in Colorado, '
                    'not per location — hence constant within only 28% of '
                    'multi-well pads, against 87% in Ohio (§6, '
                    '`covariate_audit.csv`).'),
    'max_md': (A, 'ft', 'Maximum measured depth.'),
    'max_tvd': (A, 'ft', 'Maximum true vertical depth.'),
    'n_rows': (D, 'count', 'Production records collapsed into this row.'),
    'n_months_in_window': (D, 'count', 'Reported months inside the first-365-day window.'),
    'in_shapefile': (D, 'bool', 'Whether the well joined to `WELLS_SHP`.'),
    'lateral': (D, 'ft', '`max_md − max_tvd`; the horizontal filter uses > 1000 ft.'),
    'spud': (D, 'date', 'Parsed spud date.'),
    'fy': (D, 'year', 'First production year.'),
}

DEFAULT = (A, '—', 'Carried from the source record; not read by this project.')

# ------------------------------------------------------------ result tables
# The deposit ships eighteen result CSVs and, until this section existed, not
# one of them had a column description anywhere: `DATA_DICTIONARY.md` covered
# only the five INPUT tables, and the README named the six that feed figures.
# A reader opening `fig_data.csv` had to infer from the code that `pad` is the
# grouped score and that `placebo_effect` is a control rather than a result.
#
# Columns shared by most of these files are described once, here, and named
# per file only where a file uses one differently.
SHARED = {
    'state': 'Pennsylvania, Ohio, New Mexico or Colorado.',
    'seed': 'Seed index, 0-based. Each seed is one draw of the split schedule '
            'and is a mean over five 80/20 folds.',
    'wells': 'Wells scored in this row.',
    'random': 'R² under a random split of the wells (`ShuffleSplit`).',
    'pad': 'R² under a pad-grouped split (`GroupShuffleSplit`): no pad has '
           'wells on both sides.',
    'placebo': 'R² under the placebo grouping — groups carrying the real pads\' '
               'size distribution with membership assigned at random. The '
               'control, not a result.',
    'inflation': 'Validation inflation, `random − pad`. Positive means the '
                 'random split reports an accuracy the grouped split does not '
                 'reproduce.',
    'placebo_effect': '`random − placebo`. Near zero is the intended outcome: '
                      'it says the loss under grouping is caused by pad '
                      'membership and not by grouped validation being harder.',
    'radius_m': 'Single-link clustering radius in metres. `-1` marks the '
                'published pad register, which has no radius.',
    'groups': 'Number of groups the scheme forms.',
    'mean_size': 'Mean wells per group, averaged over groups.',
    'score_sd': 'Standard deviation over all seed × fold scores — a spread, '
                'NOT a standard error. Do not divide it by √seeds.',
    'ci': 'Half-width of a 95% interval on the mean, Student t on the number '
          'of seeds the file holds.',
    'bin': 'Pad-occupancy bin: the number of wells on the pad each well sits '
           'on.',
    'pad_const': 'Share of multi-well pads whose wells all carry one value of '
                 'this covariate.',
    'uniq_share': 'Share of wells whose value of this covariate occurs on '
                  'exactly one pad. Constancy plus uniqueness is what makes a '
                  'covariate an identifier rather than a coarse stratifier '
                  '(§6.3).',
}

# `fig5_data.csv` carries the same six columns for each of its three arms.
# Expanded rather than typed out, so a fourth arm cannot be added without its
# columns being described.
ARMS = {'full': 'the whole feature set',
        'nocoord': 'the feature set minus latitude and longitude',
        'elev': 'ground elevation alone'}


def arm_columns():
    out = {}
    for arm, what in ARMS.items():
        out['%s_random' % arm] = 'R² under a random split, with %s.' % what
        out['%s_random_sd' % arm] = 'Spread of that over seeds, not a standard error.'
        out['%s_pad' % arm] = 'R² under a pad-grouped split, with %s.' % what
        out['%s_pad_sd' % arm] = 'Spread of that over seeds, not a standard error.'
        out['%s_infl' % arm] = 'Inflation with %s: `%s_random − %s_pad`.' % (what, arm, arm)
        out['%s_infl_ci' % arm] = ('Half-width of a 95%% interval on `%s_infl`, '
                                   'formed seed by seed.' % arm)
    return out

RESULTS = [
    ('recovery_sweep.csv', 'recovery_sweep.py',
     'Figure 1, Table S2 — how well the clustering recovers a published '
     'register, by radius and by extra constraint.',
     {'constraint': '`distance`, `+ operator` or `+ 3-yr spud`; each tested on '
                    'its own and never stacked.',
      'precision': 'Pairwise precision over all well pairs on the "same pad" '
                   'relation.',
      'recall': 'Pairwise recall on the same relation.',
      'f1': 'Harmonic mean of the two.',
      'ari': 'Adjusted Rand index (Hubert and Arabie, 1985).',
      'exact': 'Share of register pads recovered exactly — the strictest of '
               'the four measures.',
      'pads_inferred': 'Clusters the radius produced.',
      'pads_true': 'Pads the register reports.'}),
    ('radius_sweep.csv', 'radius_sweep.py',
     'Table 3 and Figure 3 from 25 m upwards.',
     {'grouping': '`random`, `pad register`, or the radius as a label.',
      'score': 'R² under the grouping named in `grouping`.'}),
    ('radius_fine.csv', 'radius_fine.py',
     'Table 3 and Figure 3 from 1 m to 20 m — the range in which the effect '
     'appears.',
     {'grouping': 'The radius, or `register`.',
      'score': 'R² under that grouping.'}),
    ('fig_data.csv', 'fig_compute.py, then co_fig.py',
     'Table 2 and Figure 2 — the occupancy gradient, one row per state × bin × '
     'seed so that an interval can be re-derived rather than taken on trust. '
     'Run `co_fig.py` second: it replaces the Colorado rows and keeps the rest.',
     {'mean_wells_per_pad': 'Mean occupancy of the wells in this bin.'}),
    ('fig5_data.csv', 'fig5_compute.py',
     'Tables 4 and 5, §5\'s pooled inflations and Figure 4. Three arms per '
     'state: `full_*` the whole feature set, `nocoord_*` the same minus '
     'latitude and longitude, `elev_*` ground elevation alone.',
     dict(arm_columns(), **{
      'n_wells': 'Wells modelled.', 'n_pads': 'Pads they sit on.',
      'full_infl_ci': 'Half-width of a 95% interval on the inflation, formed '
                      'seed by seed. The arms share a seed, so the pairing is '
                      'what makes the interval honest.',
      'nocoord_change': 'Change in inflation when the coordinates are removed, '
                        'paired on the seed: `nocoord_infl − full_infl`.',
      'nocoord_change_ci': 'Half-width of a 95% interval on that change.',
      'nocoord_verdict': '`worse`, `better` or `indistinguishable`, decided by '
                         'whether that interval clears zero. The paper\'s claim '
                         'is read from this column, not from the sign of the '
                         'difference — reading the sign is how the claim was '
                         'twice stated wrongly.',
      'pad_const': 'Share of multi-well pads whose wells all carry one '
                   'elevation value.',
      'uniq_share': 'Share of wells whose elevation value occurs on exactly '
                    'one pad.'}),
     ),
    ('fig5_seeds.csv', 'fig5_compute.py',
     'The per-seed inflations behind `fig5_data.csv`, so that every interval '
     'in §5 and Table 4 can be recomputed from the deposit.',
     {'arm': '`full`, `nocoord` or `elev`.',
      'inflation': 'This seed\'s `random − pad`, before any averaging.'}),
    ('proxy_compare.csv', 'proxy_compare.py',
     'Table 6 and Figure 5 — every alternative scheme measured against the pad '
     'reference.',
     {'scheme': '`pad (register)` or `pad (inferred)`, `random`, `operator`, '
                '`spud year`, `spatial 10 km`, `spatial 25 km`.',
      'mean': 'Mean R² under this scheme.',
      'delta': 'Difference from the pad reference. Positive is optimistic, '
               'negative over-conservative. Zero on the reference row itself.',
      'held_out': 'Share of WELLS held out. Table 6 balances wells rather than '
                  'groups, for the reason §S5.1 gives.'}),
    ('holdout_test.csv', 'holdout_test.py',
     '§S4\'s held-out-fraction test: is the effect an artefact of how much data '
     'a grouped split withholds?',
     {'t': 'Held-out fraction, 0.10, 0.20 or 0.40.',
      'mean_k': 'Mean pad occupancy in the bin.',
      'p_leak': 'Probability that at least one pad-mate of a given test well '
                'falls in training, `1 − t^(k−1)`, at this bin\'s occupancy.',
      'inflation_sd': 'Spread over seeds, not a standard error.'}),
    ('mechanism_test.csv', 'mechanism_test.py',
     '§S5.2 — the coordinate-removal comparison repeated across radii in the '
     'two register states, as an independent route to Table 4.',
     {'grouping': 'Radius, or `register`.',
      'infl_full': 'Inflation with the full feature set.',
      'infl_no-coords': 'Inflation with latitude and longitude removed.',
      'infl_coords-only': 'Inflation with the coordinates as the only features.'}),
    ('covariate_audit.csv', 'covariate_audit.py',
     'Table 5 and §6.3 — each covariate scored alone, to ask whether it is a '
     'pad label.',
     {'covariate': 'The single feature this row scores.',
      'n': 'Wells scored.',
      'random_sd': 'Spread over seeds.', 'pad_sd': 'Spread over seeds.',
      'pad_icc': 'Intraclass correlation of the covariate within pads. §6.3 '
                 'reports that this does NOT predict the leak; it is deposited '
                 'because the negative result is part of the paper.'}),
    ('register_vs_inferred.csv', 'register_vs_inferred.py',
     'Table S4 and §4.3 — the published register against the 150 m inferred '
     'grouping, paired by seed over thirty seeds.',
     {'register': 'R² grouping by the published register.',
      'inferred': 'R² grouping by the 150 m clustering.',
      'diff': '`inferred − register`, this seed. Negative means the inferred '
              'grouping scores lower, which is the conservative direction.',
      'train_register': 'Training-set size under the register.',
      'train_inferred': 'Training-set size under the clustering.'}),
    ('cluster_structure.csv', 'cluster_structure.py',
     '§S3.1 — what the clustering produces at each radius, with no model '
     'involved.',
     {'clusters': 'Clusters formed.',
      'per_cluster': 'Mean wells per cluster, averaged over clusters.',
      'median_cluster': 'Median cluster size.',
      'per_well_mean': 'Mean occupancy of the cluster a well sits on, averaged '
                       'over WELLS — the average that governs the leak.',
      'per_well_median': 'Median of the same.',
      'largest': 'Largest cluster, the guard against chaining.'}),
    ('occupancy_trend.csv', 'occupancy_trend.py',
     'Table S7 — mean pad occupancy by spud era.',
     {'pad_source': '`register` or `inferred 150 m`.',
      'era': 'Spud era, or `all`.',
      'pads': 'Pads in the era.',
      'per_pad': 'Mean occupancy averaged over pads.',
      'per_well_mean': 'Mean occupancy averaged over wells — the figure Table '
                       'S7 prints.',
      'per_well_median': 'Median of the same.',
      'largest': 'Largest pad in the era.'}),
    ('operator_vintage.csv', 'operator_vintage.py',
     '§8.2 — why operator grouping looks harmless on a recent sample.',
     {'sample': 'The vintage restriction, e.g. `from 2020`.',
      'pads': 'Register pads in the sample.',
      'multi': 'Of those, how many carry more than one operator code.',
      'share': 'That fraction.', 'share_pct': 'The same as a percentage.'}),
    ('pad_size_gradient.csv', 'pad_size_gradient.py',
     'An independent route to Table 2\'s cells, computed through a different '
     'code path from `fig_compute.py`.',
     {'pad_bin': 'Occupancy bin.',
      'random_sd': 'Spread over seeds.', 'placebo_sd': 'Spread over seeds.',
      'pad_sd': 'Spread over seeds.'}),
    ('co_gradient.csv', 'co_grad.py',
     'Table 2\'s Colorado column by that second code path. It agrees with '
     '`fig_data.csv` on every bin; kept because an agreement between two code '
     'paths is worth more than one path\'s word for itself.',
     {'mean_wells_per_pad': 'Mean occupancy of the bin.'}),
    ('zero_depth_check.csv', 'zero_depth_check.py',
     'Table S6 — what recoding the placeholder zeros as missing does to the '
     'measurement.',
     {'treatment': '`as published` or `zeros recoded NaN`.',
      'n': 'Wells scored.'}),
    ('oh_feat_audit.csv', 'oh_feat_audit.py',
     '§2 and §S2.5 — the one covariate the audit removed, Ohio\'s count of '
     'reported production quarters, which is downstream of the outcome.',
     {'features': '`with n_q_total` or `WITHOUT it`.',
      'bin': 'Occupancy bin, or `all`.'}),
    ('nm_rule_effect.csv', 'nm_rule_effect.py',
     '§S2.3 — the size of the defect New Mexico\'s missing first-year '
     'completeness rule was causing. Both arms run on the paper\'s own seed '
     'schedule so that the before and after are comparable.',
     {'rule': '`no completeness rule` or `twelve months required`.',
      'measure': 'Which of the paper\'s three measurements this row reports.',
      'value': 'That measurement.',
      'pads': 'Inferred pads in the arm.',
      'pad_grouped': 'The pad-grouped R², repeated here for the rows where the '
                     'measurement IS that score.'}),
    ('pod_check.csv', 'pod_check.py',
     '§3 and §9 — every New Mexico OCD "POD" identifier and the span of the '
     'wells it holds, the evidence that a published administrative grouping is '
     'not evidence of a physical one.',
     {'pod_idn': 'The OCD POD identifier.',
      'wells': 'Wells carrying it.',
      'span_m': 'Greatest distance in metres between any two of them.'}),
]


def profile(path):
    d = pd.read_csv(path, low_memory=False)
    rows = []
    for c in d.columns:
        s = d[c]
        nn = s.notna().mean()
        num = pd.to_numeric(s, errors='coerce')
        if num.notna().mean() > 0.9 and not pd.api.types.is_bool_dtype(s):
            lo, hi = num.min(), num.max()
            fmt = (lambda v: '%.4f' % v) if abs(hi) < 1000 and (hi % 1) else (lambda v: '%,.0f'.replace(',', '') % v)
            rng = '%s – %s' % (fmt(lo), fmt(hi)) if pd.notna(lo) else '—'
            typ = 'number'
        else:
            u = s.dropna().astype(str).unique()
            rng = ('%d distinct' % len(u)) if len(u) > 6 else ', '.join(sorted(u)[:6])
            typ = 'text'
        rows.append((c, typ, nn, rng))
    return len(d), rows


def esc(x):
    return str(x).replace('|', '\\|')


# ------------------------------------------- the analysis sets, for §quality
# The tables above are what is deposited. What the model actually sees is the
# filtered subset each experiment builds, so the missing-value audit has to be
# run on that subset and not on the table — the filters change the shares.
def analysis_sets():
    import importlib.util
    spec = importlib.util.spec_from_file_location('le', P.out('leakage_experiment.py'))
    le = importlib.util.module_from_spec(spec)
    sys.modules['le'] = le
    spec.loader.exec_module(le)
    FE = ['lat', 'lon', 'spud_year', 'depth', 'elev', 'n_stim']

    pa, f = le.load_pennsylvania()
    yield 'Pennsylvania', pa, f, {'depth': 'total_depth_ft', 'elev': 'elevation_ft',
                                  'n_stim': 'n_stimulations'}

    o = pd.read_csv(P.oh('oh_analysis.csv'), dtype={'PadNumber': str, 'OPNO': str},
                    low_memory=False)
    o['first_prod'] = pd.to_datetime(o.first_prod, errors='coerce')
    o['y'] = np.log10(pd.to_numeric(o.first4_gas, errors='coerce'))
    o['spud_year'] = (pd.to_datetime(o.DT_SPUD, errors='coerce', format='mixed')
                      .dt.year.fillna(o.first_prod.dt.year))
    o['depth'] = pd.to_numeric(o.DTD, errors='coerce')
    o['elev'] = pd.to_numeric(o.ELEV_GR, errors='coerce')
    o = (o.replace([np.inf, -np.inf], np.nan)
          .dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True))
    yield 'Ohio', o, FE[:5], {'depth': 'DTD', 'elev': 'ELEV_GR'}

    nm, f = le.load_new_mexico()
    yield 'New Mexico', nm, f, {'depth': 'md', 'elev': 'tvd', 'n_stim': 'n_pools'}

    c = pd.read_csv(P.co('co_analysis.csv'), dtype={'api8': str, 'operator': str},
                    low_memory=False)
    c['y'] = np.log10(pd.to_numeric(c.first365_G, errors='coerce').where(lambda s: s > 0))
    c['spud_year'] = pd.to_datetime(c.spud_dte, errors='coerce').dt.year
    c['depth'] = pd.to_numeric(c.max_md, errors='coerce')
    c['elev'] = pd.to_numeric(c.ground_elev, errors='coerce')
    c['n_stim'] = pd.to_numeric(c.max_tvd, errors='coerce')
    c = c.dropna(subset=['lat', 'lon', 'y', 'spud_year']).reset_index(drop=True)
    yield 'Colorado', c, FE, {'depth': 'max_md', 'elev': 'ground_elev',
                              'n_stim': 'max_tvd'}


def zero_depth_rows():
    """The four rows of `zero_depth_check.csv`, so the table below states what
    the experiment measured rather than what someone typed. The hardcoded
    version drifted: it printed New Mexico as +0.0692 -> +0.0689, a FALL of
    0.0003, where the deposited file has +0.0626 -> +0.0639, a RISE of 0.0014.
    """
    path = P.out('zero_depth_check.csv')
    if not os.path.exists(path):
        return None
    d = pd.read_csv(path)
    out = {}
    for st, g in d.groupby('state'):
        g = g.set_index('treatment')
        try:
            a = float(g.loc['as published', 'inflation'])
            b = float(g.loc['zeros recoded NaN', 'inflation'])
        except KeyError:
            continue
        out[st] = (a, b, b - a,
                   float(g.loc['as published', 'random']),
                   float(g.loc['zeros recoded NaN', 'random']),
                   float(g.loc['as published', 'pad']),
                   float(g.loc['zeros recoded NaN', 'pad']))
    return out


def nm_zero_shares():
    """New Mexico's placeholder-zero shares, measured on the analysis set."""
    for name, d, feats, _src in analysis_sets():
        if name != 'New Mexico':
            continue
        md = pd.to_numeric(d['depth'], errors='coerce')
        tvd = pd.to_numeric(d['elev'], errors='coerce')
        nz = md[md > 0]
        return (len(d), 100.0 * (md == 0).mean(), 100.0 * (tvd == 0).mean(),
                int((md > 30000).sum()), float(nz.median()))
    return None


def main():
    print('# DATA DICTIONARY — the five input tables and the twenty result tables\n')
    print('Generated by `make_dictionary.py`. Row counts, types, null shares and '
          'ranges are measured from the files on every run; the meaning of each '
          'column is maintained by hand in that script.\n')
    print('Every table here is a **derived join**, not a verbatim agency file. '
          'Each column is tagged `agency` (copied from the source record '
          'unchanged), `derived` (computed by a build script) or `key` (an '
          'identifier used to join the sources), so a reader can tell which '
          'values could carry our mistakes and which could not.\n')
    print('**used** marks a column some script in this project reads. *carried* '
          'marks one that is present but never read — kept because it costs '
          'nothing, flagged so nobody assumes it is part of the analysis.\n')
    print('Provenance and checksums for the raw inputs these were built from are '
          'in `SOURCES.md`.\n')
    print('---\n')

    for t in TABLES:
        n, rows = profile(t['path'])
        used = set(t['used'])
        default = t.get('default', DEFAULT)
        print('## %s\n' % t['title'])
        print('**%s**  ' % t['agency'])
        print('%d rows, %d columns.\n' % (n, len(rows)))
        print('%s\n' % t['note'])
        print('| column | kind | used | type | non-null | range or values | meaning |')
        print('|---|---|---|---|---|---|---|')
        for c, typ, nn, rng in rows:
            kind, units, mean = COLUMNS.get(c, default)
            u = '**used**' if c in used else '—'
            un = '' if units == '—' else ' *(%s)*' % units
            print('| `%s` | %s | %s | %s | %.1f%% | %s | %s%s |'
                  % (esc(c), kind, u, typ, 100 * nn, esc(rng), mean, un))
        undocumented = [c for c, _, _, _ in rows if c not in COLUMNS]
        if undocumented:
            print('\n%d of these columns carry the table\'s default description '
                  'rather than a note of their own: %s.\n'
                  % (len(undocumented), ', '.join('`%s`' % c for c in undocumented)))
        print()

    print('---\n')
    print('## The one column excluded on purpose\n')
    print('`oh_analysis.csv` carries `n_q_total`, the number of quarters a well '
          'has reported. It is **not** in any feature set. It is downstream of '
          'the outcome — a well that produces more is reported for longer — and '
          'correlates +0.26 with the target. It was found during the covariate '
          'audit, removed, and every Ohio result regenerated; its removal moves '
          'the headline Ohio inflation from +0.111 to +0.118. The column is kept '
          'in the table so the audit can be repeated, and `oh_feat_audit.py` '
          'does exactly that.\n')
    print('## What the model actually sees\n')
    print('The feature vector has the same six slots in every state, but the '
          'quantity in the last two slots is whatever that regulator publishes, '
          'and the slot names in the code are historical. The mapping is:\n')
    print('| slot | Pennsylvania | Ohio | New Mexico | Colorado |')
    print('|---|---|---|---|---|')
    print('| `lat`, `lon` | `lat_index`, `lon_index` | `lat`, `lon` | `lat`, `lon` | `lat`, `lon` |')
    print('| `spud_year` | `spud_date` | `DT_SPUD` → `first_prod` | `spud_dte` | `spud_dte` |')
    print('| `depth` | `total_depth_ft` | `DTD` | `md` | `max_md` |')
    print('| `elev` | `elevation_ft` | `ELEV_GR` | **`tvd`** | `ground_elev` |')
    print('| `n_stim` | `n_stimulations` | *(absent — five features)* | **`n_pools`** | `max_tvd` |')
    print()
    print('The two bold entries are worth stating plainly. **New Mexico\'s '
          'model is not given ground elevation**: `nm_well_summary.csv` has no '
          'elevation column, so the `elev` slot holds true vertical depth, and '
          'the sixth slot holds the pool count. New Mexico\'s ground elevation '
          'exists — §6 reads `elev_gl_num` from `wellhistory.csv` and reports '
          'its leak in Table 5 — but it is joined there for the tests of §6 '
          'and is not a modelled covariate elsewhere. `n_pools` is counted from the production '
          'filings and is therefore post-outcome in the same sense as Ohio\'s '
          '`n_q_total` (§2); unlike `n_q_total` it is 95.2% constant at the '
          'value 1 and correlates −0.024 with the target. `nm_feat_audit.py` '
          'runs the Ohio audit on it: dropping the column moves New Mexico\'s '
          '150 m inflation by about 0.0004, well inside the seed spread. It is '
          'kept; `log_nm_feat_audit.out` carries the two figures.\n')
    print('## Missing values, and the two agencies that write them as zero\n')
    print('The table below is measured on the **analysis sets** — the filtered '
          'subsets the experiments actually fit, not the deposited tables — '
          'because the filters change the shares. `zero` counts values that are '
          'exactly zero; for a depth or an elevation that is not a measurement '
          'but a placeholder for one that was never recorded.\n')
    print('| state | wells | slot | source column | zero | null | min | max |')
    print('|---|---|---|---|---|---|---|---|')
    flagged = []
    for name, d, feats, srccol in analysis_sets():
        for f in feats:
            s = pd.to_numeric(d[f], errors='coerce')
            z, nu = int((s == 0).sum()), int(s.isna().sum())
            if z or nu:
                flagged.append((name, f, z, len(d)))
            print('| %s | %d | `%s` | `%s` | %d (%.1f%%) | %d (%.1f%%) | %s | %s |'
                  % (name, len(d), f, srccol.get(f, f), z, 100 * z / len(d),
                     nu, 100 * nu / len(d),
                     '%.4g' % s.min(), '%.6g' % s.max()))
    print()
    _nz = nm_zero_shares()
    print('**New Mexico is the serious case.** Of %s wells, measured depth '
          'is zero for %.1f%% and true vertical depth for %.1f%% — the OCD writes '
          'a zero where no depth was filed. These enter the model as the number '
          'zero, not as a missing value, even though '
          % (format(_nz[0], ','), _nz[1], _nz[2]) if _nz else
          '**New Mexico is the serious case.** The OCD writes a zero where no '
          'depth was filed. These enter the model as the number zero, not as a '
          'missing value, even though '
          '`HistGradientBoostingRegressor` handles NaN natively and would have '
          'learned a default split direction for them. Ohio does the same thing '
          'on a smaller scale: 45 zeros and 42 nulls in `DTD`, 7.5% of 1,158 '
          'wells between them.\n')
    print('This is a defect in the feature, and it is reported here rather than '
          'left for a reader to find. It does not reach the measurement, for a '
          'reason that is structural rather than lucky: the quantity this paper '
          'reports is the **difference** between two partitions of one table. '
          'Both partitions see the same degraded column, so a degraded column '
          'cannot open a gap between them — it can only lower both scores. '
          '`zero_depth_check.py` tests that argument instead of resting on it, '
          'rescoring both states at the 150 m pad radius with the zeros recoded '
          'to NaN, six seeds and five 80/20 splits each, exactly as '
          '`radius_sweep.py` scores everything else:\n')
    print('| state | inflation, zeros as published | zeros recoded NaN | change |')
    print('|---|---|---|---|')
    _zd = zero_depth_rows() or {}
    for _st in ('New Mexico', 'Ohio'):
        if _st in _zd:
            _a, _b, _d = _zd[_st][:3]
            print('| %s | %+.4f | %+.4f | **%+.4f** |' % (_st, _a, _b, _d))
        else:
            print('| %s | — | — | — |  <!-- zero_depth_check.csv missing -->' % _st)
    print()
    print('Recoding lowers *both* the random and the pad-grouped score in both '
          'states, which is what the structural argument predicts: a degraded '
          'column is seen by both partitions. It does not lower them by exactly '
          'the same amount, so the difference does move — upward in New Mexico, '
          'downward in Ohio — by about a thousandth of an R², against effects of '
          '0.06 and 0.11. The argument is therefore supported in direction and '
          'in magnitude rather than exactly, which is what a test is for. '
          '`zero_depth_check.csv` carries the four rows and the underlying '
          'scores.\n')
    print('Three Pennsylvania ground elevations — 7,533, 21,702 and 24,500 ft — '
          'exceed the state\'s highest point (3,213 ft) and are transcription '
          'errors in the permit record. %s New Mexico measured depths exceed '
          '30,000 ft against a non-zero median of %s ft. Two Colorado wells '
          'carry impossible values that the retired lateral-length proxy had '
          'excluded by accident: api8 12351658 reports a true vertical depth of '
          '70,647 ft against a measured depth of 20,832, and api8 6710057 a '
          'ground elevation of 64,192 ft. All are left as '
          'published, for the same reason and with the same caveat.\n'
          % ({1:'One',2:'Two',3:'Three'}.get(_nz[3], format(_nz[3], ',')),
             format(int(round(_nz[4])), ','))
          if _nz else
          'errors in the permit record. They are left as published, for the '
          'same reason and with the same caveat.\n')
    print('---\n')
    print('## The result tables\n')
    print('The twenty CSVs beside the code are the results: every number in '
          'the paper is printed from one of them, and `verify_manuscript.py` '
          'compares the two mechanically. Row and column counts below are '
          'measured on every run; the meanings are maintained by hand in '
          '`make_dictionary.py`.\n')
    print('Unless a table says otherwise, a score is R² on held-out wells, '
          'averaged over the seed × fold schedule that table was run on, and '
          'these columns mean the same thing everywhere:\n')
    print('| column | meaning |')
    print('|---|---|')
    for c in ('state', 'seed', 'wells', 'random', 'pad', 'placebo', 'inflation',
              'placebo_effect', 'radius_m', 'groups', 'mean_size', 'bin',
              'score_sd', 'ci'):
        print('| `%s` | %s |' % (c, SHARED[c]))
    print()

    for name, by, what, notes in RESULTS:
        path = P.out(name)
        if not os.path.exists(path):
            print('### `%s`\n' % name)
            print('*Not present in this copy of the archive.*\n')
            continue
        n, rows = profile(path)
        print('### `%s`\n' % name)
        print('%s  \nWritten by `%s`. %d rows, %d columns.\n'
              % (what, by, n, len(rows)))
        print('| column | type | non-null | range or values | meaning |')
        print('|---|---|---|---|---|')
        for c, typ, nn, rng in rows:
            mean = notes.get(c) or SHARED.get(c) or '—'
            print('| `%s` | %s | %.1f%% | %s | %s |'
                  % (esc(c), typ, 100 * nn, esc(rng), mean))
        undesc = [c for c, _, _, _ in rows
                  if c not in notes and c not in SHARED]
        if undesc:
            print('\n**%d column(s) here have no description: %s.** This line is '
                  'generated, so it appears whenever a script gains a column '
                  'and `make_dictionary.py` is not updated with it.\n'
                  % (len(undesc), ', '.join('`%s`' % c for c in undesc)))
        print()

    print('---\n')
    print('## Coordinates\n')
    print('All four states publish wellhead coordinates in decimal degrees on a '
          'WGS84-compatible datum, and the clustering in §3 uses them directly. '
          'Ohio stores both NAD27 and NAD83 pairs; `oh_build.py` prefers NAD83 '
          'and falls back to NAD27 where the NAD83 value is out of state bounds. '
          'Colorado additionally publishes `loc_qual`, which distinguishes a '
          'surveyed position from a planned one — the only per-well statement of '
          'coordinate quality any of the four agencies provides.\n')


if __name__ == '__main__':
    main()
