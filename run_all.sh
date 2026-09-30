#!/bin/bash
# Reproduce every number in the paper from the deposited derived tables.
#
#     bash run_all.sh            everything below, in order
#     bash run_all.sh --quick    stop after stage 2; skips the long experiments,
#                                the figures and the data dictionary (stages 3-5)
#
# No environment variables. Everything resolves through p3_paths.py, relative
# to this script's own folder. Do NOT set P2_DATA / NM_DATA / OH_DATA /
# CO_DATA: those names belong to the author's other projects and this one
# ignores them on purpose.
#
# WHAT IS NOT HERE
#   The acquisition stage (`nm_ocd_fetch.py`, `nm_ocd_extract.py`) and the
#   build stage (`nm_build.py`, `oh_build.py`, `co_build.py`, and
#   `co_analysis.py`, which selects Colorado's modelling table out of
#   `co_well_summary.csv`) are deliberately left out. They need roughly 3 GB of raw regulator downloads that are not
#   deposited, and `oh_build.py` additionally needs the Microsoft Access ODBC
#   driver. Their outputs -- the derived state tables -- ARE deposited, and
#   everything below reads those. Run them by hand if you are rebuilding from
#   the agency files; `SOURCES.md` records where each one came from.
#
#   The two measurements of §10 that no deposited script reproduces are named
#   there: New Mexico's amendment audit and the FracFocus check.
#
# TIMING on one 2023 laptop core: stage 1 seconds, stage 2 about 25 minutes,
# stage 3 about 90 minutes, stage 4 under a minute. Stage 3 dominates because
# `pad_size_gradient.py` and `holdout_test.py` each fit several thousand
# models.
set -e
cd "$(dirname "$0")"

QUICK=0
[ "$1" = "--quick" ] && QUICK=1

run () {   # run <label> <script>
  printf '### %-26s %s\n' "$1" "$(date +%T)"
  python3 "$2" > "log_${2%.py}.out" 2>&1
  printf '    done %-21s %s\n' "" "$(date +%T)"
}

python3 p3_paths.py || { echo "inputs missing -- see above"; exit 1; }

echo "=== stage 1: tests, audits and provenance ==========================="
run "clustering equivalence"  test_infer_pads.py
run "Ohio feature audit"      oh_feat_audit.py
run "New Mexico feature audit" nm_feat_audit.py
run "New Mexico completeness rule" nm_rule_effect.py
run "placeholder zeros"       zero_depth_check.py
run "New Mexico provenance"   nm_provenance.py
run "New Mexico POD check"    pod_check.py
run "cluster structure"       cluster_structure.py
run "occupancy by era"        occupancy_trend.py
run "operator by vintage"     operator_vintage.py

echo "=== stage 2: recovery and the covariate audit ======================="
run "recovery sweep"          recovery_sweep.py
run "covariate audit"         covariate_audit.py
run "register vs inferred"    register_vs_inferred.py

if [ "$QUICK" = "1" ]; then
  echo "=== stages 3-5 skipped (--quick) ==================================="
  exit 0
fi

echo "=== stage 3: the experiments ========================================"
run "fine radius sweep"       radius_fine.py
run "radius sweep"            radius_sweep.py
run "proxy comparison"        proxy_compare.py
run "occupancy gradient"      pad_size_gradient.py
run "Colorado gradient"       co_grad.py
run "held-out fraction"       holdout_test.py
run "mechanism test"          mechanism_test.py
# ORDER MATTERS: co_fig.py rewrites only fig_data.csv's Colorado rows and keeps
# the other three states from fig_compute.py, so fig_compute.py must run FIRST.
# The reverse order leaves fig_data.csv with three states and Figure 2 silently
# loses Colorado.
run "figure 2 data"           fig_compute.py
run "figure 2 data, Colorado" co_fig.py
run "figure 4 data"           fig5_compute.py

echo "=== stage 4: figures ================================================"
for i in 1 2 3 4 5; do
  printf '### %-26s %s\n' "figure $i" "$(date +%T)"
  python3 "make_figure$i.py" > "log_make_figure$i.out" 2>&1
done

echo "=== stage 5: the data dictionary ===================================="
# SOURCES.md is NOT regenerated here: `make_sources.py` needs the ~3 GB of raw
# downloads, which the deposit does not carry. Run it on the acquisition
# machine when a raw input changes.
# NOT via run(): make_dictionary.py writes the document to STDOUT, and run()
# redirects stdout into a log. The stage used to produce log_make_dictionary.out
# and leave DATA_DICTIONARY.md untouched.
printf '### %-26s %s\n' "data dictionary" "$(date +%T)"
python3 make_dictionary.py > DATA_DICTIONARY.md 2> log_make_dictionary.out
printf '    done %-21s %s\n' "" "$(date +%T)"

echo "=== stage 6: the manuscript against the result files ==============="
# Fails if any table cell in P3_main.md or P3_supplement.md no longer matches
# the CSV it came from. Put last, because it can only run once the results
# above have been rewritten.
#
# In the DEPOSIT the manuscript sources are absent by design, so this stage has
# nothing to compare and says so rather than failing. It is a check for the
# authors' working copy, and it is shipped so that a reader can see what was
# checked and re-run it against their own copy of the text.
printf '### %-26s %s\n' "verify manuscript" "$(date +%T)"
if [ -f P3_main.md ] && [ -f P3_supplement.md ]; then
  python3 verify_manuscript.py | head -2
else
  echo "    skipped: the manuscript sources are not part of the deposit"
  echo "    (the result files beside this script are covered by MANIFEST.sha256)"
fi
printf '    done %-21s %s\n' "" "$(date +%T)"

echo "### ALL DONE $(date +%T)"
echo
echo "Result tables are the *.csv beside this script; figures are Fig*.pdf."
echo "Per-script console output is in log_*.out."
