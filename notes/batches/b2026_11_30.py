"""Batch: Mon Nov 30 - Sun Dec 6, 2026 (21 notes). 20 new visuals + 1 credited reshare.

Run:  python3 batches/b2026_11_30.py
"""
import io
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import requests
from PIL import Image

from aiq_notes import charts as C
from aiq_notes.acs import load_state
from aiq_notes.fred import series as S
from aiq_notes.schedule import pick_time

BATCH = "2026-11-30"
START = date(2026, 11, 30)
OUT = ROOT / "charts" / BATCH
OUT.mkdir(parents=True, exist_ok=True)
EXT = ROOT / "data" / "ext"
P = lambda n: str(OUT / f"{n}.png")
BLUE, RED, GREY, SUB = C.BLUE, C.RED, C.GREY, C.SUB
ACS = "U.S. Census Bureau, American Community Survey 2025 1-year estimates"
OA = "Opportunity Insights, Opportunity Atlas (Chetty, Friedman, Hendren, Jones & Porter)"
STATES = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()


def acs(t, c):
    return load_state(t, 2025)[f"{t.upper()}_{c}"].astype(float)


def states_only(s):
    return s.drop(["US", "PR"], errors="ignore").to_dict()


def _x(s):
    return [d.year + (d.month - 1) / 12 for d in s.index]


def owid(name, peers):
    t = pd.read_csv(EXT / "owid" / f"{name}.csv")
    c = t.columns[3]
    out = {}
    for e in peers:
        r = t[t.entity == e].dropna(subset=[c]).sort_values("year")
        if len(r):
            out[e] = (int(r.year.iloc[-1]), float(r[c].iloc[-1]))
    return out


# --------------------------------------------------------------------------- charts
def parents_map():
    s = acs("b09021", "E012") / acs("b09021", "E008") * 100
    return C.state_map(P("young_adults_with_parents"), "In New Jersey, nearly half of young adults live with their parents",
                       "Share of adults ages 18-34 living in a parent's home, 2025", states_only(s),
                       f"{ACS} (Table B09021). U.S. average: {s['US']:.1f}%",
                       bins=[25, 30, 34, 38, 100], labels=["Under 25%", "25-30%", "30-34%", "34-38%", "38%+"],
                       legend_title="Blue = fewer, red = more")


def real_wages():
    cpi, a = S("CPIAUCSL"), S("AHETPI")
    real = (a / cpi.reindex(a.index) * cpi.iloc[-1]).dropna()
    x = _x(real)
    v73 = real.loc["1973-01-01"]
    return C.lines(P("real_wages_1973"), "Typical workers earn barely more than they did in 1973",
                   "Average hourly earnings, production and nonsupervisory workers, in October 2026 dollars",
                   [dict(x=x, y=list(real.values), color=BLUE)],
                   "BLS via FRED (AHETPI), adjusted with CPI-U (CPIAUCSL), through Oct. 2026",
                   end_labels=False, yfmt="${:.0f}", xfmt="{:.0f}", ylim=(20, 36),
                   notes=[dict(text=f"Jan. 1973: ${v73:.2f}", xy=(1973.0, v73), xytext=(1982, 34.6), color=BLUE, bold=True),
                          dict(text=f"Today: ${real.iloc[-1]:.2f}", xy=(x[-1], real.iloc[-1]), xytext=(x[-1] - 8, 34.6),
                               color=RED, bold=True)])


def incarceration_gap():
    oa = pd.read_csv(EXT / "county_outcomes_simple.csv")
    rows = []
    for lab, g in [("Black", "black"), ("All children", "pooled"), ("White", "white"), ("Hispanic", "hisp")]:
        d = oa[[f"jail_{g}_pooled_p25", f"{g}_pooled_count"]].dropna()
        rows.append((lab, np.average(d.iloc[:, 0], weights=d.iloc[:, 1]) * 100))
    return C.hbars(P("incarceration_gap"), "Same family income, triple the incarceration rate",
                   "Share incarcerated on April 1, 2010, children raised in families at the 25th income percentile",
                   [r[0] for r in rows], [r[1] for r in rows], f"{OA}. Children born 1978-83",
                   highlight=(0,), grey=(1,), fmt="{:.1f}%", xlim=(0, 6.5), inside=True)


def health_scatter():
    t = pd.read_csv(EXT / "owid" / "life-expectancy-vs-health-expenditure.csv")
    le, sp = t.columns[3], t.columns[4]
    peers = ["United States", "Japan", "Switzerland", "Germany", "France", "United Kingdom", "Canada", "Australia",
             "Italy", "Spain", "South Korea", "Sweden", "Norway", "Netherlands", "Denmark"]
    d = t[t.entity.isin(peers) & t.year.eq(2023)].dropna(subset=[le, sp])
    fig, ax = C._frame("America spends the most on health care and dies the youngest",
                       "Health spending per person (PPP dollars) vs. life expectancy at birth, 2023",
                       "Our World in Data, from WHO Global Health Expenditure Database and UN World Population Prospects")
    for r in d.itertuples():
        us = r.entity == "United States"
        ax.scatter(getattr(r, sp), getattr(r, le), s=110 if us else 60, color=RED if us else BLUE, zorder=3)
        off = {"Spain": (6, -11), "Sweden": (6, 5), "Canada": (6, -11), "Denmark": (-48, -4), "Italy": (6, 5), "France": (-38, 5),
               "South Korea": (6, 5), "Netherlands": (6, -9)}.get(r.entity, (6, 4))
        ax.annotate(r.entity.replace("United Kingdom", "UK"), (getattr(r, sp), getattr(r, le)), xytext=off,
                    textcoords="offset points", fontsize=9.5 if not us else 11, color=RED if us else "#444444",
                    fontweight="bold" if us else "normal")
    ax.xaxis.set_major_formatter(C.plt.FuncFormatter(lambda v, _: f"${v/1000:.0f}K"))
    ax.set_xlim(3000, 13500)
    ax.set_ylim(78, 86)
    ax.set_ylabel("Life expectancy (years)", fontsize=10, color=SUB)
    C._clean(ax)
    ax.grid(axis="x", color=C.GRID, lw=0.8)
    return C._save(fig, P("health_spending_life_expectancy"))


def no_vehicle_map():
    s = acs("b08201", "E002") / acs("b08201", "E001") * 100
    return C.state_map(P("no_vehicle_households"), "Outside a few cities, America barely works without a car",
                       "Share of households with no vehicle available, 2025", states_only(s),
                       f"{ACS} (Table B08201). U.S. average: {s['US']:.1f}%",
                       bins=[5, 6.5, 8, 10, 100], labels=["Under 5%", "5-6.5%", "6.5-8%", "8-10%", "10%+"],
                       colors=["#e8e8e8", "#c7dde6", "#7fb7cc", "#3c93b3", "#1d81a2"],
                       legend_title="Darker = more car-free households")


def top1_peers():
    peers = ["United States", "Spain", "Denmark", "Germany", "United Kingdom", "France", "Canada", "Australia",
             "Sweden", "Netherlands"]
    d = owid("income-share-top-1-before-tax-wid", peers)
    d = {k: v for k, v in d.items() if v[0] >= 2021}
    order = sorted(d, key=lambda k: -d[k][1])
    labs = [f"{k.replace('United Kingdom', 'UK')} ({d[k][0]})" for k in order]
    return C.hbars(P("top1_income_peers"), "The top 1% takes a far bigger slice in America",
                   "Share of pre-tax national income going to the top 1%, latest year",
                   labs, [d[k][1] for k in order], "World Inequality Database via Our World in Data",
                   highlight=(order.index("United States"),), fmt="{:.1f}%", xlim=(0, 24), inside=True)


def young_owners_map():
    own = acs("b25007", "E003") + acs("b25007", "E004")
    ren = acs("b25007", "E013") + acs("b25007", "E014")
    s = own / (own + ren) * 100
    return C.state_map(P("young_homeownership"), "In DC, only 1 in 10 young households owns a home",
                       "Homeownership rate, householders under 35, 2025", states_only(s),
                       f"{ACS} (Table B25007). U.S. average: {s['US']:.1f}%",
                       bins=[28, 33, 37, 42, 100], labels=["Under 28%", "28-33%", "33-37%", "37-42%", "42%+"],
                       colors=["#c71e1d", "#e99a8f", "#e8e8e8", "#7fb7cc", "#1d81a2"],
                       legend_title="Red = fewer young owners, blue = more")


def austin_rents():
    z = pd.read_csv(EXT / "County_zori_uc_sfrcondomfr_sm_month.csv")
    cols = [c for c in z.columns if c[:2] == "20"]
    z["chg"] = (z[cols[-1]] / z["2022-10-31"] - 1) * 100
    big = z[z.SizeRank <= 60].dropna(subset=["chg"]).sort_values("chg")
    low, high = big.head(5), big.tail(3)[::-1]
    lab = lambda r: f"{r.RegionName.replace(' County', '')}, {r.State}"
    labels = [lab(r) for r in high.itertuples()] + ["Median large county"] + [lab(r) for r in low.itertuples()][::-1]
    vals = list(high.chg) + [big.chg.median()] + list(low.chg)[::-1]
    names = {"Travis, TX": "Travis (Austin), TX"}
    labels = [names.get(l, l) for l in labels]
    return C.hbars(P("austin_rents"), "Austin built, and rents fell",
                   "Change in typical asking rent, Oct. 2022 to Oct. 2026, 60 largest counties",
                   labels, vals, "Zillow Observed Rent Index (ZORI), all homes, smoothed",
                   highlight=(len(vals) - 1,), grey=(3,), fmt="{:+.1f}%", xlim=(-16, 30))


def infant_mortality():
    peers = ["United States", "Canada", "United Kingdom", "France", "Netherlands", "Switzerland", "Germany",
             "Australia", "Spain", "South Korea", "Italy", "Norway", "Sweden", "Japan"]
    d = owid("infant-mortality", peers)
    order = sorted(d, key=lambda k: -d[k][1])
    return C.hbars(P("infant_mortality_peers"), "American babies are 3x as likely to die as Japanese babies",
                   "Deaths before age 1 per 1,000 live births, 2024",
                   [k.replace("United Kingdom", "UK") for k in order], [d[k][1] * 10 for k in order],
                   "UN Inter-agency Group for Child Mortality Estimation via Our World in Data",
                   highlight=(order.index("United States"),), fmt="{:.1f}", xlim=(0, 6.5), inside=True,
                   h=6.2)


def commute_map():
    s = (acs("b08303", "E012") + acs("b08303", "E013")) / acs("b08303", "E001") * 100
    return C.state_map(P("long_commutes"), "Nearly 1 in 5 New York workers commutes an hour or more",
                       "Share of workers (not working from home) with a one-way commute of 60+ minutes, 2025",
                       states_only(s), f"{ACS} (Table B08303). U.S. average: {s['US']:.1f}%",
                       bins=[5, 7, 9, 12, 100], labels=["Under 5%", "5-7%", "7-9%", "9-12%", "12%+"],
                       legend_title="Blue = shorter commutes, red = longer")


def youth_unemployment():
    y, u = S("LNS14024887").loc["2000":], S("UNRATE").loc["2000":]
    return C.lines(P("youth_unemployment"), "Young workers are jobless at more than twice the overall rate",
                   "Unemployment rate, seasonally adjusted",
                   [dict(x=_x(y), y=list(y.values), color=RED, label="Ages 16-24"),
                    dict(x=_x(u), y=list(u.reindex(y.index).values), color=BLUE, label="All workers")],
                   "U.S. Bureau of Labor Statistics via FRED (LNS14024887, UNRATE), through Oct. 2026",
                   yfmt="{:.0f}%", xfmt="{:.0f}", label_fmt="{:.1f}%")


def state_unemployment():
    v, when = {}, None
    for s in STATES:
        x = S(f"{s}UR")
        v[s], when = x.iloc[-1], x.index[-1]
    return C.state_map(P("state_unemployment"), "Unemployment runs from 2% in South Dakota to 5.6% in DC",
                       f"Unemployment rate by state, {when:%B %Y}, seasonally adjusted", v,
                       "U.S. Bureau of Labor Statistics, Local Area Unemployment Statistics, via FRED",
                       bins=[3, 3.7, 4.3, 4.9, 100], labels=["Under 3%", "3-3.7%", "3.7-4.3%", "4.3-4.9%", "4.9%+"],
                       legend_title="Blue = lower, red = higher")


def income_map():
    s = acs("b19013", "E001")
    return C.state_map(P("median_income_states"), "The typical DC household earns nearly twice what Mississippi's does",
                       "Median household income, 2025", states_only(s),
                       f"{ACS} (Table B19013). U.S. median: ${s['US']:,.0f}",
                       bins=[70000, 78000, 86000, 95000, 1e9], labels=["Under $70K", "$70-78K", "$78-86K", "$86-95K", "$95K+"],
                       colors=["#c71e1d", "#e99a8f", "#e8e8e8", "#7fb7cc", "#1d81a2"],
                       legend_title="Red = lower income, blue = higher")


def uninsured_adults_map():
    s = (acs("b27010", "E033") + acs("b27010", "E050")) / (acs("b27010", "E018") + acs("b27010", "E034")) * 100
    return C.state_map(P("uninsured_adults"), "More than 1 in 5 working-age Texans has no health insurance",
                       "Share of adults ages 19-64 with no health insurance, 2025", states_only(s),
                       f"{ACS} (Table B27010). U.S. average: {s['US']:.1f}%",
                       bins=[7, 10, 13, 16, 100], labels=["Under 7%", "7-10%", "10-13%", "13-16%", "16%+"],
                       legend_title="Blue = fewer uninsured, red = more")


def working_hours():
    peers = ["United States", "Canada", "Italy", "Japan", "Australia", "United Kingdom", "Switzerland", "France",
             "Sweden", "Netherlands", "Norway", "Denmark", "Germany"]
    d = owid("annual-working-hours-per-worker", peers)
    order = sorted(d, key=lambda k: -d[k][1])
    return C.hbars(P("working_hours_peers"), "Americans work about 11 more weeks a year than Germans",
                   "Average annual hours worked per worker, 2023",
                   [k.replace("United Kingdom", "UK") for k in order], [d[k][1] for k in order],
                   "Penn World Table and OECD via Our World in Data",
                   highlight=(order.index("United States"),), grey=(order.index("Germany"),), fmt="{:,.0f}",
                   xlim=(0, 2000), inside=True, h=6.0)


def internet_map():
    s = acs("b28002", "E013") / acs("b28002", "E001") * 100
    return C.state_map(P("no_internet"), "Which state has the most households with no internet at all?",
                       "Share of households with no internet access, 2025", states_only(s),
                       f"{ACS} (Table B28002). U.S. average: {s['US']:.1f}%",
                       bins=[3, 3.8, 4.6, 5.5, 100], labels=["Under 3%", "3-3.8%", "3.8-4.6%", "4.6-5.5%", "5.5%+"],
                       legend_title="Blue = more connected, red = less")


def senior_poverty_map():
    p = load_state("b17020", 2025)
    f = lambda c: p[f"B17020_{c}"].astype(float)
    below, above = f("E007") + f("E008") + f("E009"), f("E015") + f("E016") + f("E017")
    s = below / (below + above) * 100
    return C.state_map(P("senior_poverty"), "In DC, nearly 1 in 5 older residents lives in poverty",
                       "Share of people 60 and older living below the poverty line, 2025", states_only(s),
                       f"{ACS} (Table B17020). U.S. average: {s['US']:.1f}%",
                       bins=[9, 10.5, 12, 13.5, 100], labels=["Under 9%", "9-10.5%", "10.5-12%", "12-13.5%", "13.5%+"],
                       legend_title="Blue = lower, red = higher")


def wfh_map():
    s = acs("b08301", "E021") / acs("b08301", "E001") * 100
    return C.state_map(P("work_from_home"), "Remote work is a perk of the places with high-paying jobs",
                       "Share of workers who worked from home, 2025", states_only(s),
                       f"{ACS} (Table B08301). U.S. average: {s['US']:.1f}%",
                       bins=[9, 11, 13, 15, 100], labels=["Under 9%", "9-11%", "11-13%", "13-15%", "15%+"],
                       colors=["#e8e8e8", "#c7dde6", "#7fb7cc", "#3c93b3", "#1d81a2"],
                       legend_title="Darker = more remote workers")


def stats():
    h = pd.read_csv(EXT / "County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")
    hc = [c for c in h.columns if c[:2] == "20"]
    n_now, n_19 = int((h[hc[-1]] >= 1e6).sum()), int((h["2019-10-31"] >= 1e6).sum())
    yoy = (h[hc[-1]] / h[hc[-13]] - 1) * 100
    fall = (yoy.dropna() < 0).mean() * 100
    a = C.big_stat(P("stat_million_counties"), str(n_now), "U.S. counties where the typical home is worth $1 million+",
                   f"In 2019 there were {n_19}.", "Zillow Home Value Index (ZHVI), mid-tier, October 2026 vs. October 2019",
                   kicker="Housing")
    b = C.big_stat(P("stat_counties_falling"), f"{fall:.0f}%", "of U.S. counties saw home values fall over the past year",
                   "October 2025 to October 2026.", "Zillow Home Value Index (ZHVI), mid-tier, 3,100+ counties",
                   kicker="Housing")
    return a, b, n_now, n_19, fall


def build():
    ch = dict(parents=parents_map(), wages=real_wages(), jail=incarceration_gap(), health=health_scatter(),
              car=no_vehicle_map(), top1=top1_peers(), owners=young_owners_map(), austin=austin_rents(),
              infant=infant_mortality(), commute=commute_map(), youth=youth_unemployment(),
              stateue=state_unemployment(), income=income_map(), uninsured=uninsured_adults_map(),
              hours=working_hours(), internet=internet_map(), seniors=senior_poverty_map(), wfh=wfh_map())
    ch["million"], ch["falling"], n_now, n_19, fall = stats()
    ch["transit"] = str(ROOT / "charts" / BATCH / "reshare_sunderji_east_flatbush.png")
    return ch, dict(n_now=n_now, n_19=n_19, fall=fall)


def notes(ch, k):
    N = []
    add = lambda pillar, chart, text, why, kind: N.append(dict(pillar=pillar, chart=chart, text=text.strip(),
                                                               why_now=why, source_kind=kind))
    # Mon Nov 30
    add("Housing", ch["parents"], """
A third of Americans between 18 and 34 now live in a parent's home, 24.8 million young adults in all, per new Census data. In New Jersey it's nearly half, and in Connecticut and California it's more than 4 in 10.

Those are also some of the most expensive places in the country to rent an apartment, and young adults are doing the math.""",
        "ACS 2025 1-year; holiday weekend, lots of adult kids home.", "new map: Census ACS")
    add("Employment", ch["wages"], """
After inflation, the typical rank-and-file worker in America earns $32.75 an hour. In January 1973 it was $31.85.

That's 53 years of a growing economy, and the paycheck of the average production worker has moved about 3%.""",
        "Evergreen labor chart; Oct CPI and earnings data.", "new chart: BLS")
    add("Education", ch["jail"], """
Black children who grew up in low-income families were three times as likely as white children from the same income level to be in prison or jail as young adults, according to the Opportunity Atlas.

Same family income and the same starting point, with a completely different set of odds.""",
        "Opportunity Atlas; follows the Nov 28 race-gap note with a different outcome.", "new chart: Opportunity Atlas")
    # Tue Dec 1
    add("Healthcare", ch["health"], """
The US spends $12,099 per person on health care, more than double what Japan spends, and Americans live five fewer years.

Every other rich country on this chart gets more years of life for less money.""",
        "ACA open enrollment; OWID 2023 health spending data.", "new chart: Our World in Data")
    add("Housing", ch["car"], """
In New York, 31% of households don't own a car, and in DC it's 38%. In Wyoming it's under 4%.

Across most of America, not owning a car means not getting to work, the doctor or a grocery store, which makes a car one of the most expensive necessities a low-income family has.""",
        "ACS 2025; pairs with the transit reshare this evening.", "new map: Census ACS")
    add("Housing", ch["transit"], """
The average East Flatbush resident lives 0.8 miles from the nearest rail line. Great map from @[Aziz Sunderji](2432780).

The planned Utica Avenue stop on the IBX would put most of them within a half-mile walk of a train, which for a lot of working families means time back every single day.""",
        "Reshare: Aziz Sunderji ProMap note (Nov 17) on transit access.", "reshare: Aziz Sunderji / The Pro Map")
    # Wed Dec 2
    add("Incomes", ch["top1"], """
The top 1% of Americans take home 20.7% of all pre-tax income, about double their share in 1980.

In France, Canada and Spain the top 1% gets around 12%. Other rich countries made different choices about how much of the pie goes to the very top.""",
        "World Inequality Database via OWID; wealth-tax debate continues.", "new chart: Our World in Data")
    add("Housing", ch["owners"], """
Only 10% of DC households headed by someone under 35 own their home. In California it's 22.5%, while in West Virginia it's 48.6%.

The places with the most jobs for young people are the places where they have the hardest time ever owning anything.""",
        "ACS 2025 1-year.", "new map: Census ACS")
    add("Housing", ch["austin"], """
Rents in Austin are down almost 10% since 2022, while rents in the typical large county rose 10%.

Austin built apartments faster than almost any city in America over the past few years. When supply goes up, rents come down, and renters are the ones who win.""",
        "Zillow ZORI Oct 2026; housing-supply debate.", "new chart: Zillow")
    # Thu Dec 3
    add("Healthcare", ch["infant"], """
In the US, 5.5 of every 1,000 babies die before their first birthday. In Japan it's 1.8.

The richest country in the world has a higher infant mortality rate than every peer on this chart.""",
        "UN IGME 2024 via OWID.", "new chart: Our World in Data")
    add("Housing", ch["commute"], """
Nearly 1 in 5 workers in New York spends an hour or more getting to work each way. In Nebraska and South Dakota it's under 4%.

Long commutes fall hardest on the workers who have been priced out of the places where the jobs are.""",
        "ACS 2025 1-year.", "new map: Census ACS")
    add("Housing", ch["million"], f"""
There are now {k['n_now']} counties in America where the typical home is worth more than $1 million, up from {k['n_19']} in 2019, per Zillow.

In most of them, the people who teach, nurse and police the community can't afford to live there.""",
        "Zillow ZHVI Oct 2026.", "big stat: Zillow")
    # Fri Dec 4 (jobs report day)
    add("Employment", ch["youth"], """
Unemployment for Americans aged 16 to 24 is 9.3%, more than double the overall rate of 4.1%.

The November jobs report comes out this morning, and young workers are usually the first to feel a slowdown.""",
        "November jobs report (Dec 4, 8:30am).", "new chart: BLS")
    add("Employment", ch["stateue"], """
Unemployment ranges from 2% in South Dakota to 5.6% in DC, with California, Connecticut, Michigan and Oregon all at 5% or more.

Today's national number is a single figure, but the job market a family actually faces depends a lot on where they live.""",
        "Jobs report day; BLS state data (Sept 2026).", "new map: BLS")
    add("Incomes", ch["income"], """
The typical household in DC earns $109,505 a year. In Mississippi it's $59,346, per new Census data.

Same country, with almost a 2x difference in what a family has to work with before rent, groceries or child care.""",
        "ACS 2025 1-year.", "new map: Census ACS")
    # Sat Dec 5
    add("Healthcare", ch["uninsured"], """
More than 1 in 5 working-age adults in Texas has no health insurance. In Massachusetts it's fewer than 1 in 25.

Massachusetts built near-universal coverage two decades ago, and Texas is one of the few states that still hasn't expanded Medicaid.""",
        "ACS 2025; ACA deadline for Jan 1 coverage is Dec 15.", "new map: Census ACS")
    add("Employment", ch["hours"], """
American workers put in about 1,789 hours a year on average, roughly 450 more than workers in Germany.

That's about 11 extra weeks of full-time work every year, in the richest economy on earth.""",
        "Penn World Table/OECD via OWID.", "new chart: Our World in Data")
    add("Housing", ch["internet"], """
Which state has the highest share of households with no internet access at all?

It's West Virginia, at 7.8%, nearly twice the national rate. Most of the states near the top of this list are rural and lower-income, the places where getting online would help most.""",
        "Saturday evening question format; ACS 2025.", "new map: Census ACS")
    # Sun Dec 6
    add("Incomes", ch["seniors"], """
In DC, 18.4% of residents 60 and older live below the poverty line. In Louisiana it's 16.1%.

These are people who worked their whole lives, and in much of the country a Social Security check alone doesn't cover rent and medicine.""",
        "ACS 2025; retirees-on-under-$2,000 coverage (Investopedia, Nov).", "new map: Census ACS")
    add("Employment", ch["wfh"], """
22.7% of workers in DC now work from home, compared with 6.3% in North Dakota and 6.5% in Mississippi.

Remote work quietly became one of the best perks of a high-income job, and most service workers never got the option.""",
        "ACS 2025 1-year.", "new map: Census ACS")
    add("Housing", ch["falling"], f"""
Home values fell over the past year in {k['fall']:.0f}% of US counties, per Zillow.

For most families the house is the bulk of their wealth, so a falling home value means a thinner safety net, even when the national numbers look fine.""",
        "Zillow ZHVI Oct 2026; follows the K-shaped home values reshare.", "big stat: Zillow")
    return N


def main():
    ch, k = build()
    items = notes(ch, k)
    assert len(items) == 21, len(items)
    rng = random.Random(BATCH)
    cal = []
    for i, it in enumerate(items):
        day = START + timedelta(days=i // 3)
        block = (["morning", "midday", "evening"] if day.weekday() >= 5 else ["morning", "midday", "afternoon"])[i % 3]
        t = pick_time(day, block, rng)
        cal.append(dict(id=f"{t:%Y%m%d}-{i % 3 + 1}", scheduled_et=t.isoformat(), day=f"{t:%a %b %-d}",
                        time_et=f"{t:%-I:%M %p}", block=block, status="Scheduled", pillar=it["pillar"],
                        text=it["text"], chart=str(Path(it["chart"]).relative_to(ROOT)), why_now=it["why_now"],
                        source_kind=it["source_kind"]))
    (ROOT / "calendar" / f"{BATCH}.json").write_text(json.dumps(cal, indent=1))
    print(f"wrote {len(cal)} notes")


if __name__ == "__main__":
    main()
