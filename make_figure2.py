"""Paper 3, Figure 2: validation-score inflation against wells per pad.

Reads fig_data.csv (one row per state x pad-size bin x seed, written by
fig_compute.py) and writes Fig2_occupancy.pdf and .png.

DESIGN NOTES
    Form: the data is a dose-response -- an ordered quantity (wells per pad)
    against a continuous effect -- so lines with markers, not bars.
    Colour: three states, one categorical scale, validated in OKLab before
    use. Worst adjacent-pair separation is dE 13.3 under deuteranopia and 15.1
    in normal vision, both above the floors. Marker shape carries identity as
    well as colour, and each line is labelled at its right end, so nothing
    depends on colour alone.
    The placebo is deliberately drawn in the same chart, in grey, so the
    control is visible rather than relegated to a table.
    One y-axis. No second scale, no twin axis.
    Error bars are 95% intervals across the ten seeds.

    python make_figure.py
"""
import json
import os

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
       'New Mexico': '#0099e0', 'Colorado': '#3c1ba6', 'placebo': '#767c84'}
MARK = {'Pennsylvania': 'o', 'Ohio': 's', 'New Mexico': '^', 'Colorado': 'D'}
TRUTH = {'Pennsylvania': 'published register',
         'Ohio': 'published register',
         'New Mexico': 'inferred, 150 m',
         'Colorado': 'inferred, 150 m'}
INK, MUTED, GRID = '#1a1d21', '#5b6169', '#dfe2e6'
LABEL_OFFSET = {'Ohio': (-2, 30, 'center'), 'Pennsylvania': (8, -26, 'left'),
                'New Mexico': (8, 2, 'left'), 'Colorado': (9, 0, 'left')}

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


# x is the mean number of wells per pad inside each bin -- a true dose axis,
# so bins that differ between states (Ohio's "6+" vs New Mexico's "6-7" and
# "8+") sit where they actually belong instead of at an arbitrary tick.


T95 = 2.262157        # t(0.975, df=9): fig_data.csv carries ten seeds per cell


def ci(v):
    """A 95% interval on the mean of the ten per-seed values.

    Student t, not the normal 1.96: with ten observations the normal quantile
    makes every bar 13% shorter than the interval the caption claims, and the
    rest of the project uses t for the same reason (`proxy_compare.py`,
    `register_vs_inferred.py`).
    """
    v = np.asarray(v, dtype=float)
    return T95 * v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0.0


def main():
    d = pd.read_csv('fig_data.csv')
    g = (d.groupby(['state', 'bin'])
           .agg(inflation=('inflation', 'mean'),
                inflation_ci=('inflation', ci),
                placebo=('placebo_effect', 'mean'),
                placebo_ci=('placebo_effect', ci),
                wells=('wells', 'first'))
           .reset_index())
    g['x'] = (d.groupby(['state', 'bin']).mean_wells_per_pad.first()
              .reindex(pd.MultiIndex.from_frame(g[['state', 'bin']])).values)
    g = g.sort_values(['state', 'x'])

    fig, ax = plt.subplots(figsize=(5.51, 3.6), dpi=200)

    ax.axhline(0, color=MUTED, lw=0.7, zorder=1)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, lw=0.5)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)

    # the placebo control, drawn in the same axes so it cannot be overlooked
    ax.errorbar(g.x, g.placebo, yerr=g.placebo_ci, fmt='o', ms=3.2,
                color=PAL['placebo'], ecolor=PAL['placebo'], elinewidth=0.8,
                capsize=2, zorder=3, linestyle='none', clip_on=False)

    for state, sub in g.groupby('state'):
        sub = sub.sort_values('x')
        ax.errorbar(sub.x, sub.inflation, yerr=sub.inflation_ci,
                    color=PAL[state], lw=2.0, marker=MARK[state],
                    markersize=5.2, markeredgecolor='white',
                    markeredgewidth=0.9, capsize=2.5, elinewidth=1.0,
                    zorder=5, clip_on=False)
        last = sub.iloc[-1]
        # Ohio's last point sits on New Mexico's line, so label it above
        dx, dy, ha = LABEL_OFFSET.get(state, (8, 0, 'left'))
        ax.annotate(state, (last.x, last.inflation),
                    xytext=(dx, dy), textcoords='offset points',
                    va='center', ha=ha, fontsize=8, color=PAL[state],
                    fontweight='bold')

    ax.annotate('placebo grouping: groups of the same sizes,\nmembership assigned at random',
                (0.995, 0.012), xycoords='axes fraction', ha='right', va='bottom',
                fontsize=7, color=PAL['placebo'], linespacing=1.4)

    # The one-well point is zero by construction, not by finding. That belongs
    # in the caption, which says it; repeating it inside the artwork would put
    # the same sentence twice on the same page.

    ax.set_xlabel('wells sharing the pad', labelpad=6)
    ax.set_ylabel('validation inflation\n(random $R^2$ $-$ pad-grouped $R^2$)',
                  labelpad=6, linespacing=1.4)
    ax.set_xticks([1, 2, 4, 6, 8, 10, 12, 14, 16, 18])
    ax.set_xlim(0.35, 21.5)
    # -0.14 so Pennsylvania's 4-5 placebo interval, which reaches -0.133, is
    # shown in full. Four of the eighteen placebo cells exclude zero -- that
    # one plus Colorado's 1, 6-7 and 12+ -- and all four are NEGATIVE, so none
    # manufactures an effect; a cropped negative bar is exactly the thing a
    # sceptical reader should be able to see. The top, 0.47, clears New
    # Mexico's 8+ upper bound of 0.453.
    ax.set_ylim(-0.14, 0.47)
    ax.set_yticks(np.arange(0, 0.45, 0.1))

    # No title in the artwork: Elsevier sets the caption below the figure, and
    # a title here would repeat its first sentence. Panel labels stay; claims
    # belong in the caption.

    save(fig, 'Fig2_occupancy', 140.0)

    print('\nplotted values')
    print(g[['state', 'bin', 'wells', 'inflation', 'inflation_ci',
             'placebo', 'placebo_ci']].round(3).to_string(index=False))


if __name__ == '__main__':
    main()
