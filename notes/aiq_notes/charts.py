"""American Inequality chart style for Substack Notes.

Matches the Datawrapper-style charts from "The Big 5 of Inequality":
Roboto, bold left-aligned headline, grey subtitle, Datawrapper blue for the
baseline series, red for the point that matters, light horizontal gridlines,
short annotations, and a source + credit footer on every chart.

Every function returns the path of a 1700px-wide PNG.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
for f in FONT_DIR.glob("Roboto-*.ttf"):
    font_manager.fontManager.addfont(str(f))

BLUE = "#1d81a2"      # Datawrapper blue: the baseline / "everyone else"
RED = "#c71e1d"       # Datawrapper red: the thing the reader should see
GREY = "#a8a8a8"      # counterfactual / context bars
INK = "#1a1a1a"       # headline
SUB = "#555555"       # subtitle
TICK = "#666666"
GRID = "#e3e3e3"
FOOT = "#888888"
CREDIT = "Chart: Jeremy Ney | americaninequality.substack.com"

DPI = 200
W_IN, H_IN = 8.5, 5.44          # 1700 x 1088 px, same as the Big 5 exports

plt.rcParams.update({
    "font.family": "Roboto",
    "font.size": 11,
    "axes.edgecolor": "#999999",
    "axes.labelcolor": TICK,
    "xtick.color": TICK,
    "ytick.color": TICK,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "svg.fonttype": "none",
})


# --------------------------------------------------------------------------
# Frame: headline, subtitle, footer
# --------------------------------------------------------------------------
def _frame(title, subtitle, source, note=None, h=H_IN, top=0.80, bottom=0.14,
           left=0.08, right=0.97):
    fig = plt.figure(figsize=(W_IN, h), dpi=DPI, facecolor="white")
    fig.text(0.045, 0.955, title, fontsize=19, fontweight="bold", color=INK, va="top")
    if subtitle:
        fig.text(0.045, 0.885, subtitle, fontsize=12, color=SUB, va="top")
    src = f"Source: {source}" + (f". {note}" if note else "")
    fig.text(0.045, 0.055, src, fontsize=8.6, color=FOOT, va="bottom")
    fig.text(0.045, 0.022, CREDIT, fontsize=8.6, color=FOOT, fontweight="bold", va="bottom")
    ax = fig.add_axes([left, bottom + 0.03, right - left, top - bottom - 0.03])
    return fig, ax


def _clean(ax, grid_axis="y"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def _save(fig, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)
    return str(out)


def _fmt(v, fmt):
    return fmt.format(v) if isinstance(fmt, str) else fmt(v)


def annotate(ax, text, xy, xytext, color=INK, bold=False, ha="center", size=10.5):
    ax.annotate(text, xy=xy, xytext=xytext, textcoords="data", ha=ha, va="center",
                fontsize=size, color=color, fontweight="bold" if bold else "normal",
                arrowprops=dict(arrowstyle="-", color=color, lw=0.9))


# --------------------------------------------------------------------------
# Chart types
# --------------------------------------------------------------------------
def bars(out, title, subtitle, labels, values, source, highlight=(), grey=(),
         fmt="{:,.0f}", ylim=None, yfmt=None, notes=(), note=None, label_values=True,
         label_every=1):
    """Vertical bars. `highlight` indices are red, `grey` indices are grey."""
    fig, ax = _frame(title, subtitle, source, note)
    colors = [RED if i in highlight else GREY if i in grey else BLUE for i in range(len(values))]
    x = range(len(values))
    ax.bar(x, values, color=colors, width=0.68, zorder=2)
    ax.set_xticks(list(x)[::label_every])
    ax.set_xticklabels(labels[::label_every], fontsize=11.5, color="#333333")
    if ylim:
        ax.set_ylim(*ylim)
    if yfmt:
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _fmt(v, yfmt)))
    if label_values:
        top = ax.get_ylim()[1]
        for i, v in enumerate(values):
            ax.text(i, v + top * 0.012, _fmt(v, fmt), ha="center", va="bottom", fontsize=11,
                    fontweight="bold", color=colors[i] if colors[i] != GREY else "#777777")
    _clean(ax)
    for n in notes:
        annotate(ax, **n)
    return _save(fig, out)


def hbars(out, title, subtitle, labels, values, source, highlight=(), grey=(),
          fmt="{:,.0f}", xlim=None, side_notes=None, note=None, h=H_IN, inside=False):
    """Horizontal bars, first label on top. `side_notes` maps index -> text."""
    n = len(values)
    left = 0.30 if max(len(l) for l in labels) > 18 else 0.20
    fig, ax = _frame(title, subtitle, source, note, h=h, left=left, right=0.93)
    colors = [RED if i in highlight else GREY if i in grey else BLUE for i in range(n)]
    y = list(range(n))[::-1]
    ax.barh(y, values, color=colors, height=0.62, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11.5, color="#444444")
    if xlim:
        ax.set_xlim(*xlim)
    right = ax.get_xlim()[1]
    for i, v in enumerate(values):
        if inside:
            ax.text(v - right * 0.012, y[i], _fmt(v, fmt), ha="right", va="center",
                    fontsize=11.5, fontweight="bold", color="white")
        else:
            ax.text(v + right * 0.01, y[i], _fmt(v, fmt), ha="left", va="center",
                    fontsize=11.5, fontweight="bold", color=colors[i] if colors[i] != GREY else "#777777")
        if side_notes and i in side_notes:
            off = right * (0.012 if inside else 0.09)
            ax.text(v + off, y[i], side_notes[i], ha="left", va="center", fontsize=11,
                    fontweight="bold", color=colors[i] if colors[i] != GREY else "#666666")
    ax.set_xticks([])
    _clean(ax, grid_axis=None)
    ax.spines["bottom"].set_visible(False)
    return _save(fig, out)


def lines(out, title, subtitle, series, source, yfmt=None, ylim=None, notes=(),
          note=None, end_labels=True, shade=None, xfmt=None, legend=False, label_fmt=None):
    """series: list of dicts {x, y, label, color, lw, dashed}."""
    fig, ax = _frame(title, subtitle, source, note, right=0.86 if end_labels else 0.97)
    for s in series:
        ax.plot(s["x"], s["y"], color=s.get("color", BLUE), lw=s.get("lw", 2.4),
                ls="--" if s.get("dashed") else "-", label=s.get("label"), zorder=3,
                solid_capstyle="round")
        if end_labels and s.get("label"):
            lab = s["label"]
            if label_fmt:
                lab = f"{lab}\n{_fmt(s['y'][-1], label_fmt)}"
            ax.text(s["x"][-1], s["y"][-1] + s.get("label_dy", 0), "  " + lab, color=s.get("color", BLUE),
                    fontsize=11, fontweight="bold", va="center", ha="left")
    if shade:
        for a, b, lab in shade:
            ax.axvspan(a, b, color="#f0f0f0", zorder=0, lw=0)
            if lab:
                ax.text(a, ax.get_ylim()[1], " " + lab, fontsize=9, color="#777777", va="top")
    if ylim:
        ax.set_ylim(*ylim)
    if yfmt:
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _fmt(v, yfmt)))
    if xfmt:
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _fmt(v, xfmt)))
    if legend:
        ax.legend(frameon=False, loc="upper left", fontsize=10.5)
    _clean(ax)
    for n in notes:
        annotate(ax, **n)
    return _save(fig, out)


def big_stat(out, number, line1, line2, source, color=RED, kicker=None, compare=None):
    """One giant number with a short line of context. `compare` adds a grey second stat."""
    fig = plt.figure(figsize=(W_IN, H_IN), dpi=DPI, facecolor="white")
    y0 = 0.86
    if kicker:
        fig.text(0.07, y0, kicker.upper(), fontsize=13, color=SUB, fontweight="bold", va="top")
    fig.text(0.07, 0.76, number, fontsize=110 if len(number) <= 6 else 84, fontweight="black",
             color=color, va="top")
    fig.text(0.07, 0.38, line1, fontsize=21, fontweight="bold", color=INK, va="top", wrap=True)
    if line2:
        fig.text(0.07, 0.27, line2, fontsize=14.5, color=SUB, va="top")
    if compare:
        num, lab = compare
        fig.text(0.62, 0.70, num, fontsize=54, fontweight="black", color=GREY, va="top")
        fig.text(0.62, 0.52, lab, fontsize=13, color=SUB, va="top")
    fig.text(0.07, 0.075, f"Source: {source}", fontsize=9.5, color=FOOT)
    fig.text(0.07, 0.035, CREDIT, fontsize=9.5, color=FOOT, fontweight="bold")
    return _save(fig, out)


# --------------------------------------------------------------------------
# State choropleth
# --------------------------------------------------------------------------
_STATES = None


def _states():
    global _STATES
    if _STATES is None:
        import geopandas as gpd
        from shapely import affinity
        g = gpd.read_file(ROOT / "data" / "geo" / "cb_2023_us_state_20m.shp")
        g = g[~g.STUSPS.isin(["PR"])].to_crs("ESRI:102003")      # Albers equal area
        ak = g.STUSPS == "AK"
        hi = g.STUSPS == "HI"
        g.loc[ak, "geometry"] = g.loc[ak, "geometry"].apply(
            lambda s: affinity.translate(affinity.scale(s, 0.35, 0.35, origin="centroid"), 1.2e6, -4.6e6))
        g.loc[hi, "geometry"] = g.loc[hi, "geometry"].apply(
            lambda s: affinity.translate(s, 5.2e6, -1.35e6))
        _STATES = g
    return _STATES


def state_map(out, title, subtitle, values, source, bins, labels, colors=None, note=None,
              legend_title=None):
    """values: {state_abbrev: number}. bins: upper edges (len = len(labels))."""
    import numpy as np
    colors = colors or ["#1d81a2", "#7fb7cc", "#e8e8e8", "#e99a8f", "#c71e1d"][:len(labels)]
    g = _states().copy()
    g["v"] = g.STUSPS.map(values)

    def pick(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "#f5f5f5"
        for edge, c in zip(bins, colors):
            if v <= edge:
                return c
        return colors[-1]

    g["c"] = g.v.apply(pick)
    fig = plt.figure(figsize=(W_IN, 6.0), dpi=DPI, facecolor="white")
    fig.text(0.045, 0.955, title, fontsize=19, fontweight="bold", color=INK, va="top")
    if subtitle:
        fig.text(0.045, 0.895, subtitle, fontsize=12, color=SUB, va="top")
    ax = fig.add_axes([0.02, 0.10, 0.96, 0.70])
    g.plot(ax=ax, color=g.c, edgecolor="white", linewidth=0.6)
    ax.set_axis_off()
    handles = [Patch(color=c, label=l) for c, l in zip(colors, labels)]
    lg = fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.04, 0.855), ncol=len(labels),
                    frameon=False, fontsize=10, handlelength=1.6, columnspacing=1.2,
                    title=legend_title, title_fontsize=10, alignment="left")
    if legend_title:
        lg.get_title().set_color(SUB)
    src = f"Source: {source}" + (f". {note}" if note else "")
    fig.text(0.045, 0.05, src, fontsize=8.6, color=FOOT)
    fig.text(0.045, 0.02, CREDIT, fontsize=8.6, color=FOOT, fontweight="bold")
    return _save(fig, out)
