"""Paper 3, Figure 4: the leak travels through covariates, not through the
coordinates, and one ordinary covariate can carry it alone.

Reads fig5_data.csv (written by fig5_compute.py) and writes
Fig4_mechanism.pdf / .png.

WHAT THE FIGURE HAS TO SHOW
    (a) A practitioner who suspects location leakage and drops lat/lon does
        not fix it. In three of four states it gets worse -- sixfold in Ohio.
        Drawn as a move, not as two bars, because the direction IS the result:
        the arrow points right in three states and left in one.

    (b) Why. Ground elevation, used alone, scores 0.408 under a random split
        in Ohio and -0.357 when pad-mates are withheld. A covariate that is
        surveyed once per surface location is a pad label, and the random
        split pays for reciting it. The zero rule is the reference: a mark
        left of it means the covariate carries no transferable information at
        all.

    The two panels share a state order and a colour, so a row is one state
    read across. Rows are ordered by panel (b), largest first.

    python3 make_figure4.py
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
       'New Mexico': '#0099e0', 'Colorado': '#3c1ba6'}
MARK = {'Pennsylvania': 'o', 'Ohio': 's', 'New Mexico': '^', 'Colorado': 'D'}
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



def frame(ax):
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color=GRID, lw=0.5, zorder=0)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis='y', length=0)


def main():
    d = pd.read_csv('fig5_data.csv')
    d = d.sort_values('elev_infl', ascending=True).reset_index(drop=True)
    ypos = np.arange(len(d))

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.48, 3.15), dpi=200,
                               gridspec_kw={'width_ratios': [1.0, 1.08],
                                            'wspace': 0.30})
    YLO, YHI = -0.98, len(d) - 0.35
    GAP = 0.022          # data-space clearance between a mark and its label

    def ends(ax, xa, xb, i, c, bold_is):
        """Label both ends of a span, always outside it, so they never touch.

        `bold_is` is the value that carries the result -- it gets the state
        colour and weight wherever it happens to sit; the reference value is
        muted. Position therefore encodes only magnitude, never meaning.
        """
        lo, hi = (xa, xb) if xa <= xb else (xb, xa)
        for x, side in ((lo, 'right'), (hi, 'left')):
            strong = abs(x - bold_is) < 1e-12
            ax.annotate(fmt(x, 3),
                        (x - GAP if side == 'right' else x + GAP, i),
                        va='center', ha=side,
                        fontsize=8.0 if strong else 7.8,
                        fontweight='bold' if strong else 'normal',
                        color=c if strong else MUTED,
                        bbox=dict(boxstyle='square,pad=0.06', fc='white',
                                  ec='none'), zorder=6)

    # ---- (a) full features -> no coordinates -------------------------------
    frame(a)
    a.axvline(0, color=MUTED, lw=0.7, zorder=1)
    for i, r in d.iterrows():
        c = PAL[r.state]
        x0, x1 = r.full_infl, r.nocoord_infl
        a.annotate('', xy=(x1, i), xytext=(x0, i),
                   arrowprops=dict(arrowstyle='-|>,head_width=0.22,head_length=0.5',
                                   color=c, lw=1.6, shrinkA=3.2, shrinkB=0),
                   zorder=4)
        a.plot([x0], [i], marker=MARK[r.state], ms=5.2, color='white',
               markeredgecolor=c, markeredgewidth=1.5, zorder=5)
        ends(a, x0, x1, i, c, x1)
    a.set_yticks(ypos)
    a.set_yticklabels(d.state)
    a.set_ylim(YLO, YHI)
    a.set_xlim(-0.145, 0.80)
    a.set_xticks(np.arange(0, 0.81, 0.2))
    a.set_xlabel('validation inflation\n(random $R^2$ $-$ pad-grouped $R^2$)',
                 labelpad=5, linespacing=1.4)
    # Panel letter and a bare label only. The claim each panel makes is the
    # caption's job; a sentence here would repeat it above the same figure.
    a.set_title('a', loc='left', fontsize=10, fontweight='bold', pad=10)
    a.legend(handles=[
        Line2D([], [], color=MUTED, marker='o', ms=5.2, lw=0, mfc='white',
               mec=MUTED, mew=1.3, label='all features'),
        Line2D([], [], color=MUTED, lw=1.6, marker='>', ms=4.4, mec=MUTED,
               mfc=MUTED, markevery=[-1], label='coordinates removed')],
        loc='lower center', bbox_to_anchor=(0.5, 0.025), frameon=False,
        fontsize=7.8, handlelength=2.0, labelspacing=0.35, ncol=2,
        columnspacing=1.4, borderaxespad=0.0)

    # ---- (b) elevation alone ------------------------------------------------
    frame(b)
    b.axvline(0, color=INK, lw=0.9, zorder=2)
    b.annotate('$\\leftarrow$ worse than predicting the mean',
               (-0.02, YHI - 0.10), ha='right', va='top', fontsize=7.8,
               color=MUTED)
    for i, r in d.iterrows():
        c = PAL[r.state]
        b.plot([r.elev_pad, r.elev_random], [i, i], color=c, lw=1.6,
               solid_capstyle='round', zorder=3)
        b.plot([r.elev_pad], [i], marker=MARK[r.state], ms=5.2, color='white',
               markeredgecolor=c, markeredgewidth=1.5, zorder=5)
        b.plot([r.elev_random], [i], marker=MARK[r.state], ms=5.2, color=c,
               markeredgecolor='white', markeredgewidth=0.8, zorder=5)
        ends(b, r.elev_pad, r.elev_random, i, c, r.elev_random)
        b.annotate('%.0f%% of multi-well pads share one value' % (100 * r.pad_const),
                   (0.5 * (r.elev_pad + r.elev_random), i - 0.30),
                   va='center', ha='center', fontsize=7.8, color=MUTED,
                   bbox=dict(boxstyle='square,pad=0.10', fc='white', ec='none'),
                   zorder=6)
    b.set_yticks(ypos)
    b.set_yticklabels(['' for _ in ypos])
    b.set_ylim(YLO, YHI)
    b.set_xlim(-0.62, 0.66)
    b.set_xticks([-0.4, -0.2, 0, 0.2, 0.4])
    b.set_xlabel('$R^2$ of a model given ground elevation\nand nothing else',
                 labelpad=5, linespacing=1.4)
    b.set_title('b', loc='left', fontsize=10, fontweight='bold', pad=10)
    b.legend(handles=[
        Line2D([], [], color=MUTED, marker='o', ms=5.2, lw=0, mfc=MUTED,
               mec='white', label='random split'),
        Line2D([], [], color=MUTED, marker='o', ms=5.2, lw=0, mfc='white',
               mec=MUTED, mew=1.3, label='pad-grouped')],
        loc='lower center', bbox_to_anchor=(0.5, 0.025), frameon=False,
        fontsize=7.8, handlelength=1.2, labelspacing=0.35, ncol=2,
        columnspacing=1.4, borderaxespad=0.0)

    save(fig, 'Fig4_mechanism', 190.0)
    print(d[['state', 'full_infl', 'nocoord_infl', 'elev_random', 'elev_pad',
             'pad_const', 'uniq_share']].round(3).to_string(index=False))


if __name__ == '__main__':
    main()
