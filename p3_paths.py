r"""One place that knows where the data is.

Every script in this project reads its inputs through this module, so the
project is self-contained: the code, the data and the results all live under
this folder, and nothing points outside it.

    P3_Data/
    ├── *.py                       the code
    ├── *.csv, Fig*.pdf/.png       the results and figures
    ├── SOURCES.md                 provenance and checksums for everything below
    └── Data/
        ├── Pennsylvania/          P2_wells_with_logs.csv
        ├── Ohio/                  oh_analysis.csv, oh_well_summary.csv
        ├── NewMexico/             the OCD .zip downloads
        │   └── csv/               and the tables extracted from them
        └── Colorado/              co_analysis.csv, co_well_summary.csv
            └── (plus the raw prod_reports and shapefiles at Data/ level)

WHY A MODULE AND NOT A CONSTANT IN EACH SCRIPT
    Before this existed, each script carried its own absolute path, and some
    of them pointed at a scratch directory on a machine that no longer exists.
    A script that cannot find its data fails loudly, which is survivable; the
    worse case is two scripts pointing at two different vintages of the same
    table and quietly disagreeing. This module makes that impossible.

WHERE THE ROOT COMES FROM, in order
    1. the P3_ROOT environment variable, if set
    2. the directory this file sits in
    The second is the normal case: keep the scripts and Data/ together and
    everything resolves, whatever directory you run from.

OUTPUTS
    Result tables and figures are written to the project root, not to the
    working directory, so `python3 radius_sweep.py` puts `radius_sweep.csv`
    beside the code no matter where it was launched from. Use `out(name)`.

NO PER-STATE ENVIRONMENT OVERRIDES, DELIBERATELY
    P2_DATA, NM_DATA, OH_DATA and CO_DATA are read by other projects of the
    same authors and are deliberately ignored here. Honouring them would let
    a variable left set in the shell redirect one state to another study's
    table, producing plausible and wrong numbers with no error raised and
    nothing in the output identifying the directory used.

    Only P3_ROOT is honoured, and it can only move the whole project, never one
    state. Everything this paper uses lives under P3_ROOT/Data and nowhere
    else.

    import p3_paths as P
    d = pd.read_csv(P.oh('oh_analysis.csv'))
    df.to_csv(P.out('radius_sweep.csv'), index=False)
"""
import os

ROOT = os.environ.get('P3_ROOT') or os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'Data')

PA_DIR = os.path.join(DATA, 'Pennsylvania')
OH_DIR = os.path.join(DATA, 'Ohio')
NM_DIR = os.path.join(DATA, 'NewMexico')
CO_DIR = os.path.join(DATA, 'Colorado')
NM_CSV = os.path.join(NM_DIR, 'csv')


def _j(base, name):
    return os.path.join(base, name) if name else base


def pa(name=''):
    """Pennsylvania: the compiled well table."""
    return _j(PA_DIR, name)


def oh(name=''):
    """Ohio: the derived analysis tables built from RBDMS."""
    return _j(OH_DIR, name)


def nm(name=''):
    """New Mexico: the OCD archives as downloaded."""
    return _j(NM_DIR, name)


def nmcsv(name=''):
    """New Mexico: the tables extracted from those archives."""
    return _j(NM_CSV, name)


def co(name=''):
    """Colorado: the derived analysis tables built from ECMC."""
    return _j(CO_DIR, name)


def out(name=''):
    """A result table or figure, written beside the code."""
    return _j(ROOT, name)


def warn_on_stale_env():
    """Say so if a sibling project's variable is set in this shell.

    It no longer changes anything. A reader who sets P2_DATA expecting it to
    take effect is told explicitly that it is ignored.
    """
    stale = [v for v in ('P2_DATA', 'NM_DATA', 'OH_DATA', 'CO_DATA')
             if os.environ.get(v)]
    if stale:
        print('note: %s set in the environment and IGNORED -- this project '
              'reads only %s' % (', '.join(stale), DATA))
    return stale


def check(verbose=True):
    """Report which expected inputs are present. Run this first if a script
    cannot find something; it says what is missing rather than which line
    threw."""
    want = [
        ('Pennsylvania', pa('P2_wells_with_logs.csv')),
        ('Ohio', oh('oh_analysis.csv')),
        ('New Mexico', nmcsv('nm_well_summary.csv')),
        ('New Mexico, well history', nmcsv('wellhistory.csv')),
        ('Colorado', co('co_analysis.csv')),
    ]
    warn_on_stale_env()
    missing = []
    for label, path in want:
        ok = os.path.exists(path)
        if not ok:
            missing.append((label, path))
        if verbose:
            print('%-26s %-6s %s' % (label, 'ok' if ok else 'MISSING', path))
    if verbose:
        print('\nroot: %s' % ROOT)
    return missing


if __name__ == '__main__':
    import sys
    sys.exit(1 if check() else 0)
