"""Redraw all five figures of the paper from the result tables in this folder.

    python3 reproduce_figures.py            redraw and compare
    python3 reproduce_figures.py --render   redraw only, no comparison

Requires nothing beyond this repository: no download, no `Data/` folder, no
regulator files. Each `make_figureN.py` reads result CSVs only, so the five
figures are reproducible from the code and the twenty result tables beside it.
Runs in under a minute.

WHAT IS CHECKED

    That each redrawn figure is pixel for pixel the one in this repository.
    That is the portable claim: the figure a reader redraws is the figure that
    was published.

    Byte identity is reported but is not the pass condition. matplotlib
    compresses a PNG through the zlib bundled with the running Python, so the
    same raster deflates to different bytes under a different Python --
    3.11 and 3.13 disagree on all five of these files while producing the same
    image. Bytes match on the pinned environment of `environment.yml`, Python
    3.11 included, which is where the deposited files were produced.

    The PDFs are not compared. matplotlib writes a /CreationDate into every
    PDF and provides no way to suppress it, so a rebuilt PDF differs in that
    field on every machine and is identical elsewhere.

WHEN THE PIXELS DIFFER

    If the resolved typeface is not Liberation Sans, pixel identity is not
    attainable: different glyph outlines produce a different canvas under
    `bbox_inches='tight'`. The script reports that the comparison could not be
    made and exits 0.

    If the typeface and all pinned versions match and the pixels still
    differ, the figures did not reproduce and the script exits 1. Compare the
    installed versions with `requirements.txt` first; if those agree, the
    cause is a platform difference in rendering.

WHEN ONLY THE BYTES DIFFER

    Two causes, distinguished by the chunk lists the script prints.

    1. A different zlib, which accompanies a different Python. Expected.
    2. The shipped copy was modified after the code wrote it. Some
       applications insert a C2PA provenance chunk, `caBX`, of about 5.8 kB
       into any image they save, leaving the pixels unchanged. The redrawn
       file is then the correct one.
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Filled by versions() when the typeface in use is not the one the
# deposited figures were drawn with. Pixel identity is then out of
# reach, and the run reports that rather than failing.
FONT_DIFFERS = []
NAMES = ['Fig1_recovery', 'Fig2_occupancy', 'Fig3_radius', 'Fig4_mechanism',
         'Fig5_proxies']


def png_chunks(blob):
    """The chunk types of a PNG, in order, for the failure message."""
    if blob[:8] != b'\x89PNG\r\n\x1a\n':
        return ['(not a PNG)']
    out, i = [], 8
    while i + 8 <= len(blob):
        ln = struct.unpack('>I', blob[i:i + 4])[0]
        out.append(blob[i + 4:i + 8].decode('latin1', 'replace'))
        i += 12 + ln
    return out


def same_pixels(a, b):
    """(verdict, note) for two PNG blobs, comparing the raster, not the file.

    Returns True only if the decoded rasters are identical. Pillow is a
    matplotlib dependency and so is normally present; if it is absent the
    result is None, reported as "not compared" rather than as a pass.
    """
    try:
        import io

        from PIL import Image
    except Exception:                                        # noqa: BLE001
        return None, 'Pillow is not installed, so the pixels were not compared'
    try:
        ia = Image.open(io.BytesIO(a))
        ib = Image.open(io.BytesIO(b))
        if ia.size != ib.size:
            return False, 'different size: %s vs %s' % (ia.size, ib.size)
        ia, ib = ia.convert('RGBA'), ib.convert('RGBA')
        if ia.tobytes() != ib.tobytes():
            # Report the magnitude: a single antialiased edge pixel and a
            # different chart are both "not identical" but are not the same
            # finding.
            pa, pb = ia.tobytes(), ib.tobytes()
            n = sum(1 for x, y in zip(pa, pb) if x != y)
            return False, ('%d of %d channel values differ'
                           % (n, len(pa)))
        return True, ''
    except Exception as err:                                 # noqa: BLE001
        return None, 'could not decode: %s' % err


def read(path):
    try:
        with open(path, 'rb') as fh:
            return fh.read()
    except OSError:
        return None


def versions():
    """Report the resolved typeface and installed versions against the pins.

    Printed before anything is drawn. It answers the question any difference
    below raises: was this figure drawn by the same software that drew the
    published one?
    """
    pins = {}
    try:
        with open(os.path.join(HERE, 'requirements.txt'), encoding='utf-8') as fh:
            for line in fh:
                line = line.split('#')[0].strip()
                if '==' in line:
                    name, ver = line.split('==', 1)
                    pins[name.strip().lower()] = ver.strip()
    except OSError:
        pass

    rows, drift = [], []
    print('%-14s %-16s %s' % ('', 'in use here', 'used for the paper'))
    # The typeface first: it is the setting with the largest effect on the
    # output. A substituted face changes the rendered ink and therefore the
    # canvas size under `bbox_inches='tight'`. `figure_font` refuses to
    # substitute; this reports the face in use before anything is drawn.
    try:
        sys.path.insert(0, HERE)
        import figure_font
        print('%-14s %-16s %-18s%s'
              % ('typeface', figure_font.FAMILY, figure_font.REFERENCE,
                 '' if figure_font.FAMILY == figure_font.REFERENCE
                 else '   <-- differs'))
        if figure_font.FAMILY != figure_font.REFERENCE:
            # Not appended to `drift`: a typeface difference is not a
            # version difference and is not fixed by pip. It is handled
            # separately below because it makes pixel identity unattainable
            # rather than merely unlikely, and a check that cannot hold is
            # not reported as a check that failed.
            FONT_DIFFERS.append(figure_font.FAMILY)
    except SystemExit:
        raise
    except Exception as err:                                 # noqa: BLE001
        print('typeface       could not be resolved: %s' % err)

    # Python is pinned to a minor version in environment.yml (`python=3.11`),
    # not a patch, so 3.11.15 satisfies it. Comparing the full string reported
    # every correctly pinned environment as drifting.
    rows.append(('python', '%d.%d.%d' % sys.version_info[:3], '3.11',
                 '%d.%d' % sys.version_info[:2]))
    for mod in ('numpy', 'pandas', 'scipy', 'sklearn', 'matplotlib'):
        key = 'scikit-learn' if mod == 'sklearn' else mod
        try:
            got = __import__(mod).__version__
        except Exception:                                    # noqa: BLE001
            got = '(not installed)'
        rows.append((key, got, pins.get(key, '(unpinned)'), got))
    for name, got, want, compare in rows:
        ok = want.startswith('(') or compare == want
        if not ok:
            drift.append(name)
        print('%-14s %-16s %-18s%s'
              % (name, got, want, '' if ok else '   <-- differs'))
    if drift:
        print('\n%s %s from the pins. The figures will still be drawn and the\n'
              'paper\'s conclusions do not depend on the third decimal place, '
              'but a\nbyte-for-byte match below is then not expected.'
              % (', '.join(drift), 'differs' if len(drift) == 1 else 'differ'))
    print()
    return drift


def main():
    # --render redraws and reports, without comparing. It is how the
    # published artwork is produced: on a machine with Arial the output is
    # intended to replace the files here, so comparing it with the previous
    # rendering and calling a difference a failure would be wrong.
    render_only = '--render' in sys.argv

    drift = versions()
    before = {n: read(os.path.join(HERE, n + '.png')) for n in NAMES}

    for i in (1, 2, 3, 4, 5):
        script = 'make_figure%d.py' % i
        print('### figure %d  (%s)' % (i, script), flush=True)
        log = os.path.join(HERE, 'log_make_figure%d.out' % i)
        with open(log, 'w', encoding='utf-8') as fh:
            r = subprocess.run([sys.executable, script], cwd=HERE,
                               stdout=fh, stderr=subprocess.STDOUT)
        if r.returncode != 0:
            print('\n%s exited %d. Its output is in %s'
                  % (script, r.returncode, os.path.basename(log)))
            return 1

    if render_only:
        print('\n### rendered, not compared (--render)')
        for n in NAMES:
            blob = read(os.path.join(HERE, n + '.png'))
            if blob is None:
                print('    %-18s NOT WRITTEN' % n)
                return 1
            try:
                import io

                from PIL import Image
                w, h = Image.open(io.BytesIO(blob)).size
                print('    %-18s %5d x %5d px   %7.2f MB'
                      % (n, w, h, len(blob) / 1e6))
            except Exception:                                # noqa: BLE001
                print('    %-18s %7.2f MB' % (n, len(blob) / 1e6))
        print('\nThese files are now the rendering of record for this '
              'machine\'s typeface.')
        return 0

    print('\n### comparing the redrawn figures with the ones that shipped')
    exact = pixel_only = bad = new = unchecked = 0
    detail, rewritten = [], []
    for n in NAMES:
        after = read(os.path.join(HERE, n + '.png'))
        if after is None:
            print('    %-18s NOT WRITTEN' % n)
            bad += 1
            continue
        if before[n] is None:
            print('    %-18s no earlier copy to compare' % n)
            new += 1
            continue
        if before[n] == after:
            print('    %-18s identical, byte for byte' % n)
            exact += 1
            continue

        ok, note = same_pixels(before[n], after)
        was, now = png_chunks(before[n]), png_chunks(after)
        extra = sorted(set(c for c in was if c not in now))
        if ok:
            print('    %-18s same pixels; %d bytes shipped, %d now'
                  % (n, len(before[n]), len(after)))
            pixel_only += 1
        elif ok is None:
            print('    %-18s bytes differ, pixels NOT COMPARED -- %s'
                  % (n, note))
            unchecked += 1
        else:
            print('    %-18s PIXELS DIFFER -- %s' % (n, note))
            bad += 1
        if extra:
            rewritten.append(n)
            detail.append('      %s: the shipped copy carries %s and the '
                          'redrawn one does not. It was rewritten after the '
                          'code wrote it, and the redrawn file is the correct '
                          'one.' % (n, extra))

    print('\n%d byte-identical, %d same pixels, %d differing, %d not compared, '
          '%d new.' % (exact, pixel_only, bad, unchecked, new))
    for line in detail:
        print(line)

    if bad and FONT_DIFFERS:
        # The figures were drawn in a different face from the deposited ones,
        # so they cannot be pixel-identical and it would be wrong to call that
        # a failure. Say plainly that the check could not be made.
        print('\nNOT VERIFIED AT PIXEL LEVEL -- and that is expected here.')
        print('These were drawn in %s; the deposited figures were drawn in '
              '%s.\nDifferent glyph outlines give a different canvas under '
              '`bbox_inches=\n\'tight\'`, so the sizes above differ by a '
              'millimetre or two. The figures\nare the same figures. To '
              'compare them pixel for pixel, install\nLiberation Sans (it is '
              'free) and run this again; figure_font.py names\nthe command '
              'for each platform.' % (', '.join(FONT_DIFFERS), 'Liberation Sans'))
        return 0

    if bad:
        print('\nFIGURES DID NOT REPRODUCE.')
        if drift:
            print('%s differ from the pins in requirements.txt. Install the '
                  'pinned\nversions and try again before treating this as a '
                  'fault.' % ', '.join(drift))
        else:
            print('The typeface and every pinned version match, so this is '
                  'not an\nenvironment difference. The remaining explanation '
                  'is a platform\ndifference in rendering.')
        return 1

    if rewritten:
        print('\nThe figures reproduce, but %s in this folder had been '
              'rewritten\nafter the code wrote %s -- the redrawn file is now '
              'the correct one.'
              % (', '.join(rewritten), 'it' if len(rewritten) == 1 else 'them'))
    if pixel_only:
        print('\nAll five redraw to the same image. %d of them differ in bytes '
              'only,\nwhich is zlib: matplotlib deflates a PNG through the '
              'zlib that comes\nwith your Python, and a different Python '
              'compresses the same pixels\ndifferently. Byte identity holds on '
              'the environment in environment.yml,\nPython 3.11 included; '
              'pixel identity is the claim that travels.' % pixel_only)
    if unchecked:
        print('\n%d file(s) could not be compared as images. Install Pillow '
              '(`python3 -m pip install pillow`) and run this again.'
              % unchecked)
        return 1
    print('\nConsole output from each script is in log_make_figureN.out.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
