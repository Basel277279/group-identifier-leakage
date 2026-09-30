"""Paper 3, Figure 1: how well the pad is recovered from coordinates alone.

Reads recovery_sweep.csv. Two panels, one per state with a published pad
register. Each shows pairwise F1 against the register as the clustering radius
varies, for distance alone and for distance plus each of the two extra fields a
practitioner would naturally add.

The point of the figure is that the extra fields do not help and in Ohio hurt:
they split pads that changed operator or were drilled out over several years.
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

COL = {'distance': '#803b53', '+ operator': '#d0750a', '+ 3-yr spud': '#0099e0'}
MARK = {'distance': 'o', '+ operator': 's', '+ 3-yr spud': '^'}
NAME = {'distance': 'distance only', '+ operator': '+ same operator',
        '+ 3-yr spud': '+ 3-year spud window'}
INK, MUTED, GRID = '#1a1d21', '#5b6169', '#dfe2e6'

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


d = pd.read_csv('recovery_sweep.csv')
states = ['Pennsylvania', 'Ohio']
fig, axes = plt.subplots(1, 2, figsize=(7.48, 3.2), dpi=200, sharey=True)

for ax, st in zip(axes, states):
    s = d[d.state == st]
    # distance is drawn as a wide halo beneath the others: in Pennsylvania the
    # operator constraint tracks it to within 0.0006 F1 at every radius and
    # would hide it completely if both were drawn at the same width
    for c in ('distance', '+ operator', '+ 3-yr spud'):
        sub = s[s.constraint == c].sort_values('radius_m')
        wide = c == 'distance'
        ax.plot(sub.radius_m, sub.f1, color=COL[c],
                lw=4.0 if wide else 1.7, alpha=0.5 if wide else 1.0,
                solid_capstyle='round', zorder=4 if wide else 5)
        ax.plot(sub.radius_m, sub.f1, color=COL[c], lw=0, marker=MARK[c],
                ms=4.4, markeredgecolor='white', markeredgewidth=0.8,
                label=NAME[c], zorder=6 if wide else 5)
    # Pennsylvania ties at 150 m and 200 m; take the SMALLEST radius that
    # reaches the maximum, so the marked point is the 150 m the paper uses
    # rather than an arbitrary pick from the tie.
    dist = s[s.constraint == 'distance']
    best = dist[dist.f1 >= dist.f1.max() - 1e-12].sort_values('radius_m').iloc[0]
    ax.scatter([best.radius_m], [best.f1], s=95, facecolors='none',
               edgecolors=COL['distance'], lw=1.1, zorder=6)
    ax.annotate('F1 %.4f\nat %d m' % (best.f1, best.radius_m),
                (best.radius_m, best.f1), xytext=(0, -30),
                textcoords='offset points', ha='center', va='top',
                fontsize=7.8, color=COL['distance'], linespacing=1.4)
    ax.set_xscale('log')
    ax.set_xticks([25, 50, 100, 200, 500, 1000])
    ax.set_xticklabels(['25', '50', '100', '200', '500', '1000'])
    ax.set_xlim(20, 1300)
    ax.set_ylim(0.58, 1.02)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, lw=0.5)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    if st == 'Pennsylvania':
        ax.annotate('the operator constraint is\nindistinguishable from\ndistance alone here',
                    (27, 0.80), ha='left', va='top', fontsize=7.8,
                    color=MUTED, linespacing=1.5)
    n = int(s.pads_true.iloc[0])
    # Panel identifier, not a title: the state and its register size. The
    # claim the panel makes is the caption's job.
    ax.set_title('%s\n%s published pads' % (st, format(n, ',')),
                 loc='left', fontsize=8.5,
                 fontweight='bold', pad=8, linespacing=1.4)
    ax.set_xlabel('clustering radius (m)', labelpad=5)

axes[0].set_ylabel('agreement with the published register\n(pairwise F1)',
                   labelpad=6, linespacing=1.4)
axes[1].legend(frameon=False, fontsize=7.8, loc='lower left',
               handlelength=2.0, labelspacing=0.4, borderaxespad=0.3)

save(fig, 'Fig1_recovery', 190.0)
for st in states:
    s = d[(d.state == st) & (d.constraint == 'distance')]
    s = s[s.f1 >= s.f1.max() - 1e-12].sort_values('radius_m')
    tie = '' if len(s) == 1 else ' (tied to %d m)' % s.radius_m.iloc[-1]
    r = s.iloc[0]
    print('%-14s best F1 %.3f at %d m%s, recall %.3f, %.1f%% of pads exact'
          % (st, r.f1, r.radius_m, tie, r.recall, 100*r.exact))
