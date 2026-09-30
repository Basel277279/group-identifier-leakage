# Data/ is empty on purpose

The four states' derived well tables are research data rather than code, they
come to about 139 MB, and they are archived with a DOI:

> Alrawi, B., Huang, W., Mao, X., 2026. Derived tables and analysis code for
> "Group-identifier leakage in unconventional production models: ordinary
> covariates identify the well pad". Zenodo.
> https://doi.org/10.5281/zenodo.22998446

Download that record and copy its `Data/` folder over this one. `p3_paths.py`
resolves every input as `<folder holding p3_paths.py>/Data/<State>/...`, so the
paths must keep the layout the archive ships -- New Mexico's tables live in
`Data/NewMexico/csv/`, not `Data/NewMexico/`. Run `python3 p3_paths.py`
afterwards and it will say which tables it can see.

Nothing in the repository's quick start needs any of this. The test suite, the
worked example and all five figures reproduce from the code and result tables
alone; see `README.md`.
