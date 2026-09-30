"""Paper 3, Figure 3: validation inflation against the grouping radius.

Reads radius_sweep.csv (10 m - 10 km, three states, with a size-matched
placebo at every radius) and radius_fine.csv (1 - 20 m, the two states with a
published pad register) and writes Fig3_radius.pdf / .png.

WHAT THE FIGURE HAS TO SHOW
    three regimes and the boundaries between them --
      < 3 m     clusters are singletons, so the grouping IS the random split
      3 - 15 m  the whole pad effect appears; this is wellhead spacing
      20 m - 300 m  flat: no further dependence to remove (<=0.017 in every state)
      > 3 km    a different regime, and partly a group-size artefact

    The flat middle is the most persuasive part, so the x axis is logarithmic
    and the regimes are shaded behind the data rather than described in a
    caption.

    Points beyond the y limit are drawn at the top with their true value
    printed, rather than rescaling the axis and flattening everything that
    matters.

    python make_figure3.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figure_font
import p3_paths as P
# This script reads its data and writes its artwork by bare relative name.
# Anchoring the working directory to the project root is what makes
# `python3 make_figureN.py` behave the same from any directory, which is the
# contract p3_paths.py states.
os.chdir(P.ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

PAL = {'Pennsylvania': '#803b53', 'Ohio': '#d0750a',
       'New Mexico': '#0099e0', 'placebo': '#767c84'}
MARK = {'Pennsylvania': 'o', 'Ohio': 's', 'New Mexico': '^'}
INK, MUTED, GRID = '#1a1d21', '#5b6169', '#dfe2e6'
BAND = '#f2f4f6'
YMAX = 0.20

plt.rcParams.update({
    # Elsevier's artwork instructions list Arial, Courier, Times New Roman
    # and Symbol, "or fonts that look similar". `figure_font` resolves Arial
    # where it is installed and a metric-compatible substitute otherwise, and
    # refuses to draw if neither is available. Every mathtext variant is
    # pointed at the same family so that $R^2$ in an axis label does not
    # arrive in a different typeface from the label around it.
    'font.family': figure_font.FAMILY, 'font.size': 8,
    'mathtext.fontset': 'custom', 'mathtext.rm': figure_font.FAMILY,
    'mathtext.it': figure_font.FAMILY + ':italic',
    'mathtext.bf': figure_font.FAMILY + ':bold',
    'mathtext.cal': figure_font.FAMILY + ':italic',
    'mathtext.sf': figure_font.FAMILY, 'mathtext.tt': figure_font.MONO,
    'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'text.color': INK,
    'xtick.color': MUTED, 'ytick.color': MUTED,
    'axes.linewidth': 0.6, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'savefig.bbox': 'tight',
    # matplotlib's default of 0.1 in adds 5.08 mm to the saved width, which
    # is more margin than a journal figure needs and makes every scale
    # derived from the tight bbox -- the dpi below, and
    # `check_figure_text.py`'s font-size check -- too generous. Zero is the
    # other extreme: the bounding box is the outermost ink, so the axis
    # labels sit flush against the edge of the file with no white space at
    # all. 0.05 in is 1.27 mm on each side, enough to separate the labels
    # from the edge and small enough that the text still clears the 7 pt
    # floor by a margin `check_figure_text.py` measures on every run.
    'savefig.pad_inches': 0.05,
})


def fmt(v, nd=2):
    """A value label with the same minus sign the axis ticks use.

    matplotlib draws a Unicode MINUS SIGN (U+2212) on tick labels, so a value
    label written with an ASCII hyphen puts two different minus glyphs in one
    panel.
    """
    return ('%.*f' % (nd, v)).replace('-', '\u2212')

def save(fig, stem, target_mm):
    """Write the PDF and a PNG that is at least 1000 dpi at the printed width.

    Computers & Geosciences asks for bitmapped line drawings at 3543 px for a
    90 mm single column and 7480 px for a 190 mm full page -- 1000 dpi at final
    size. `savefig.bbox='tight'` crops the unused margin, so the saved image is
    narrower than the figsize and a fixed dpi would undershoot; the dpi is
    therefore derived from the bounding box.

    The bounding box is then CHECKED rather than trusted. `get_tightbbox` and
    the box `savefig` recomputes can differ by a per cent, which is enough to
    land a nominally compliant figure a few dozen pixels under the minimum, so
    the written file is measured and rewritten at a corrected dpi if it is
    short. The printed line reports the width of the file on disk.
    """
    import math
    import struct
    need_px = int(math.ceil(1000.0 * target_mm / 25.4))

    def png_width(path):
        with open(path, 'rb') as fh:
            head = fh.read(24)
        return struct.unpack('>I', head[16:20])[0]

    fig.canvas.draw()
    bb = fig.get_tightbbox(fig.canvas.get_renderer())
    dpi = math.ceil(need_px / bb.width)
    fig.savefig(stem + '.pdf')
    fig.savefig(stem + '.png', dpi=dpi)
    got = png_width(stem + '.png')
    if got < need_px:
        dpi = int(math.ceil(dpi * need_px / float(got))) + 1
        fig.savefig(stem + '.png', dpi=dpi)
        got = png_width(stem + '.png')
    assert got >= need_px, '%s.png is %d px, needs %d' % (stem, got, need_px)
    print('wrote %s.pdf and %s.png (%d dpi, %d px wide, >=1000 dpi at %.0f mm)'
          % (stem, stem, dpi, got, target_mm))



def load():
    sw = pd.read_csv('radius_sweep.csv')
    fi = pd.read_csv('radius_fine.csv')
    reg = sw[sw.grouping == 'pad register'][['state', 'inflation']] \
        .set_index('state').inflation.to_dict()
    sw = sw[sw.radius_m > 0]
    fi = fi[fi.radius_m > 0]
    # the fine run is authoritative below 25 m, the sweep above it
    fi = fi[fi.radius_m <= 20]
    sw = sw[sw.radius_m >= 25]
    keep = ['state', 'radius_m', 'inflation']
    d = pd.concat([fi[keep], sw[keep]], ignore_index=True)
    plac = pd.read_csv('radius_sweep.csv')
    plac = plac[plac.radius_m > 0].copy()
    ref = pd.read_csv('radius_sweep.csv')
    rnd = ref[ref.grouping == 'random'].set_index('state').score.to_dict()
    plac['placebo_infl'] = plac.state.map(rnd) - plac.placebo
    return d.sort_values(['state', 'radius_m']), reg, plac


def main():
    d, reg, plac = load()
    fig, ax = plt.subplots(figsize=(5.51, 3.7), dpi=200)

    for lo, hi in ((0.9, 3.2), (16, 320)):
        ax.axvspan(lo, hi, color=BAND, zorder=0)
    ax.axhline(0, color=MUTED, lw=0.7, zorder=1)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, lw=0.5, zorder=0)
    for s_ in ('top', 'right'):
        ax.spines[s_].set_visible(False)

    for x, t in [(1.75, 'grouping is the\nrandom split'),
                 (7.2, 'pad\nscale'),
                 (72, 'flat across a factor of fifteen'),
                 ]:
        ax.annotate(t, (x, YMAX * 0.99), ha='center', va='top', fontsize=7,
                    color=MUTED, linespacing=1.35, zorder=2)

    ax.annotate('groups grow;\nregional regime', (3000, 0.055), ha='center',
                va='center', fontsize=7, color=MUTED, linespacing=1.35)

    ax.scatter(plac.radius_m, plac.placebo_infl, s=9, color=PAL['placebo'],
               zorder=3, linewidths=0)

    # off-scale labels are staggered so the 3 km and 10 km stacks stay legible
    OFF = {'Pennsylvania': (-11, 3), 'Ohio': (0, 13), 'New Mexico': (11, 23)}
    handles = []
    for state in ('Pennsylvania', 'Ohio', 'New Mexico'):
        sub = d[d.state == state].sort_values('radius_m')
        if sub.empty:
            continue
        x = sub.radius_m.to_numpy(); y = sub.inflation.to_numpy()
        vis = np.minimum(y, YMAX - 0.012)
        ln, = ax.plot(x, vis, color=PAL[state], lw=1.8, marker=MARK[state],
                      ms=4.6, markeredgecolor='white', markeredgewidth=0.8,
                      zorder=5, clip_on=False, label=state)
        handles.append(ln)
        for xi, yi in zip(x, y):
            if yi > YMAX - 0.012:
                ax.annotate(fmt(yi, 3), (xi, YMAX - 0.012), xytext=OFF[state],
                            textcoords='offset points', ha='center',
                            fontsize=7, color=PAL[state], fontweight='bold',
                            annotation_clip=False)
        if state in reg:
            ax.plot([3.2, 320], [reg[state]] * 2, color=PAL[state], lw=1.0,
                    ls=(0, (5, 3)), zorder=4, alpha=0.8)

    handles.append(Line2D([], [], color=PAL['placebo'], marker='o', ms=3.4,
                          lw=0, label='placebo (size-matched, random)'))
    handles.append(Line2D([], [], color=MUTED, lw=1.0, ls=(0, (5, 3)),
                          label='published pad register'))
    # Two columns, upper left, below the regime labels and above the highest
    # curve in that x-span (Ohio, 0.124 at 100 m). One column at this width is
    # four rows deep and reaches down into the data.
    ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(0.012, 0.87),
              frameon=False, fontsize=7, handlelength=2.0, labelspacing=0.45,
              ncol=2, columnspacing=1.4, borderaxespad=0.0)

    ax.set_xscale('log')
    ax.set_xlim(0.55, 16000)
    ax.set_ylim(-0.035, YMAX)
    ax.set_xticks([1, 3, 10, 30, 100, 300, 1000, 3000, 10000])
    ax.set_xticklabels(['1 m', '3 m', '10 m', '30 m', '100 m', '300 m',
                        '1 km', '3 km', '10 km'])
    ax.set_yticks(np.arange(0, 0.21, 0.05))
    ax.set_xlabel('radius used to group wells', labelpad=6)
    ax.set_ylabel('validation inflation\n(random $R^2$ $-$ grouped $R^2$)',
                  labelpad=6, linespacing=1.4)
    # No title in the artwork — see make_figure2.py.

    save(fig, 'Fig3_radius', 140.0)
    print(d.pivot_table(index='radius_m', columns='state',
                        values='inflation').round(3).to_string())


if __name__ == '__main__':
    main()
