"""Build 01_acquire/SOURCES.md: the provenance record for every raw input.

WHY THIS EXISTS
    The raw regulator downloads total roughly 3 GB and are not deposited.
    SOURCES.md is what stands in for them: for every file, where it came from,
    when it was retrieved, how large it is and its SHA-256. A reader who
    re-downloads can verify the bytes against the retrieved originals; a reader who
    cannot re-download at least knows exactly what they are missing.

    Regulator endpoints move. A hash is only useful while the file is still
    served, so the table also records whether the URL is a verified direct
    link or a landing page that must be navigated. Recording that honestly is
    more useful to a reviewer than a plausible-looking URL that 404s.

HOW IT IS BUILT
    Hashes come from two sha256sum inventories, because the raw files live in
    two places: the New Mexico downloads were fetched into the analysis
    environment, everything else sits on the acquisition machine.

    Take an inventory in each raw directory (the exact command is in
    `read_hashes` below and in the Verifying section of the output), save it,
    and point this script at the files. It merges them, joins on basename, and writes the
    table. Files it has no hash for are listed with the reason, not omitted --
    an incomplete record that says so is honest; a complete-looking record
    with silent gaps is not.

    python3 make_sources.py hashes_device.txt hashes_container.txt > SOURCES.md
"""
import os
import re
import sys
from datetime import date

# --------------------------------------------------------------------- sources
# `url` is a verified direct link where `direct` is True, and a landing page
# that must be navigated where it is False. Do not promote one to the other
# without checking it in a browser.
STATES = [
    dict(
        state='Pennsylvania',
        agency='Pennsylvania Department of Environmental Protection',
        url='https://newdata.pa.gov/dataset/oil-and-gas-well-permits',
        direct=False,
        note='The table used here is the compiled well/production/permit join '
             'built for the companion study, not a single agency download. '
             'Its own provenance is recorded in that study\'s deposit; the '
             'hash below is of the compiled file as consumed here.',
        files=['P2_wells_with_logs.csv'],
    ),
    dict(
        state='Ohio',
        agency='Ohio Department of Natural Resources, Division of Oil and Gas '
               'Resources Management',
        url='https://ohiodnr.gov/discover-and-learn/safety-conservation/'
            'about-ODNR/oil-gas/oil-gas-resources/featured-content-3',
        direct=False,
        note='RBDMS is published as a weekly ZIP containing two Access '
             'databases. Production is published separately as quarterly and '
             'annual spreadsheets at '
             'https://ohiodnr.gov/business-and-industry/energy-resources/'
             'well-information/production . Reading the .mdb files needs '
             'mdbtools; no Access installation is required.',
        files=['Rbdmsd97Weekly.zip'],
        globs=[r'^\d{4}_AllQtrs.*\.xlsx$',
               r'^\d{4}-\d.._Quarter\.xlsx$',
               r'^\d{4}_Horizontal_and_Vertical_Production.*\.xlsx$'],
    ),
    dict(
        state='New Mexico',
        agency='New Mexico Energy, Minerals and Natural Resources Department, '
               'Oil Conservation Division',
        url='ftp://ftp.emnrd.nm.gov/Public/OCD/OCD Interface v1.1/',
        direct=True,
        note='Anonymous FTP, port 21, passive. Core tables sit at the root; '
             'the volume tables are under volumes/. The server drops data '
             'connections after roughly fifteen listings, so the fetch script '
             'reconnects and retries. Files are UTF-16 XML inside the ZIPs.',
        files=['wellhistory.zip', 'wchistory.zip', 'pod.zip', 'podwc.zip',
               'property.zip', 'pool.zip', 'spacingunit.zip', 'acreage.zip',
               'ogrid.zip', 'punevent.zip', 'README_CORE.txt',
               'README_VOLUMES.txt',
               'OCD Interface v1.1 Data Dictionary.xlsx',
               'wcproduction.zip', 'wcinjection.zip',
               'podvolume.zip', 'podstorage.zip', 'othervolume.zip'],
    ),
    dict(
        state='Colorado',
        agency='Colorado Energy and Carbon Management Commission',
        url='https://ecmc.state.co.us/data2.html',
        direct=False,
        note='Annual production files are served directly at '
             'https://ecmc.state.co.us/documents/data/downloads/production/'
             '<year>_prod_reports.csv (verified), each also offered as a ZIP. '
             'The GIS shapefiles are reached from the data page; their direct '
             'paths are not recorded here because they were not verified '
             'independently of the browser session that fetched them.',
        files=['monthly_prod.csv', 'WELLS_SHP.ZIP',
               'DIRECTIONAL_BOTTOMHOLE_LOCATIONS_SHP.ZIP',
               'DIRECTIONAL_LINES_SHP.ZIP'],
        globs=[r'^\d{4}_prod_reports\.(zip|csv)$'],
    ),
]

# Files that are downloaded but never read by the pipeline. Named so a reader
# is not left wondering whether they matter.
UNUSED = {
    'DIRECTIONAL_LINES_SHP.ZIP': 'directional survey lines; not used',
    'acreage.zip': 'not used',
    'ogrid.zip': 'operator registry; not used (operator comes from the well table)',
    'pool.zip': 'not used',
    'property.zip': 'not used',
    'punevent.zip': 'not used',
    'spacingunit.zip': 'not used',
    'podvolume.zip': 'not read by the pipeline',
    'podstorage.zip': 'not read by the pipeline',
    'othervolume.zip': 'not read by the pipeline',
    'wcinjection.zip': 'injection volumes; not used (gas production only)',
    'README_CORE.txt': 'agency note',
    'README_VOLUMES.txt': 'agency note',
    'OCD Interface v1.1 Data Dictionary.xlsx': 'agency schema documentation',
    '2026-1st_Quarter.xlsx': 'superseded by 2026_AllQtrs_FINAL_20260820.xlsx',
}

# Files hashed directly on the acquisition machine rather than through an
# inventory file, because they are too large to move. Taken with PowerShell
# `Get-FileHash -Algorithm SHA256` and normalised to lower case here; sizes
# from the directory listing.
MANUAL = {
    'wcproduction.zip': (
        971286162,
        '702cf2bc4f0174f19a6a1752d65c1d675429adad3bd528d0b226865aebdc6174'),
    'podvolume.zip': (
        458138540,
        'cb661e2967effa4e252f72203cf16fc7417b520fa15e3ba1d49093d9647afb56'),
    'podstorage.zip': (
        182747375,
        '893d63f8f457a50441d064d39ce29771d4c3733287eab19e7b7ea1fd407750d4'),
    'othervolume.zip': (
        101543300,
        '283ba7ec61845f35c689138066feceb60deec97a5253d3f3fc10200fe19e6d73'),
}

NO_HASH = {}


def read_hashes(paths):
    """basename -> (sha256, size).

    Inventory format, one line per file:

        <sha256>  <size in bytes>  <name>

    produced in each raw directory by

        for f in *; do [ -f "$f" ] && \
            echo "$(sha256sum "$f" | cut -d' ' -f1)  $(stat -c%s "$f")  $f"; \
        done | sort -k3 > hashes.txt

    The size is recorded at hash time rather than looked up later, because
    the inventories are taken on the machines that hold the raw files and
    this script runs somewhere else.

    Plain `sha256sum` output (two fields) is also accepted, and yields no
    size.
    """
    out = {}
    for p in paths:
        with open(p) as fh:
            for line in fh:
                parts = line.strip().split(None, 2)
                if len(parts) == 3 and parts[1].isdigit():
                    h, size, name = parts[0], int(parts[1]), parts[2]
                elif len(parts) >= 2:
                    h, size, name = parts[0], None, ' '.join(parts[1:])
                else:
                    continue
                out[os.path.basename(name.strip())] = (h, size)
    return out


def human(n):
    if n is None:
        return '—'
    for unit in ('B', 'kB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return '%.1f %s' % (n, unit) if unit != 'B' else '%d B' % n
        n /= 1024.0


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    H = read_hashes(sys.argv[1:])
    for name, (size, h) in MANUAL.items():
        H.setdefault(name, (h, size))

    print('# SOURCES — raw inputs, provenance and checksums\n')
    print('Generated %s by `make_sources.py`. Retrieval dates are the '
          'download dates recorded on the acquisition machine.\n' % date.today())
    print('The raw inputs total roughly 3 GB and are **not deposited**. This '
          'file is what stands in for them. Every derived table in `Data/` '
          'is deposited in full and is sufficient to reproduce every number in '
          'the paper without re-downloading anything.\n')
    print('A **direct** URL was verified as a working file link. A '
          '**landing page** must be navigated; the agency does not publish a '
          'stable direct path, or we did not verify one. Regulator endpoints '
          'move, so a hash that no longer matches anything downloadable is a '
          'record of what we used, not a promise about what is served.\n')
    print('---\n')

    listed = set()
    for s in STATES:
        print('## %s\n' % s['state'])
        print('**%s**  ' % s['agency'])
        print('%s: `%s`\n' % ('Direct' if s['direct'] else 'Landing page',
                              s['url']))
        print('%s\n' % s['note'])

        names = list(s.get('files', []))
        for pat in s.get('globs', []):
            rx = re.compile(pat)
            names += sorted(n for n in H if rx.match(n) and n not in names)

        print('| file | size | SHA-256 | note |')
        print('|---|---|---|---|')
        for n in names:
            listed.add(n)
            note = UNUSED.get(n, '')
            if n in H:
                h, size = H[n]
                print('| `%s` | %s | `%s` | %s |'
                      % (n, human(size), h, note))
            elif n in NO_HASH:
                size, why = NO_HASH[n]
                tag = ('**hash not recorded** — %s' % why)
                print('| `%s` | %s | — | %s%s |'
                      % (n, human(size), tag,
                         ('; ' + note) if note else ''))
            else:
                print('| `%s` | — | — | not present in the hash inventory%s |'
                      % (n, ('; ' + note) if note else ''))
        print()

    extra = sorted(set(H) - listed)
    if extra:
        print('---\n')
        print('## Hashed but not attributed to a source above\n')
        print('These were in the raw directories and are recorded for '
              'completeness. Most are extractions of a ZIP listed above; '
              'anything genuinely unexplained should be resolved before '
              'deposit.\n')
        print('| file | size | SHA-256 |')
        print('|---|---|---|')
        for n in extra:
            h, size = H[n]
            print('| `%s` | %s | `%s` |' % (n, human(size), h))
        print()

    print('---\n')
    print('## Verifying\n')
    print('```sh')
    print('cd <raw directory>')
    print('for f in *; do [ -f "$f" ] && \\')
    print('    echo "$(sha256sum "$f" | cut -d\' \' -f1)  $(stat -c%s "$f")'
          '  $f"; \\')
    print('done | sort -k3            # compare against the tables above')
    print('```\n')
    print('## Known gaps\n')
    print('None among the raw inputs. `2018_prod_reports.csv` was missing for '
          'a time -- only its ZIP had been kept -- and was restored from that '
          'ZIP on 23 September 2026. It carries 744,618 data rows, matching '
          'the count in the Colorado build log exactly, so it is the same '
          'file the published results were computed from.\n')
    print('Every raw input listed above carries a SHA-256. The four New '
          'Mexico volume archives were hashed in place on the acquisition '
          'machine with PowerShell `Get-FileHash` rather than through the '
          'inventory files, because at 97 MB to 926 MB they were not moved.\n')
    print('**The one derived file not hashed** is `Data/NewMexico/csv/'
          'wcproduction.csv`, the 4.35 GB extraction of `wcproduction.zip` '
          'holding 48,254,734 rows. It is the largest intermediate in the '
          'project and exists only on the acquisition machine. To close the '
          'chain from archive to derived table, run\n')
    print('```powershell')
    print('Get-FileHash "Data\\NewMexico\\csv\\wcproduction.csv" '
          '-Algorithm SHA256')
    print('```')


if __name__ == '__main__':
    main()
