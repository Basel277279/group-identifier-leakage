#!/bin/bash
# Re-run every experiment that feeds a figure, then rebuild all five.
#
# All SIX are required: recovery_sweep.py feeds Figure 1 and fig5_compute.py
# feeds Figure 4. Omitting either redraws that figure from whatever result
# file is already on disk.
#
# No environment variables. Everything resolves through p3_paths.py, relative
# to this script's own folder. Do NOT set P2_DATA / NM_DATA / OH_DATA /
# CO_DATA: those names belong to the author's other projects and this one
# ignores them on purpose.
set -e
cd "$(dirname "$0")"

python3 p3_paths.py || { echo "inputs missing -- see above"; exit 1; }

echo "### 1/6 recovery sweep (Figure 1)   $(date +%T)"
python3 recovery_sweep.py > v_recov.out 2>&1;  echo "    done $(date +%T)"
echo "### 2/6 fine sweep     (Figure 3)   $(date +%T)"
python3 radius_fine.py   > v_fine.out  2>&1;  echo "    done $(date +%T)"
echo "### 3/6 radius sweep   (Figure 3)   $(date +%T)"
python3 radius_sweep.py  > v_sweep.out 2>&1;  echo "    done $(date +%T)"
echo "### 4/6 proxy compare  (Figure 5)   $(date +%T)"
python3 proxy_compare.py > v_proxy.out 2>&1;  echo "    done $(date +%T)"
echo "### 5/6 mechanism data (Figure 4)   $(date +%T)"
python3 fig5_compute.py  > v_fig5.out  2>&1;  echo "    done $(date +%T)"
# fig_compute.py FIRST, then co_fig.py: co_fig.py replaces only fig_data.csv's
# Colorado rows and keeps the rest. The other order drops Colorado silently.
echo "### 6/6 occupancy data (Figure 2)   $(date +%T)"
python3 fig_compute.py   > v_fig.out   2>&1
python3 co_fig.py       >> v_fig.out   2>&1;  echo "    done $(date +%T)"

echo "### regenerating all five figures $(date +%T)"
for i in 1 2 3 4 5; do python3 make_figure$i.py > v_f$i.out 2>&1; done
echo "### ALL DONE $(date +%T)"
