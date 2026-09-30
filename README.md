# Group-identifier leakage in unconventional production models: ordinary covariates identify the well pad

Basel Alrawi, Wenhui Huang, Xiaoping Mao
School of Energy Resources, China University of Geosciences (Beijing),
Beijing 100083, China
Corresponding author: Basel Alrawi, <basel@email.cugb.edu.cn>

Analysis code, one result file per experiment, and the five figures for the
paper above, submitted to *Computers & Geosciences*.

**What the code does.** Machine-learning studies of unconventional well
productivity are usually validated by splitting wells at random. Wells are not
independent: two to eight of them share a surface pad, and a regulator's table
records much of what distinguishes a pad — elevation, formation top, completion
date, operator — once per pad and copies it to every well on it. A random split
therefore trains and tests on the same pad. This code measures how large that
effect is: it recovers the pad from wellhead coordinates, scores one untuned
learner twice on the same table changing only the fold assignment, and reports
the difference. Across four US states the random split reports up to 0.39 R²
that grouping by pad does not reproduce. It also tests the obvious remedies —
grouping by operator, by spud year, by spatial block, and deleting the
coordinates — and finds that each errs in the opposite direction or makes the
leak worse.

Everything resolves inside this folder. No script reads a path outside it, and
none reads an environment variable that could redirect one.

---

## Quick start

Nothing here needs a download. Clone, install five packages, and run:

```sh
git clone https://github.com/Basel277279/group-identifier-leakage.git
cd group-identifier-leakage
python3 -m pip install -r requirements.txt

python3 test_infer_pads.py --quick      # the test suite, ~4 s
python3 example_diagnostic.py           # the method on one worked example, ~30 s
python3 reproduce_figures.py            # redraw all five paper figures, <1 min
```

Those three commands are the whole of what this repository can be checked by
without any data download. The first two are described under **Running the
tests** below; the third is described under **Reproducing the paper**.

## Requirements and installation

Python 3.11 or newer, and five packages. Both dependency files pin the exact
versions every published number and figure was produced with:

```sh
python3 -m pip install -r requirements.txt     # pip
```

```sh
conda env create -f environment.yml            # conda, same pins
conda activate p3-leakage
```

| package | version used |
|---|---|
| numpy | 2.4.4 |
| pandas | 3.0.2 |
| scipy | 1.17.1 |
| scikit-learn | 1.8.0 |
| matplotlib | 3.10.9 |

The versions are pinned rather than bounded on purpose. The reported quantity
is a difference between two partitions of one table, and both partitions depend
on scikit-learn's splitter RNG and on `HistGradientBoostingRegressor`'s
binning. A different scikit-learn will reproduce the paper's conclusions; it
will not reproduce the third decimal place of every cell.

**One font, for the figure scripts only.** The published figures were
rendered in **Arial**, which is the face the journal names and which Windows
and macOS provide. On a machine without it, `figure_font.py` falls back to
Helvetica, Liberation Sans, Nimbus Sans or Arimo, in that order; Liberation
Sans is free and metric-compatible with Arial (`apt install fonts-liberation`,
`dnf install liberation-sans-fonts`, `brew install --cask font-liberation`).
A substitute gives the same figure at the same dimensions with different glyph
outlines, so it is not pixel-identical to the published file, and
`reproduce_figures.py` says so. If none of the listed faces is available the
figure scripts stop rather than let matplotlib substitute DejaVu Sans, which
this journal does not accept and which changes the size of every figure. Only
`make_figureN.py` and `reproduce_figures.py` need a font; the test, the
worked example and every experiment run without one.

Two optional extras are needed only to rebuild a state table from the
regulator's own files, which no command above does: `mdbtools` (Linux, macOS)
or `pyodbc` with the Microsoft Access driver (Windows), for Ohio's RBDMS
database. Nothing else in this repository needs either.

No compiled extension, no GPU, no cluster. The longest job in the repository
fits in about 2 GB of memory on one core.

## Running the tests

### The quick test — 4 seconds, no data needed

```sh
python3 test_infer_pads.py --quick
```

It prints one line per test and `5/5 passed`, and exits 0 only if all five
pass. It also runs under pytest (`pytest test_infer_pads.py`) if you prefer.

This is not a smoke test. `infer_pads` groups wells by single-link clustering
within a radius, and for speed it does not compare all pairs: it bins wells
into a grid and compares each well only with the nine cells around it. That is
an optimisation of a clustering, which is exactly the kind of code that fails
silently — it returns a partition either way, and a partition that is 2% wrong
looks entirely normal downstream. It did fail once, in a version that used the
same cell size in degrees for latitude and longitude; a degree of longitude
spans only cos(φ) of a degree of latitude, so the longitude cells were too
narrow by about 1.24 at the latitude of the Permian, and pads were split. The
first of the five tests is the regression fixture for that bug, swept across
thirty-three positions within a grid cell at five latitudes, because at a
single fixed position the buggy code passes at exactly the latitudes this study
uses. The other four cover synthetic pads at eleven radii from 10 m to 10 km,
edge cases (empty input, one well, coincident wells, the prime meridian and the
equator), order independence, and the transitivity of single link.

### The full test — about four minutes, needs the data

```sh
python3 test_infer_pads.py
```

Adds a sixth test: the grid partition must equal the brute-force O(n²)
partition, exactly, on all four state datasets at every one of the eleven
radii. It needs `Data/` (see below); without it that test prints which states
it skipped and the other five still run.

### The worked example — 30 seconds, no data needed

```sh
python3 example_diagnostic.py            # built-in synthetic wells
python3 example_diagnostic.py wells.csv  # your own table
```

The paper's claim is a procedure, and `example_diagnostic.py` is that procedure
on its own, short enough to read in one sitting and to lift into another study.
It builds a synthetic well table whose pads are known by construction, recovers
the pads from the coordinates, scores one learner under a random split and
under a grouped split, prints the gap, and then runs the per-feature audit that
is recommendation 3 of §9 — each feature scored alone under both splits, so
that a feature acting as a pad label is named rather than guessed at.

Its synthetic pad effect is deliberately strong, so the gap it prints is about
1.1 R², far larger than the 0.39 the paper reports at its worst. It is a
demonstration that the diagnostic responds to a pad effect of a size chosen by
the fixture. It is not a result; the paper's numbers come from the state
tables.

To run it on your own wells, give it a CSV with `lat`, `lon` and `y` columns —
wellhead coordinates in decimal degrees and one target per well. Every other
numeric column is used as a feature. Add a `pad` column and it is used as the
grouping; leave it out and the grouping is recovered from the coordinates by
single-link clustering at 150 m, which is what the paper does where no register
exists.

### Checking the files themselves

```sh
python3 verify_manifest.py
```

Hashes every file against `MANIFEST.sha256` and also reports any file present
but unlisted, which a checksum list cannot notice by construction. It uses only
the standard library, because `sha256sum -c` does not exist on Windows. Run it
on a fresh clone: `reproduce_figures.py` and `run_all.sh` are supposed to
rewrite result files, and afterwards a hash that differs may mean the
reproduction differed, which is interesting, or merely that a file was
rewritten identically, which is not. Downloaded data under `Data/` and the
`log_*.out` files a run leaves behind are reported separately and are not
faults.

## Reproducing the paper

### The five figures — from this repository alone

```sh
python3 reproduce_figures.py
```

No figure reads the raw data; each reads result CSVs and nothing else, and all
twenty result tables are in this repository. So the figures are reproducible
from the code here with no download at all, in under a minute. The script
redraws all five and then compares each one with the copy that shipped, and it
fails unless every redrawn figure is **pixel for pixel** the published one. It
reports byte identity as well, but does not require it: matplotlib compresses a
PNG through the zlib that comes with your Python, so the same image deflates to
different bytes under a different Python — 3.11 and 3.13 disagree on all five
of these files while drawing exactly the same picture. Bytes match on the fully
pinned environment of `environment.yml`, Python 3.11 included, which is where
the files here were made; pixels match everywhere, and pixels are the claim
that matters.

The script prints the typeface and the installed versions against the
reference before it draws anything, so a difference is diagnosed rather than
left to be guessed at, and it names the PNG chunks of both copies when only
the bytes differ — that is how a file rewritten after the code wrote it (some
applications insert a C2PA `caBX` chunk into any image they save) is told
apart from a zlib difference.

If the typeface in use is not Arial, pixel identity is not
attainable — different glyph outlines give a different canvas under
`bbox_inches='tight'` — and the script says the comparison could not be made
rather than reporting a failure. It is the same figure either way.

The vector PDFs beside them are not compared: matplotlib writes a
`/CreationDate` into every PDF and does not let a caller suppress it, so a
rebuilt PDF differs in that one field on every machine, every time, and is
identical everywhere else.

| figure | reads | written by |
|---|---|---|
| Fig 1 | `recovery_sweep.csv` | `recovery_sweep.py` |
| Fig 2 | `fig_data.csv` | `fig_compute.py`, then `co_fig.py` |
| Fig 3 | `radius_sweep.csv`, `radius_fine.csv` | `radius_sweep.py`, `radius_fine.py` |
| Fig 4 | `fig5_data.csv` | `fig5_compute.py` |
| Fig 5 | `proxy_compare.csv` | `proxy_compare.py` |

Figures are numbered by order of first citation, so `make_figureN.py` writes
`FigN_*`. Each is written at its final printed width and at 1000 dpi, and
`save()` measures the file it wrote and raises the dpi if it came out short
rather than trusting the bounding box.

### The result tables — needs the derived state tables

The twenty result CSVs are regenerated by the experiments, and the experiments
read the four states' derived well tables. Those tables are research data
rather than code, they come to about 139 MB, and they are archived with a DOI:

> Alrawi, B., Huang, W., Mao, X., 2026. Derived tables and analysis code for
> "Group-identifier leakage in unconventional production models: ordinary
> covariates identify the well pad". Zenodo.
> <https://doi.org/10.5281/zenodo.22998446>

Download that record, and copy its `Data/` folder into this one, so that the
tree reads:

```
group-identifier-leakage/
├── *.py, *.sh                    the code
├── *.csv, Fig*.png, Fig*.pdf     the results and the figures
└── Data/
    ├── Pennsylvania/   P2_wells_with_logs.csv      2,505 wells
    ├── Ohio/           oh_analysis.csv             1,158 wells, modelling set
    │                   oh_register.csv             4,618 wells / 1,070 pads
    │                   oh_well_summary.csv
    ├── NewMexico/csv/  nm_well_summary.csv        89,406 producing wells
    │                   wellhistory.csv             ground elevation
    │                   pod.csv, podwc.csv          the OCD pod register
    └── Colorado/       co_analysis.csv            12,139 wells
                        co_well_summary.csv        66,930 producing wells
```

Then:

```sh
python3 p3_paths.py        # says which tables are present and which are missing
bash run_all.sh            # every result table and every figure, about 2 hours
bash run_all.sh --quick    # stages 1 and 2 only, about 25 minutes
bash reverify_all.sh       # only the six experiments that feed figures
```

`run_all.sh` writes `log_<script>.out` beside each script it runs and prints a
timestamp per stage. Stage 3 dominates: `pad_size_gradient.py` and
`holdout_test.py` each fit several thousand models.

### Rebuilding from the agencies' own files

`run_all.sh` does not run the acquisition stage (`nm_ocd_fetch.py`,
`nm_ocd_extract.py`) or the build stage (`nm_build.py`, `oh_build.py`,
`co_build.py`, `co_analysis.py`, `nm_check.py`). They read about 3 GB of raw
regulator downloads that are not redistributed, and `oh_build.py` additionally
needs the Access driver. Their outputs — the derived state tables above — are
what everything else reads. `SOURCES.md` gives the origin, size and SHA-256 of
each of the 82 raw inputs, so a reader can fetch them from the four agencies
and verify they have the same bytes. Run those two stages by hand if you are
rebuilding from the agency files.

Two measurements in the paper are reproduced by no script here, and are named
as such in §10: New Mexico's amendment audit and the FracFocus check of §S7.1.
Neither appears in a table or a figure.

## Inputs, outputs and options

**Where the data is.** `p3_paths.py` is the only place that knows. Every script
imports it, so the folder can be renamed, moved to another drive or copied to
another machine and everything still resolves. It honours one environment
variable, `P3_ROOT`, which moves the whole project; it deliberately honours no
per-state variable, because those names belong to the authors' other projects
and a stale one in the shell would make this code read another paper's data and
produce plausible, wrong numbers with nothing in the output to say so. Run
`python3 p3_paths.py` to be told what is present and what is missing.

**Where results go.** Beside the code, not into the working directory:
`python3 radius_sweep.py` writes `radius_sweep.csv` next to `radius_sweep.py`
whatever directory it was launched from. Scripts take no command-line
arguments; the two exceptions are documented in their own docstrings
(`test_infer_pads.py --quick`, `example_diagnostic.py <csv>`).

**What the columns mean.** `DATA_DICTIONARY.md` documents every column of every
derived table and every result table: which table or figure it feeds, the
source field, the units, whether the value is the agency's or ours, and whether
a spread column is a standard error or a spread over seeds. It also gives the
per-state mapping from the six feature slots to the agencies' own column names,
which is **not** the same in all four states, and the share of zero and missing
values in every feature of every analysis set. It is generated by
`make_dictionary.py`, not maintained by hand.

**The engine.** `leakage_experiment.py` holds the three things everything else
calls: `infer_pads(lat, lon, radius_m=150.0)` returns a pad label per well;
`load_pennsylvania()` and `load_new_mexico()` return a tidy table and its
feature list; `score(d, feats, splitter, groups, name)` runs one learner over
one splitter and returns R², MAE, the fold count and the group count. Read
`example_diagnostic.py` for how the three fit together.

## The code, in the order it runs

| stage | scripts |
|---|---|
| acquire | `nm_ocd_fetch.py`, `nm_ocd_extract.py` |
| build | `nm_build.py`, `oh_build.py`, `co_build.py`, `co_analysis.py`, `nm_check.py` |
| the engine | `p3_paths.py`, `leakage_experiment.py` |
| experiments | `pad_size_gradient.py`, `recovery_sweep.py`, `radius_sweep.py`, `radius_fine.py`, `proxy_compare.py`, `holdout_test.py`, `mechanism_test.py`, `fig5_compute.py`, `fig_compute.py`, `co_fig.py` |
| figures | `make_figure1.py` … `make_figure5.py` |
| tests and audits | `test_infer_pads.py`, `example_diagnostic.py`, `oh_feat_audit.py`, `nm_feat_audit.py`, `nm_rule_effect.py`, `zero_depth_check.py`, `nm_provenance.py`, `pod_check.py`, `audit_targets.py`, `co_window_scan.py`, `co_admit_scan.py`, `verify_manuscript.py`, `verify_manifest.py` |
| quoted in the text | `register_vs_inferred.py`, `covariate_audit.py`, `cluster_structure.py`, `occupancy_trend.py`, `operator_vintage.py` |
| provenance | `make_sources.py`, `make_dictionary.py` |
| superseded, kept for the record | `audit3.py`, `recheck.py`, `oh_run_b.py`, `co_grad.py`, `key_test.py`, `mech_nm_co.py`, `nocoord_nmco.py`, `pad_infer.py`, `pad_infer_ohio.py` |

The superseded scripts are not relied on; §S9 of the supplement says which
current script subsumed each. Only `co_grad.py` still writes a result file, and
it agrees with `fig_data.csv`.

`verify_manuscript.py` is the authors' own check that the paper's printed
numbers are these files' numbers — 318 values across the six main tables, four
of the supplement's tables, and the prose and captions that quote a figure. It
needs the
manuscript sources, which are not in this repository, so here it reports that
there is nothing to compare and exits cleanly. It is shipped so that a reader
can see exactly what was checked, and re-run it against their own copy of the
text.

All comments and identifiers in the code are in English.

## Two things to know before changing anything

**The clustering has a test, and it matters.** Run
`python3 test_infer_pads.py` after touching `infer_pads` — not the `--quick`
path, which skips the four-state equivalence check. The history above is why.

**Results are reported as differences, not absolute scores.** The model is
deliberately untuned. The measurement is what changes when only the train/test
partition changes; the absolute R² values are a by-product, and tuning the
learner is not a way to improve them.

## Licence and citation

Creative Commons Attribution 4.0 International (CC BY 4.0) — see `LICENSE`.
You may share and adapt this material for any purpose, including commercially,
provided you give appropriate credit and indicate whether changes were made.

The licence covers the code and the derived tables, which are our processing
and not verbatim agency files. The four agencies' own terms govern their raw
downloads; `SOURCES.md` records where each of the 82 came from.

Cite the archived version, which cannot change:

> Alrawi, B., Huang, W., Mao, X., 2026. Derived tables and analysis code for
> "Group-identifier leakage in unconventional production models: ordinary
> covariates identify the well pad". Zenodo.
> <https://doi.org/10.5281/zenodo.22998446>
