"""Replacements for four notes that reused visuals (Nov 17 fix). All new visuals."""
import numpy as np
import pandas as pd
from pathlib import Path
from aiq_notes import charts as C

EXT = Path(__file__).resolve().parent.parent / "data" / "ext"
OUT = Path(__file__).resolve().parent.parent / "charts" / "2026-11-16"
P = lambda n: str(OUT / f"{n}.png")
OA_SRC = "Opportunity Insights, Opportunity Atlas (Chetty, Friedman, Hendren, Jones & Porter). Children born 1978-83, income at age ~35"


def oa_county_map():
    oa = pd.read_csv(EXT / "county_outcomes_simple.csv")
    oa = oa[oa.pooled_pooled_count > 500]
    oa["fips"] = oa.state * 1000 + oa.county
    v = dict(zip(oa.fips, oa.kfr_pooled_pooled_p25 * 100))
    return C.county_map(P("opportunity_atlas_counties"), "Where a kid born poor ends up depends on the county",
                        "Adult income rank of children who grew up in low-income families (25th percentile)",
                        v, OA_SRC, bins=[36, 39, 42, 45, 100],
                        labels=["Under 36th pct", "36-39th", "39-42nd", "42-45th", "45th+"],
                        legend_title="Red = less upward mobility, blue = more",
                        callouts=[("Shelby Co., TN (Memphis): 32nd", 47157, 2.0e5, -5.5e5), ("Bergen Co., NJ: 52nd", 34003, -2.5e5, 4.5e5)])


def oa_race_gap():
    oa = pd.read_csv(EXT / "county_outcomes_simple.csv")
    rows = []
    for lab, g in [("White", "white"), ("Hispanic", "hisp"), ("All children", "pooled"), ("Black", "black")]:
        d = oa[[f"kfr_{g}_pooled_p25", f"{g}_pooled_count"]].dropna()
        rows.append((lab, np.average(d.iloc[:, 0], weights=d.iloc[:, 1]) * 100))
    return C.hbars(P("opportunity_race_gap"), "Same family income, a 12-point gap by adulthood",
                   "Average adult income percentile of children raised in families at the 25th percentile",
                   [r[0] for r in rows], [r[1] for r in rows], OA_SRC,
                   highlight=(3,), grey=(2,), fmt="{:.1f}", xlim=(0, 52), inside=True)


def bay_area_rents():
    z = pd.read_csv(EXT / "County_zori_uc_sfrcondomfr_sm_month.csv")
    cols = [c for c in z.columns if c[:2] == "20"]
    z["yoy"] = (z[cols[-1]] / z[cols[-13]] - 1) * 100
    big = z[z.SizeRank <= 100].sort_values("yoy", ascending=False).dropna(subset=["yoy"])
    top, low = big.head(6), big.tail(3)
    lab = lambda r: f"{r.RegionName.replace(' County', '')}, {r.State}"
    labels = [lab(r) for r in top.itertuples()] + ["Median large county"] + [lab(r) for r in low.itertuples()]
    vals = list(top.yoy) + [big.yoy.median()] + list(low.yoy)
    return C.hbars(P("bay_area_rents"), "Bay Area rents are rising faster than in any other big county",
                   "Change in typical asking rent, Oct. 2025 to Oct. 2026, 100 largest counties",
                   labels, vals, "Zillow Observed Rent Index (ZORI), all homes, smoothed",
                   highlight=(0, 1, 2, 3), grey=(6,), fmt="{:+.1f}%", xlim=(-2, 30))


def home_value_states():
    s = pd.read_csv(EXT / "State_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")
    sc = [c for c in s.columns if c[:2] == "20"]
    s["chg"] = (s[sc[-1]] / s["2020-01-31"] - 1) * 100
    ab = {'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA','Colorado':'CO','Connecticut':'CT','Delaware':'DE','District of Columbia':'DC','Florida':'FL','Georgia':'GA','Hawaii':'HI','Idaho':'ID','Illinois':'IL','Indiana':'IN','Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME','Maryland':'MD','Massachusetts':'MA','Michigan':'MI','Minnesota':'MN','Mississippi':'MS','Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV','New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM','New York':'NY','North Carolina':'NC','North Dakota':'ND','Ohio':'OH','Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA','Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD','Tennessee':'TN','Texas':'TX','Utah':'UT','Vermont':'VT','Virginia':'VA','Washington':'WA','West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY'}
    v = {ab[r.RegionName]: r.chg for r in s.itertuples() if r.RegionName in ab}
    return C.state_map(P("home_values_since_2020"), "New England homes have gained the most since 2020",
                       "Change in typical home value, January 2020 to October 2026",
                       v, "Zillow Home Value Index (ZHVI), mid-tier, smoothed and seasonally adjusted",
                       bins=[35, 45, 52, 60, 200], labels=["Under 35%", "35-45%", "45-52%", "52-60%", "60%+"],
                       legend_title="Blue = smaller gains, red = bigger")


def build():
    return dict(oa_map=oa_county_map(), oa_race=oa_race_gap(), bay=bay_area_rents(), hv=home_value_states())
