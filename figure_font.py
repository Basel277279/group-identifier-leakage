"""Resolve the figure typeface, and fail if no acceptable face is installed.

    import figure_font
    plt.rcParams.update({'font.family': figure_font.FAMILY, ...})

RATIONALE

    matplotlib does not treat a missing font as an error. It emits a warning
    on stderr and substitutes DejaVu Sans. Two consequences make that
    unacceptable here.

    DejaVu Sans is not among the faces the journal accepts -- "Arial (or
    Helvetica), Courier, Symbol, Times (or Times New Roman)" -- so artwork
    produced on a machine without the intended face is not submittable, and
    nothing in the output indicates it.

    It also changes the figure. The figure scripts save with
    `bbox_inches='tight'`, so the canvas is sized to the rendered ink, and
    DejaVu's metrics differ from Liberation Sans's: substituting it makes
    Figure 4 7481 x 3577 px rather than 7484 x 3662, about two millimetres
    shorter at 1000 dpi.

    The face is therefore resolved once, here, with matplotlib's fallback
    disabled, and a machine with none of the acceptable faces is told to
    install one rather than given a silently altered figure.

RESOLUTION ORDER

    Liberation Sans first: the deposited figures were drawn with it, so a
    machine that has it reproduces them exactly. Arial second: it is present
    on every Windows and macOS installation, it is the face the journal
    names, and Liberation Sans is metric-compatible with it. The remainder
    are the other metric-compatible or accepted faces.

    A machine resolving to anything other than Liberation Sans draws the same
    figure to within the glyph outlines, not to the pixel.
    `reproduce_figures.py` reports the resolved face so that any difference is
    attributable.

INSTALLATION

    Liberation Sans is free and openly licensed.

      Debian, Ubuntu    apt install fonts-liberation
      Fedora, RHEL      dnf install liberation-sans-fonts
      macOS             brew install --cask font-liberation
      Windows           the .ttf files from
                        github.com/liberationfonts/liberation-fonts, or Arial,
                        which Windows provides and this module accepts
"""
import sys

from matplotlib import font_manager

# In preference order. Arial first: it is the face the journal names, it is
# what the submitted artwork is rendered in, and it is present on every
# Windows and macOS installation. The rest are metric-compatible substitutes
# for a reader who does not have it; Liberation Sans is free and is the one
# to install on Linux.
CANDIDATES = ('Arial', 'Helvetica', 'Liberation Sans', 'Nimbus Sans',
              'Arimo', 'Helvetica Neue')

# Monospace, for the mathtext tt variant. Courier is on the journal's list;
# the others are metric-compatible with it.
MONO_CANDIDATES = ('Courier New', 'Courier', 'Liberation Mono', 'Cousine',
                   'Nimbus Mono PS', 'DejaVu Sans Mono')

# The face the deposited figures were rendered in. Any other face reproduces
# the same figure but not the same pixels.
REFERENCE = 'Arial'


def _resolve(candidates=CANDIDATES):
    for name in candidates:
        try:
            # fallback_to_default=False raises on a missing face instead of
            # substituting one, which is the purpose of this module.
            path = font_manager.findfont(
                font_manager.FontProperties(family=name),
                fallback_to_default=False)
        except Exception:                                    # noqa: BLE001
            continue
        # Some matplotlib versions still return the default file for a name
        # they did not match, so the resolved path is checked as well.
        if 'DejaVu' in path and not name.startswith('DejaVu'):
            continue
        return name, path
    return None, None


FAMILY, PATH = _resolve()
MONO, MONO_PATH = _resolve(MONO_CANDIDATES)
if MONO is None:                       # every platform ships some monospace
    MONO = 'monospace'

if FAMILY is None:
    sys.exit(
        'No acceptable figure typeface is installed.\n'
        '\n'
        'Tried, in order: %s\n'
        '\n'
        'matplotlib would substitute DejaVu Sans, which this journal does not\n'
        'accept and which changes the dimensions of every figure. Install one\n'
        'of the faces above:\n'
        '\n'
        '  Debian, Ubuntu    apt install fonts-liberation\n'
        '  Fedora, RHEL      dnf install liberation-sans-fonts\n'
        '  macOS             brew install --cask font-liberation\n'
        '  Windows           Arial is normally present; if this message\n'
        '                    appears there, refresh the matplotlib font cache\n'
        '                    with: python -c "import matplotlib.font_manager '
        'as f; f._load_fontmanager(try_read_cache=False)"\n'
        % ', '.join(CANDIDATES))

if FAMILY != REFERENCE:
    sys.stderr.write(
        'note: drawing with %r; the published figures were rendered in %r,\n'
        '      which the journal names and which Windows and macOS provide.\n'
        '      %r is metric-compatible with it, so this is the same figure\n'
        '      at the same dimensions, but the glyph outlines differ and the\n'
        '      output will not match the published files pixel for pixel.\n'
        % (FAMILY, REFERENCE, FAMILY))


if __name__ == '__main__':
    print('figure typeface: %s' % FAMILY)
    print('file:            %s' % PATH)
    print('monospace:       %s' % MONO)
    print('reference:       %s%s'
          % (REFERENCE, '' if FAMILY == REFERENCE else '   (not in use here)'))
