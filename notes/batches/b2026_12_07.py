"""Batch: Mon Dec 7 - Sun Dec 13, 2026. 14 notes, 2 per day (midday + evening).

Built from the first 10 days of results: the winners were national "record" charts about
capital vs. labor and the top 1% (profit share, top-1% wealth, corporate taxes, labor share),
a single striking housing number (first-time buyer age), and Rattner reshares. State maps,
Aziz reshares and morning slots did worst, so this week leans on the winners.
Voice follows VOICE.md "Jeremy's post-publication edits (Nov 25)".
"""
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from aiq_notes import charts as C
from aiq_notes.acs import load_state
from aiq_notes.fred import series as S
from aiq_notes.schedule import pick_time

BATCH = "2026-12-07"
START = date(2026, 12, 7)
OUT = ROOT / "charts" / BATCH
OUT.mkdir(parents=True, exist_ok=True)
EXT = ROOT / "data" / "ext"
P = lambda n: str(OUT / f"{n}.png")
BLUE, RED, GREY = C.BLUE, C.RED, C.GREY
DFA = "Federal Reserve, Distributional Financial Accounts, via FRED"
ACS = "U.S. Census Bureau, American Community Survey 2025 1-year estimates"


def _x(s):
    return [d.year + (d.month - 1) / 12 for d in s.index]


def top10_income():
    t = pd.read_csv(EXT / "owid" / "income-share-top-10-before-tax-wid.csv")
    c = t.columns[3]
    u = t[t.entity == "United States"].sort_values("year")
    x, y = list(u.year), list(u[c])
    v29 = float(u[u.year == 1929][c].iloc[0])
    lo = u.loc[u[c].idxmin()]
    return C.lines(P("top10_income_share_history"), "The top 10% are back to their 1929 share of income",
                   "Share of pre-tax national income going to the top 10%, United States",
                   [dict(x=x, y=y, color=BLUE)], "World Inequality Database via Our World in Data",
                   end_labels=False, yfmt="{:.0f}%", xfmt="{:.0f}", ylim=(25, 55),
                   notes=[dict(text=f"1929: {v29:.1f}%", xy=(1929, v29), xytext=(1940, 52), color=BLUE, bold=True),
                          dict(text=f"{int(lo.year)}: {lo[c]:.1f}%", xy=(lo.year, lo[c]), xytext=(1975, 28), color=BLUE, bold=True),
                          dict(text=f"{x[-1]}: {y[-1]:.1f}%", xy=(x[-1], y[-1]), xytext=(x[-1] - 14, 52.5), color=RED, bold=True)])


def top01_wealth():
    s = S("WFRBSTP1300")
    return C.lines(P("top01_wealth_share"), "The top 0.1% now hold a record share of America's wealth",
                   "Share of total household net worth held by the top 0.1%",
                   [dict(x=_x(s), y=list(s.values), color=BLUE)], f"{DFA} (WFRBSTP1300), through Q2 2026",
                   end_labels=False, yfmt="{:.0f}%", xfmt="{:.0f}", ylim=(0, 17),
                   notes=[dict(text=f"1989: {s.iloc[0]:.1f}%", xy=(_x(s)[0], s.iloc[0]), xytext=(1993, 4), color=BLUE, bold=True),
                          dict(text=f"Record: {s.iloc[-1]:.1f}%", xy=(_x(s)[-1], s.iloc[-1]), xytext=(_x(s)[-1] - 9, 16.3),
                               color=RED, bold=True)])


def wages_share():
    s = S("W270RE1A156NBEA")
    x = [d.year for d in s.index]
    return C.lines(P("wages_share_income"), "Paychecks are near their smallest share of the economy since 1948",
                   "Wages and salaries as a share of gross domestic income",
                   [dict(x=x, y=list(s.values), color=BLUE)], "U.S. Bureau of Economic Analysis via FRED (W270RE1A156NBEA), through 2025",
                   end_labels=False, yfmt="{:.0f}%", xfmt="{:.0f}", ylim=(38, 54),
                   notes=[dict(text=f"{s.idxmax().year}: {s.max():.1f}%", xy=(s.idxmax().year, s.max()), xytext=(1962, 53), color=BLUE, bold=True),
                          dict(text=f"{x[-1]}: {s.iloc[-1]:.1f}%", xy=(x[-1], s.iloc[-1]), xytext=(x[-1] - 10, 39.5), color=RED, bold=True)])


def gdp_vs_income():
    g, m = S("A939RX0Q048SBEA"), S("MEHOINUSA672N")
    ga = g.groupby(g.index.year).mean().loc[1984:2025]
    gi, mi = 100 * ga / ga.iloc[0] - 100, 100 * m / m.iloc[0] - 100
    return C.lines(P("gdp_vs_median_income"), "The economy doubled. The typical household's income didn't.",
                   "Change since 1984, adjusted for inflation",
                   [dict(x=list(gi.index), y=list(gi.values), color=BLUE, label="GDP per person"),
                    dict(x=[d.year for d in mi.index], y=list(mi.values), color=RED, label="Median income")],
                   "BEA (A939RX0Q048SBEA) and Census (MEHOINUSA672N) via FRED, through 2025",
                   yfmt="+{:.0f}%", xfmt="{:.0f}", label_fmt="+{:.0f}%")


def top_tax_rate():
    t = pd.read_csv(EXT / "owid" / "top-income-tax-rates-piketty.csv")
    c = t.columns[3]
    u = t[t.entity == "United States"].sort_values("year")
    x, y = list(u.year) + [2026], list(u[c]) + [37.0]
    return C.lines(P("top_tax_rate_history"), "The top tax rate used to be 91%",
                   "Top federal marginal income tax rate, United States",
                   [dict(x=x, y=y, color=BLUE)],
                   "Piketty (2014) via Our World in Data, through 2017; IRS for 2026",
                   end_labels=False, yfmt="{:.0f}%", xfmt="{:.0f}", ylim=(0, 100),
                   notes=[dict(text="1960: 91%", xy=(1960, 91), xytext=(1972, 97), color=BLUE, bold=True),
                          dict(text="Today: 37%", xy=(2026, 37), xytext=(2008, 62), color=RED, bold=True)])


def stocks_top_bottom():
    t, b = S("WFRBST01122"), S("WFRBSB50203")
    return C.lines(P("stock_ownership_top1_bottom50"), "The top 1% own half the stock market",
                   "Share of corporate equities and mutual fund shares held",
                   [dict(x=_x(t), y=list(t.values), color=RED, label="Top 1%"),
                    dict(x=_x(b), y=list(b.reindex(t.index).values), color=BLUE, label="Bottom 50%")],
                   f"{DFA} (WFRBST01122, WFRBSB50203), through Q2 2026",
                   yfmt="{:.0f}%", xfmt="{:.0f}", ylim=(0, 60), label_fmt="{:.1f}%")


def homeownership_race():
    rows = []
    for lab, t in [("White", "b25003a"), ("Asian", "b25003d"), ("All households", "b25003"),
                   ("Hispanic", "b25003i"), ("Black", "b25003b")]:
        d = load_state(t, 2025).loc["US"]
        rows.append((lab, float(d[f"{t.upper()}_E002"]) / float(d[f"{t.upper()}_E001"]) * 100))
    return C.hbars(P("homeownership_by_race"), "A 27-point gap in who owns a home",
                   "Homeownership rate by race and ethnicity of householder, 2025",
                   [r[0] for r in rows], [r[1] for r in rows],
                   f"{ACS} (Tables B25003, B25003A-I). Race groups are 'alone'; Hispanic may be of any race",
                   highlight=(4,), grey=(2,), fmt="{:.1f}%", xlim=(0, 80), inside=True)


def home_price_vs_income():
    p, cpi, m = S("MSPUS"), S("CPIAUCSL"), S("MEHOINUSA672N")
    pr = (p / cpi.reindex(p.index) * cpi.iloc[-1]).dropna()
    pa = pr.groupby(pr.index.year).mean().loc[1984:2025]
    pi, mi = 100 * pa / pa.iloc[0] - 100, 100 * m / m.iloc[0] - 100
    return C.lines(P("home_price_vs_income"), "Home prices have outrun incomes for 40 years",
                   "Change since 1984, adjusted for inflation",
                   [dict(x=list(pi.index), y=list(pi.values), color=RED, label="Home price"),
                    dict(x=[d.year for d in mi.index], y=list(mi.values), color=BLUE, label="Median income")],
                   "Census/HUD (MSPUS), Census (MEHOINUSA672N), BLS CPI-U via FRED, through 2025",
                   yfmt="+{:.0f}%", xfmt="{:.0f}", label_fmt="+{:.0f}%")


def dividends_vs_wages():
    d, w = S("B703RC1Q027SBEA"), S("A576RC1").resample("QS").mean()
    d, w = d.loc["2000":], w.reindex(d.loc["2000":].index)
    di, wi = 100 * d / d.iloc[0] - 100, 100 * w / w.iloc[0] - 100
    return C.lines(P("dividends_vs_wages"), "Dividend checks have grown more than twice as fast as paychecks",
                   "Change since 2000, personal dividend income vs. wages and salaries (nominal)",
                   [dict(x=_x(di), y=list(di.values), color=RED, label="Dividends"),
                    dict(x=_x(wi), y=list(wi.values), color=BLUE, label="Wages")],
                   "U.S. Bureau of Economic Analysis via FRED (B703RC1Q027SBEA, A576RC1), through Q3 2026",
                   yfmt="+{:.0f}%", xfmt="{:.0f}", label_fmt="+{:.0f}%")


def households_200k():
    b = load_state("b19001", 2025)
    s = b.B19001_E017.astype(float) / b.B19001_E001.astype(float) * 100
    return C.state_map(P("households_200k"), "In DC, 1 in 4 households earns $200,000 or more",
                       "Share of households with income of $200,000+, 2025",
                       s.drop(["US", "PR"], errors="ignore").to_dict(), f"{ACS} (Table B19001). U.S. average: {s['US']:.1f}%",
                       bins=[10, 13, 16, 20, 100], labels=["Under 10%", "10-13%", "13-16%", "16-20%", "20%+"],
                       colors=["#e8e8e8", "#c7dde6", "#7fb7cc", "#3c93b3", "#1d81a2"],
                       legend_title="Darker = more high-income households")


def rent_stat():
    z = pd.read_csv(EXT / "Metro_zori.csv")
    us = z[z.RegionName == "United States"].iloc[0]
    cols = [c for c in z.columns if c[:2] == "20"]
    now, then = us[cols[-1]], us["2019-10-31"]
    return C.big_stat(P("stat_typical_rent"), f"${now:,.0f}", "The typical asking rent in America, per month",
                      f"In October 2019 it was ${then:,.0f}.", "Zillow Observed Rent Index (ZORI), all homes, October 2026",
                      kicker="Housing"), now, then


def build():
    rent, now, then = rent_stat()
    ch = dict(top10=top10_income(), top01=top01_wealth(), wages=wages_share(), gdp=gdp_vs_income(),
              tax=top_tax_rate(), stocks=stocks_top_bottom(), own=homeownership_race(),
              home=home_price_vs_income(), div=dividends_vs_wages(), hh200=households_200k(), rent=rent,
              manhattan=str(OUT / "reshare_rattner_manhattan.png"),
              anthropic=str(OUT / "reshare_rattner_anthropic.png"),
              dems=str(OUT / "reshare_rattner_dem_gains.png"))
    return ch, dict(rent_now=now, rent_then=then)


def notes(ch, k):
    N = []
    add = lambda pillar, chart, text, why, kind: N.append(dict(pillar=pillar, chart=chart, text=text.strip(),
                                                               why_now=why, source_kind=kind))
    # Mon Dec 7
    add("Incomes", ch["top10"], """
The top 10% of Americans now take home 46.8% of all pre-tax income, about the same share they had in 1929. In 1970 it was 33.5%.""",
        "Capital-vs-labor 'record' theme (top performers Nov 16-22).", "new chart: WID via OWID")
    add("Incomes", ch["manhattan"], """
Manhattan now has the most unequal incomes of any large county in America, and three of the top ten on this list from @[Steve Rattner](1658881) are in New York. Anyone who has walked from the Upper East Side into East Harlem has seen it within a few blocks.""",
        "Reshare: Rattner (Nov 19), Census Gini by county; Rattner reshares averaged a score of 59.", "reshare: Steve Rattner")
    # Tue Dec 8
    add("Incomes", ch["top01"], """
The top 0.1% of American households now hold 15% of all the wealth in the country, the highest share since the Fed started tracking it in 1989. Back then it was 8.6%.""",
        "Fed DFA Q2 2026 record; top-1% wealth note scored 100.", "new chart: Federal Reserve")
    add("Employment", ch["wages"], """
Wages and salaries now make up 42% of national income, tied for the lowest share since 1948. In the early 1950s it was above 51%.""",
        "Labor-share theme (scored 82 and 137).", "new chart: BEA")
    # Wed Dec 9
    add("Incomes", ch["gdp"], """
Since 1984, GDP per person in America has doubled after inflation, while median household income is up 41%. Most of that growth went somewhere other than the typical family's paycheck.""",
        "Capital-vs-labor theme.", "new chart: BEA + Census")
    add("Incomes", ch["tax"], """
In 1960, the top federal income tax rate in America was 91%. Today it's 37%.""",
        "Two-number format of the corporate-tax note (scored 89).", "new chart: Piketty via OWID")
    # Thu Dec 10
    add("Incomes", ch["stocks"], """
The top 1% of Americans own 50.9% of all stocks. The bottom half of the country owns 0.6%.

I keep this in mind every time I see a headline about the stock market hitting another record.""",
        "Fed DFA Q2 2026.", "new chart: Federal Reserve")
    add("Housing", ch["own"], """
72.5% of white households in America own their home, compared with 45.9% of Black households, per new Census data. Owning a home is still how most families build wealth, so this gap carries straight into the racial wealth gap.""",
        "ACS 2025; race-gap notes drew replies.", "new chart: Census ACS")
    # Fri Dec 11
    add("Housing", ch["home"], """
After inflation, the price of a typical new home is up 68% since 1984, while median household income is up 41%. No wonder the typical first-time buyer is now 40.""",
        "Callback to the first-time buyer note (scored 91).", "new chart: Census/HUD + BLS")
    add("Incomes", ch["div"], """
Since 2000, the dividend income Americans receive has grown 484%. Wages and salaries are up 185% over the same period. Most dividend income goes to the households with the biggest stock portfolios.""",
        "BEA Q3 2026; capital-vs-labor theme.", "new chart: BEA")
    # Sat Dec 12
    add("Incomes", ch["hh200"], """
About 1 in 4 households in DC, Massachusetts and New Jersey now earn more than $200,000 a year. In Mississippi and West Virginia it's about 1 in 16.""",
        "ACS 2025; one map this week (maps were the weakest format).", "new map: Census ACS")
    add("Incomes", ch["anthropic"], """
Anthropic's 5,300 founders and employees are now worth about as much as the bottom third of US households combined, roughly 45 million families, in this chart from @[Steve Rattner](1658881).""",
        "Reshare: Rattner (Nov 20), wealth concentration; 53 likes / 31 restacks.", "reshare: Steve Rattner")
    # Sun Dec 13
    add("Housing", ch["rent"], f"""
The typical asking rent in America is now ${k['rent_now']:,.0f} a month, per Zillow. In October 2019 it was ${k['rent_then']:,.0f}.""",
        "Single-number format of the first-time buyer note (scored 91).", "big stat: Zillow")
    add("Incomes", ch["dems"], """
Democrats' biggest gains in the midterms came in Texas and the Deep South, per this chart from @[Steve Rattner](1658881). I'd love to see how much of that shift came from voters worried about rent, groceries and health care.""",
        "Reshare: Rattner (Nov 18); post-election notes performed well.", "reshare: Steve Rattner")
    return N


def main():
    ch, k = build()
    items = notes(ch, k)
    assert len(items) == 14, len(items)
    rng = random.Random(BATCH)
    cal = []
    for i, it in enumerate(items):
        day = START + timedelta(days=i // 2)
        block = (["midday", "evening"] if day.weekday() >= 5 else ["midday", "afternoon"])[i % 2]
        t = pick_time(day, block, rng)
        cal.append(dict(id=f"{t:%Y%m%d}-{i % 2 + 2}", scheduled_et=t.isoformat(), day=f"{t:%a %b %-d}",
                        time_et=f"{t:%-I:%M %p}", block=block, status="Scheduled", pillar=it["pillar"],
                        text=it["text"], chart=str(Path(it["chart"]).relative_to(ROOT)), why_now=it["why_now"],
                        source_kind=it["source_kind"]))
    (ROOT / "calendar" / f"{BATCH}.json").write_text(json.dumps(cal, indent=1))
    print(f"wrote {len(cal)} notes")


if __name__ == "__main__":
    main()
