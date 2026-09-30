"""Paper 3, Figure 5: how far each validation scheme sits from the pad reference.

Reads proxy_compare.csv. One model, one feature set; only the partition varies.
The x axis is the difference from the pad-grouped score, so zero is correct
validation, positive is optimistic and negative is over-conservative.

Plotting the difference rather than raw R² is what makes the point legible: the
three states have very different baselines (0.562, 0.786, 0.600) but the same
pattern of errors around them.
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

PAL = {'Pennsylvania': '#803b53', 'Ohio': '#d0750a', 'New Mexico': '#0099e0'}
MARK = {'Pennsylvania': 'o', 'Ohio': 's', 'New Mexico': '^'}
INK, MUTED, GRID = '#1a1d21', '#5b6169', '#dfe2e6'
ORDER = ['random', 'spatial 10 km', 'spud year', 'spatial 25 km', 'operator']
XMIN = -0.42

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
    'xtick.color': MUTED, 'ytick.color': INK,
    'axes.linewidth': 0.6, 'xtick.major.width': 0.6, 'ytick.major.width': 0,
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


d = pd.read_csv('proxy_compare.csv')
d = d[d.scheme.isin(ORDER)]
fig, ax = plt.subplots(figsize=(5.51, 3.3), dpi=200)

ax.axvspan(XMIN, 0, color='#f5f6f8', zorder=0)
ax.axvline(0, color=INK, lw=1.1, zorder=2)
ax.set_axisbelow(True)
ax.xaxis.grid(True, color=GRID, lw=0.5, zorder=0)
for s in ('top', 'right', 'left'):
    ax.spines[s].set_visible(False)

off = {'Pennsylvania': 0.22, 'Ohio': 0.0, 'New Mexico': -0.22}
for state in ('Pennsylvania', 'Ohio', 'New Mexico'):
    s = d[d.state == state].set_index('scheme').reindex(ORDER)
    ypos = np.arange(len(ORDER))[::-1] + off[state]
    x = s.delta.to_numpy()
    xv = np.maximum(x, XMIN + 0.015)
    ax.errorbar(xv, ypos, xerr=np.where(x < XMIN + 0.015, 0, s.ci.to_numpy()),
                fmt=MARK[state], ms=5.0, color=PAL[state], ecolor=PAL[state],
                elinewidth=1.0, capsize=2.2, markeredgecolor='white',
                markeredgewidth=0.8, label=state, zorder=5, linestyle='none')
    for xi, xvi, yi in zip(x, xv, ypos):
        if xi < XMIN + 0.015:
            ax.annotate(fmt(xi, 3) + '  ', (xvi, yi), xytext=(-4, 0),
                        textcoords='offset points', ha='right', va='center',
                        fontsize=7, color=PAL[state], fontweight='bold')

ax.set_yticks(np.arange(len(ORDER))[::-1])
ax.set_yticklabels(ORDER, fontsize=8.5)
ax.set_ylim(-0.7, len(ORDER) - 0.3)
ax.set_xlim(XMIN, 0.19)
ax.set_xticks(np.arange(-0.4, 0.19, 0.1))
ax.set_xlabel('difference from pad-grouped $R^2$', labelpad=6)

ax.annotate('optimistic', (0.012, len(ORDER) - 0.55), ha='left', va='center',
            fontsize=7.5, color=INK, fontweight='bold')
ax.annotate('over-conservative', (-0.012, len(ORDER) - 0.55), ha='right',
            va='center', fontsize=7.5, color=MUTED)
ax.annotate('correct\nvalidation', (0.006, -0.62), ha='left', va='bottom',
            fontsize=7, color=INK, linespacing=1.3)

ax.legend(frameon=False, fontsize=7.5, loc='upper left',
          bbox_to_anchor=(0.012, 0.93), handletextpad=0.4, labelspacing=0.35)
# No title in the artwork — see make_figure2.py.

save(fig, 'Fig5_proxies', 140.0)
print(d.pivot_table(index='scheme', columns='state', values='delta')
      .reindex(ORDER).round(3).to_string())
