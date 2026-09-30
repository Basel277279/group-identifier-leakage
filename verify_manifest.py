"""Check every file in this archive against MANIFEST.sha256.

    python3 verify_manifest.py          check, and print only what is wrong
    python3 verify_manifest.py -v       print every file and its verdict

WHY THIS EXISTS RATHER THAN `sha256sum -c`
    `sha256sum` is a GNU coreutils program. It is not present on a stock Windows
    machine, and Windows has no batch equivalent: `certutil -hashfile` does one
    file at a time and prints a different format, and `Get-FileHash` needs a
    PowerShell loop written by hand. A reader on Windows therefore could not
    check this archive at all, which defeats the point of shipping a checksum
    file. This does the same job with the Python standard library, so it runs
    wherever the rest of the code runs.

WHAT IT CHECKS, AND THE ONE THING `sha256sum -c` DOES NOT
    * every file listed in MANIFEST.sha256 exists and hashes to the recorded
      value -- the same check `sha256sum -c` performs
    * no file in the archive is ABSENT from the manifest. An extra, unlisted
      file is how a stray copy, an editor backup or a machine-specific
      `__pycache__` gets published, and a checksum list cannot notice it by
      construction: it only knows what it lists.

    Exits 0 only when both hold.

RUN IT BEFORE YOU RUN ANYTHING ELSE
    `run_all.sh` is SUPPOSED to overwrite things: it rewrites every result CSV,
    regenerates `DATA_DICTIONARY.md` and redraws all ten figure files, and it
    drops a `log_<script>.out` beside each script it runs. So this check is
    meaningful on a freshly unpacked archive and not after a reproduction run --
    hashes that differ afterwards may mean the reproduction differed, which is
    interesting, or merely that the file was rewritten identically, which is
    not. The run logs are recognised and reported separately from extras that
    have no such explanation.

A NOTE ON IMAGES
    If the five PNGs fail here by a few kilobytes each while everything else
    passes, they have most likely been rewritten in transit by something that
    embeds provenance metadata -- a C2PA `caBX` chunk, for instance, which some
    desktop applications add to any image they write. The pixels are untouched,
    but the bytes are not the bytes that were hashed. Rebuild the archive with
    `make_deposit.py` on the machine that holds it rather than copying it in.
"""
import fnmatch
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, 'MANIFEST.sha256')
# Not hashed: the manifest cannot contain its own hash. Nothing else is exempt.
SELF = {'MANIFEST.sha256'}
# Files a reproduction run leaves behind. These are unlisted by design -- they
# are output, not archive -- so they are reported apart from extras that have no
# explanation, instead of twenty log files reading as twenty tampered files.
RUN_ARTIFACTS = ('log_*.out', 'v_*.out', '*.zip', 'deposit/*')
# Unlisted for a different reason: not output, but input the reader was told to
# fetch. The code repository ships without the derived state tables -- they are
# research data, they live at the Zenodo DOI, and README.md says to unpack them
# here -- so a reader who follows that instruction must not then be told that a
# hundred megabytes of legitimately downloaded data means the tree is not
# verified. Reported apart from run output because calling a downloaded table
# "left by a reproduction run" would be a plainly wrong explanation.
DOWNLOADED = ('Data/*',)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read_manifest(path):
    """`<64 hex>  <relative/path>` per line, as sha256sum writes it."""
    rows = []
    for n, line in enumerate(open(path, encoding='utf-8'), 1):
        # Strip \r as well as \n. Python's text mode already folds CRLF to \n on
        # every platform, so this is belt and braces rather than a fix -- but a
        # manifest can also arrive with literal CR through a checkout or an
        # archive tool that rewrote line endings, and then the \r would be read
        # as the last character of the file name and every line would fail in an
        # archive where nothing is wrong.
        line = line.rstrip('\r\n')
        if not line.strip():
            continue
        parts = line.split('  ', 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise SystemExit('MANIFEST.sha256 line %d is not '
                             '"<sha256>  <path>": %r' % (n, line))
        rows.append((parts[0].lower(), parts[1]))
    return rows


def walk_archive():
    found = set()
    for dirpath, dirnames, files in os.walk(HERE):
        # `.git` is version-control bookkeeping, not archive content. Without
        # this line a clone of the code repository reports several hundred
        # objects under .git/ as files "NOT in the manifest", and the check
        # that exists to find a stray file fails on every clone instead.
        dirnames[:] = [d for d in dirnames
                       if d not in ('__pycache__', '.git')]
        for f in files:
            rel = os.path.relpath(os.path.join(dirpath, f), HERE)
            found.add(rel.replace(os.sep, '/'))
    return found


def main(argv):
    verbose = '-v' in argv
    if not os.path.exists(MANIFEST):
        raise SystemExit('No MANIFEST.sha256 beside this script. Run it from '
                         'inside the archive.')

    rows = read_manifest(MANIFEST)
    ok, failed, missing = [], [], []
    for want, rel in rows:
        full = os.path.join(HERE, rel.replace('/', os.sep))
        if not os.path.exists(full):
            missing.append(rel)
            continue
        got = sha256(full)
        if got == want:
            ok.append(rel)
            if verbose:
                print('   ok       %s' % rel)
        else:
            failed.append((rel, os.path.getsize(full), want, got))

    listed = {rel for _, rel in rows} | SELF
    unlisted = sorted(walk_archive() - listed)
    run_left = [r for r in unlisted
                if any(fnmatch.fnmatch(r, p) for p in RUN_ARTIFACTS)]
    fetched = [r for r in unlisted
               if r not in set(run_left)
               and any(fnmatch.fnmatch(r, p) for p in DOWNLOADED)]
    extra = [r for r in unlisted
             if r not in set(run_left) and r not in set(fetched)]

    print('%d files listed in MANIFEST.sha256' % len(rows))
    print('  %d OK' % len(ok))

    if failed:
        print('\n%d FAILED -- the file is there but its bytes are not the '
              'bytes that were hashed:' % len(failed))
        for rel, size, want, got in failed:
            print('  %s  (%d bytes now)' % (rel, size))
            print('      recorded %s' % want)
            print('      found    %s' % got)
    if missing:
        print('\n%d MISSING from the archive:' % len(missing))
        for rel in missing:
            print('  ' + rel)
    if extra:
        print('\n%d file(s) in the archive but NOT in the manifest, and not '
              'something a reproduction run explains. Each is either something '
              'that should not be published or a sign the manifest is stale:'
              % len(extra))
        for rel in extra:
            print('  ' + rel)
    if fetched:
        print('\n%d file(s) under Data/. Those are the derived state tables, '
              'which are archived at the DOI rather than shipped with the code, '
              'so they are not in the manifest by design. Not a fault:'
              % len(fetched))
        for rel in fetched:
            print('  ' + rel)
    if run_left:
        print('\n%d file(s) left by a reproduction run (`run_all.sh` writes one '
              'log per script). Not a fault, and not part of the archive:'
              % len(run_left))
        for rel in run_left:
            print('  ' + rel)
        if failed:
            print('  -- and since this archive has been run in, the failures '
                  'above may be regenerated files rather than altered ones.')

    if failed or missing or extra:
        print('\nNOT VERIFIED. Rebuild with `make_deposit.py` on the machine '
              'that holds the files, or investigate the entries above.')
        return 1
    print('\nVERIFIED: every listed file is present and unchanged, and the '
          'archive contains nothing the manifest does not list.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
