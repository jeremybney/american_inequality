"""Batch: Mon Nov 16 - Sun Nov 29, 2026 (42 notes).

Run:  python3 batches/b2026_11_16.py
Writes charts to charts/2026-11-16/ and the calendar to calendar/2026-11-16.json.
"""
import json
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from PIL import Image

from aiq_notes import charts as C
from aiq_notes.acs import load_state
from aiq_notes.fred import series as S
from aiq_notes.schedule import pick_time, ET
from aiq_notes import batch_nov16_new as NEW

BATCH = "2026-11-16"
START = date(2026, 11, 16)
OUT = ROOT / "charts" / BATCH
OUT.mkdir(parents=True, exist_ok=True)
EXISTING = ROOT / "existing"          # Jeremy's own previously published charts
P = lambda name: str(OUT / f"{name}.png")


def existing(name, src):
    """Copy one of Jeremy's published charts into this batch (normalised to PNG)."""
    im = Image.open(EXISTING / src).convert("RGB")
    im.save(P(name))
    return P(name)


# ---------------------------------------------------------------------------
# New charts from fresh government data
# ---------------------------------------------------------------------------
def ch_labor_share():
    s = S("PRS85006173")
    x = [d.year + (d.month - 1) / 12 for d in s.index]
    return C.lines(P("labor_share"), "Workers' share of the economy just hit a record low",
                   "Labor share of output, nonfarm business sector (index, 2017 = 100)",
                   [dict(x=x, y=list(s.values), color=BLUE)],
                   "U.S. Bureau of Labor Statistics via FRED (PRS85006173), data through Q3 2026",
                   end_labels=False, xfmt="{:.0f}",
                   notes=[dict(text="Q3 2026: lowest\nsince records began", xy=(x[-1], s.iloc[-1]),
                               xytext=(x[-1] - 20, s.iloc[-1] + 0.5), color=RED, bold=True)])


def ch_profit_share():
    cp, g = S("CP"), S("GDP")
    s = (cp / g * 100).dropna()
    s = s[s.index >= "1960-01-01"]
    x = [d.year + (d.month - 1) / 12 for d in s.index]
    return C.lines(P("profit_share"), "Corporate profits just hit a record share of the economy",
                   "Corporate profits after tax as a share of GDP",
                   [dict(x=x, y=list(s.values), color=BLUE)],
                   "U.S. Bureau of Economic Analysis via FRED (CP, GDP), data through Q2 2026",
                   end_labels=False, xfmt="{:.0f}", yfmt="{:.0f}%",
                   notes=[dict(text=f"{s.iloc[-1]:.1f}%\nall-time high", xy=(x[-1], s.iloc[-1]),
                               xytext=(x[-1] - 8, s.iloc[-1] + 0.6), color=RED, bold=True)])


def ch_wealth():
    t, b = S("WFRBST01134"), S("WFRBSB50215")
    x = [d.year + (d.month - 1) / 12 for d in t.index]
    return C.lines(P("wealth_top1_bottom50"), "The top 1% own 14x more than the entire bottom half",
                   "Share of total U.S. household wealth",
                   [dict(x=x, y=list(t.values), color=RED, label="Top 1%"),
                    dict(x=x, y=list(b.values), color=BLUE, label="Bottom 50%")],
                   "Federal Reserve, Distributional Financial Accounts, via FRED, data through Q2 2026",
                   yfmt="{:.0f}%", ylim=(0, 36), xfmt="{:.0f}", label_fmt="{:.1f}%")


def ch_min_wage():
    mw, cpi = S("FEDMINNFRWG"), S("CPIAUCSL")
    m = mw.resample("MS").ffill().reindex(cpi.index).ffill().dropna()
    real = (m * cpi.iloc[-1] / cpi.reindex(m.index)).loc["1950":]
    x = [d.year + (d.month - 1) / 12 for d in real.index]
    pk = real.idxmax()
    return C.lines(P("real_min_wage"), "The minimum wage is worth the least since 1949",
                   "Federal minimum wage, adjusted to October 2026 dollars",
                   [dict(x=x, y=list(real.values), color=BLUE)],
                   "U.S. Department of Labor via FRED (FEDMINNFRWG), adjusted with BLS CPI-U",
                   end_labels=False, yfmt="${:.0f}", ylim=(0, 18), xfmt="{:.0f}",
                   notes=[dict(text=f"1968: ${real.max():.2f}", xy=(pk.year + 0.1, real.max()),
                               xytext=(pk.year + 9, 17.0), color=BLUE, bold=True),
                          dict(text="Today: $7.25\nunchanged since 2009", xy=(x[-1], real.iloc[-1]),
                               xytext=(x[-1] - 10, 3.2), color=RED, bold=True)])


def ch_black_white():
    w, b = S("LNS14000003"), S("LNS14000006")
    w = w.loc["1972":]
    b = b.loc["1972":]
    x = [d.year + (d.month - 1) / 12 for d in b.index]
    return C.lines(P("black_white_unemployment"), "Black unemployment has run near double white for 50 years",
                   "Unemployment rate, seasonally adjusted, monthly",
                   [dict(x=x, y=list(b.values), color=RED, label="Black"),
                    dict(x=x, y=list(w.reindex(b.index).values), color=BLUE, label="White")],
                   "U.S. Bureau of Labor Statistics, Current Population Survey, via FRED, through Oct. 2026",
                   yfmt="{:.0f}%", xfmt="{:.0f}", label_fmt="{:.1f}%", ylim=(0, 22))


def ch_ppi():
    pp = S("PPIFIS")
    y = (100 * (pp / pp.shift(12) - 1)).dropna().loc["2019":]
    x = [d.year + (d.month - 1) / 12 for d in y.index]
    return C.lines(P("ppi"), "Wholesale prices are rising at the fastest pace since 2022",
                   "Producer Price Index for final demand, change from a year earlier",
                   [dict(x=x, y=list(y.values), color=BLUE)],
                   "U.S. Bureau of Labor Statistics via FRED (PPIFIS), through Oct. 2026",
                   end_labels=False, yfmt="{:.0f}%", xfmt="{:.0f}",
                   notes=[dict(text=f"Oct. 2026: +{y.iloc[-1]:.1f}%", xy=(x[-1], y.iloc[-1]),
                               xytext=(x[-1] - 1.4, y.iloc[-1] + 3.0), color=RED, bold=True)])


def ch_grocery():
    f = S("CUSR0000SAF11").loc["2019":]
    idx = 100 * f / f.loc["2021-01-01"]
    x = [d.year + (d.month - 1) / 12 for d in idx.index]
    pct = idx.iloc[-1] - 100
    return C.lines(P("groceries"), f"Groceries cost {pct:.0f}% more than they did in January 2021",
                   "Consumer Price Index, food at home (January 2021 = 100)",
                   [dict(x=x, y=list(idx.values), color=BLUE)],
                   "U.S. Bureau of Labor Statistics via FRED (CUSR0000SAF11), through Oct. 2026",
                   end_labels=False, xfmt="{:.0f}",
                   notes=[dict(text=f"+{pct:.0f}%", xy=(x[-1], idx.iloc[-1]),
                               xytext=(x[-1] - 1.0, idx.iloc[-1] + 4), color=RED, bold=True)])


def ch_mortgage():
    p, mr = S("MSPUS"), S("MORTGAGE30US")

    def pay(price, rate):
        r = rate / 1200
        return price * 0.8 * r / (1 - (1 + r) ** -360)
    yrs = [str(y) for y in range(2019, 2026)]
    vals = [pay(p.loc[y].mean(), mr.loc[y].mean()) for y in yrs] + [pay(p.iloc[-1], mr.iloc[-1])]
    labels = yrs + ["Now"]
    return C.bars(P("mortgage_payment"), "Same house, $830 more a month",
                  "Monthly principal + interest on the median-priced new home, 20% down, 30-year fixed",
                  labels, vals, "Census/HUD (MSPUS) and Freddie Mac (MORTGAGE30US) via FRED; author's calculation",
                  highlight=(len(vals) - 1,), fmt="${:,.0f}", yfmt="${:,.0f}", ylim=(0, 2600),
                  note="Annual averages; Now = Q3 2026 price, Nov. 12 rate")


def ch_productivity():
    o, c = S("OPHNFB"), S("COMPRNFB")
    o, c = o.loc["1973":], c.loc["1973":]
    oi, ci = 100 * o / o.iloc[0], 100 * c / c.iloc[0]
    x = [d.year + (d.month - 1) / 12 for d in oi.index]
    return C.lines(P("productivity_pay"), "Workers produce 163% more than in 1973. Pay is up 64%.",
                   "Cumulative change since 1973, nonfarm business sector",
                   [dict(x=x, y=list(oi.values - 100), color=BLUE, label="Productivity"),
                    dict(x=x, y=list(ci.values - 100), color=RED, label="Real pay per hour")],
                   "U.S. Bureau of Labor Statistics via FRED (OPHNFB, COMPRNFB), through Q3 2026. Pay = real hourly compensation",
                   yfmt="+{:.0f}%", xfmt="{:.0f}", label_fmt="+{:.0f}%")


def ch_saving():
    s = S("PSAVERT").loc["2015":]
    x = [d.year + (d.month - 1) / 12 for d in s.index]
    return C.lines(P("saving_rate"), "Americans are saving less than at any point since 2022",
                   "Personal saving as a share of disposable income",
                   [dict(x=x, y=list(s.values), color=BLUE)],
                   "U.S. Bureau of Economic Analysis via FRED (PSAVERT), through Sept. 2026",
                   end_labels=False, yfmt="{:.0f}%", xfmt="{:.0f}",
                   notes=[dict(text=f"{s.iloc[-1]:.1f}%", xy=(x[-1], s.iloc[-1]),
                               xytext=(x[-1] - 0.8, s.iloc[-1] + 6), color=RED, bold=True),
                          dict(text="Pandemic checks", xy=(2020.3, 31), xytext=(2017.2, 28), color=SUB)])


def ch_edu_unemp():
    a, b = S("LNS14027662"), S("LNS14027659")
    a, b = a.rolling(3).mean().dropna(), b.rolling(3).mean().dropna()
    x = [d.year + (d.month - 1) / 12 for d in b.index]
    return C.lines(P("unemployment_education"), "No diploma, double the unemployment",
                   "Unemployment rate, ages 25+, 3-month average",
                   [dict(x=x, y=list(b.values), color=RED, label="No diploma"),
                    dict(x=x, y=list(a.reindex(b.index).values), color=BLUE, label="Bachelor's degree+")],
                   "U.S. Bureau of Labor Statistics, Current Population Survey, via FRED, through Oct. 2026",
                   yfmt="{:.0f}%", xfmt="{:.0f}", label_fmt="{:.1f}%")


def acs_maps():
    g = load_state("b19083", 2025)["B19083_E001"].astype(float)
    gini = C.state_map(P("gini_map"), "New York is now the most unequal state in America",
                       "Gini index of household income inequality, 2025 (higher = more unequal)",
                       g.drop(["US", "PR"], errors="ignore").to_dict(),
                       "U.S. Census Bureau, American Community Survey 2025 1-year estimates (Table B19083)",
                       bins=[0.455, 0.465, 0.475, 0.485, 1], labels=["Under .455", ".455-.465", ".465-.475", ".475-.485", ".485+"],
                       legend_title="Blue = more equal, red = more unequal")
    gs = g.drop(["US", "PR"], errors="ignore").sort_values()
    top = gs.tail(5)[::-1]
    low = gs.head(5)[::-1]
    names = {"NY": "New York", "DC": "Washington, D.C.", "CT": "Connecticut", "LA": "Louisiana", "CA": "California",
             "UT": "Utah", "NH": "New Hampshire", "AK": "Alaska", "DE": "Delaware", "ID": "Idaho"}
    labs = [names.get(k, k) for k in list(top.index) + list(low.index)]
    vals = list(top.values) + list(low.values)
    gbar = C.hbars(P("gini_bars"), "The most and least unequal states in America",
                   "Gini index of household income inequality, 2025 (higher = more unequal)",
                   labs, vals, "U.S. Census Bureau, American Community Survey 2025 1-year estimates (Table B19083)",
                   highlight=tuple(range(5)), fmt="{:.3f}", xlim=(0.40, 0.54))

    r = load_state("b25071", 2025)["B25071_E001"].astype(float)
    rent = C.state_map(P("rent_burden_map"), "Florida renters are the most rent-burdened in America",
                       "Median gross rent as a share of household income, 2025",
                       r.drop(["US", "PR"], errors="ignore").to_dict(),
                       "U.S. Census Bureau, American Community Survey 2025 1-year estimates (Table B25071)",
                       bins=[27, 29, 30.5, 32, 100], labels=["Under 27%", "27-29%", "29-30.5%", "30.5-32%", "32%+"],
                       legend_title="Blue = less burdened, red = more burdened")

    b = load_state("b25070", 2025)
    for c in ["E001", "E007", "E008", "E009", "E010", "E011"]:
        b[c] = b["B25070_" + c].astype(float)
    sev = (b.E010 / (b.E001 - b.E011) * 100)
    sv = sev.drop(["US", "PR"], errors="ignore").sort_values(ascending=False).head(10)
    full = {"FL": "Florida", "CA": "California", "HI": "Hawaii", "NY": "New York", "CT": "Connecticut",
            "MS": "Mississippi", "LA": "Louisiana", "MI": "Michigan", "OR": "Oregon", "NJ": "New Jersey"}
    labs = [full.get(k, k) for k in sv.index] + ["U.S. average"]
    vals = list(sv.values) + [sev["US"]]
    sevbar = C.hbars(P("severe_rent_burden"), "In Florida, nearly 1 in 3 renters spend over half their income on rent",
                     "Share of renter households paying 50%+ of income on rent, 2025, top 10 states",
                     labs, vals, "U.S. Census Bureau, American Community Survey 2025 1-year estimates (Table B25070)",
                     highlight=(0,), grey=(10,), fmt="{:.1f}%", xlim=(0, 36), inside=True)
    burdened = int(b.E007["US"] + b.E008["US"] + b.E009["US"] + b.E010["US"])
    return gini, gbar, rent, sevbar, burdened, int(b.E010["US"])


BLUE, RED, SUB = C.BLUE, C.RED, C.SUB


def build():
    gini, gini_bars, rent_map, severe, burdened, severe_n = acs_maps()
    ch = dict(
        labor=ch_labor_share(), profit=ch_profit_share(), wealth=ch_wealth(), minwage=ch_min_wage(),
        bw=ch_black_white(), ppi=ch_ppi(), grocery=ch_grocery(), mortgage=ch_mortgage(),
        productivity=ch_productivity(), saving=ch_saving(), edu=ch_edu_unemp(),
        gini=gini, gini_bars=gini_bars, rent_map=rent_map, severe=severe,
        electricity=NEW.electricity(P), credit=NEW.credit_cards(P), childpov=NEW.child_poverty(P),
        valinc=NEW.value_income(P), rentwage=NEW.rent_wages(P), corptax=NEW.corp_tax(P),
        income=NEW.median_income(P), kids=NEW.kids_uninsured(P), snapmap=NEW.snap_map(P),
        rentjump=NEW.rent_jumps(P), gas=NEW.gas(P), povrace=NEW.poverty_race(P),
        # Jeremy's previously published charts: only his best performers
        # (top articles by likes/restacks) and only where today's news makes them new again
        insurance=existing("insurance_71", "stealth_insurance_premiums_map.webp"),
        billmap=existing("billionaires_blue_states", "billionaires_blue_states_map.png"),
        homeless=existing("homelessness_trend", "homelessness_trend.png"),
        giving=existing("affluent_giving", "affluent_giving.png"),
    )
    st = dict(
        snap=C.big_stat(P("stat_snap"), "6.3M", "Americans who would lose SNAP under the USDA's new rule",
                        "Proposed November 10, about two weeks before Thanksgiving.",
                        "USDA proposed rule, as reported by Reuters and The New York Times, Nov. 10, 2026",
                        kicker="Food assistance"),
        buyer=C.big_stat(P("stat_first_time_buyer"), "40", "The median age of a first-time homebuyer in America",
                         "In 1981, it was 29.", "National Association of Realtors, 2026 Profile of Home Buyers and Sellers",
                         kicker="Housing"),
        burdened=C.big_stat(P("stat_cost_burdened"), f"{burdened/1e6:.1f}M",
                            "renter households are cost burdened",
                            f"52% of renters paid 30%+ of income on rent in 2025. {severe_n/1e6:.1f} million paid over half.",
                            "U.S. Census Bureau, American Community Survey 2025 1-year estimates (Table B25070)",
                            kicker="New Census data"),
        homeless_kids=C.big_stat(P("stat_homeless_students"), "1.5M", "homeless students counted by public schools in 2023-24",
                                 "Most since national reporting began in 2004.",
                                 "U.S. Department of Education (EDFacts); HUD 2025 Annual Homeless Assessment Report",
                                 kicker="Two ways to count", compare=("133,962", "children under 18\ncounted by HUD (2025)")),
        tipped=C.big_stat(P("stat_tipped_wage"), "$2.13", "the federal minimum cash wage for tipped workers",
                          "Unchanged since 1991. The regular minimum, $7.25, hasn't moved since 2009.",
                          "U.S. Department of Labor, Wage and Hour Division", kicker="If you're eating out"),
        insurers=C.big_stat(P("stat_insurer_premiums"), "$1.03T", "in premiums collected by U.S. property insurers last year",
                            "The most ever. More than the entire U.S. military budget.",
                            "NAIC data as analyzed by the Vanderbilt Policy Accelerator; American Inequality",
                            kicker="Home insurance"),
        starter=C.big_stat(P("stat_starter_homes"), "242", "U.S. cities where a typical starter home costs $1 million+",
                           "A record. A starter home.", "Zillow, as reported by Fortune, Nov. 7, 2026", kicker="Housing"),
        top1=C.big_stat(P("stat_top1_share"), "32.5%", "of all U.S. wealth is held by the top 1%",
                        "1989: 22.8%   2000: 27.9%   2008: 28.9%   2020: 29.0%   2026: 32.5%",
                        "Federal Reserve, Distributional Financial Accounts, Q2 2026", kicker="A record high"),
        transfer=C.big_stat(P("stat_wealth_transfer"), "$84T", "will pass from older Americans to their heirs by 2045",
                            "The largest wealth transfer in history.", "Cerulli Associates; American Inequality, \"The Great Generational Wealth Divide\"",
                            kicker="Inheritance"),
    )
    return ch, st


# ---------------------------------------------------------------------------
# The calendar. Order inside each day = morning, midday, afternoon/evening.
# ---------------------------------------------------------------------------
def notes(ch, st):
    N = []

    def add(pillar, chart, text, why, source_kind):
        N.append(dict(pillar=pillar, chart=chart, text=text.strip(), why_now=why, source_kind=source_kind))

    # Mon Nov 16
    add("Employment", ch["labor"], """
Workers' share of the economy just hit the lowest level ever recorded.

BLS has tracked this since 1947. It has never been lower than it is right now.""",
        "New BLS productivity release (Q3 2026) shows labor share at a record low.", "new chart: BLS")
    add("Incomes", ch["electricity"], """
Electricity prices are up 43% since January 2021. Prices overall are up 28.5%.

Lower-income families spend a much bigger share of their budget on utilities, so they feel this first. With data centers pulling more power every month, I don't see it slowing down.""",
        "Oct CPI; winter utility bills; data-center power demand in the news.", "new chart: BLS")
    add("Incomes", ch["billmap"], """
California just voted down a billionaire tax after tech spent $425 million to kill it.

Worth remembering where new billionaires come from. 64% of the ones minted last year came from states where Democrats control both the governor's office and the legislature.

Blue states are great at making billionaires. Taxing them is another story.""",
        "Prop 40 failed Nov 10 after record tech spending.", "my chart: blue-state billionaires")
    # Tue Nov 17
    add("Incomes", st["snap"], """
The USDA wants to cut 6.3 million more people off SNAP. They announced it two weeks before Thanksgiving.

Food banks were already saying demand is up this year. This makes it a lot worse.""",
        "USDA proposed SNAP rule (Nov 10); Thanksgiving week coming.", "big stat: USDA")
    add("Incomes", ch["wealth"], """
The top 1% now own 32.5% of all the wealth in America. A record.

The entire bottom half of the country owns 2.3%.

1% of households have 14 times the wealth of 50% of households.""",
        "Fed DFA Q2 2026 shows record top-1% share.", "new chart: Federal Reserve")
    add("Incomes", ch["credit"], """
Americans now owe a record $1.1 trillion on their credit cards. The average interest rate is 21%.

Carrying a balance at 21% is one of the most expensive ways to be broke in America.""",
        "Fed H.8 weekly data (Nov 4) shows a new record; Fed hike expected in December.", "new chart: Federal Reserve")
    # Wed Nov 18
    add("Incomes", ch["gini"], """
New York is now the most unequal state in America, per new Census data. Then DC, Connecticut, Louisiana and California.

The most equal state? Utah.

A lot of deep blue on the unequal end of this map. Something to sit with now that Democrats run Congress.""",
        "ACS 2025 1-year estimates just released.", "new map: Census ACS")
    add("Incomes", ch["childpov"], """
In Louisiana, 25% of kids live below the poverty line. Mississippi: 24.6%. DC: 24.5%.

Nationally it's 14.8%. In the richest country in the world.""",
        "ACS 2025 1-year estimates.", "new map: Census ACS")
    add("Employment", ch["minwage"], """
Democrats just won the House and the Senate. Here's where I'd start.

The federal minimum wage has been $7.25 since July 2009. After inflation, it's now worth less than at any point since 1949.

In 1968 it was worth $15.79 in today's dollars.""",
        "New Democratic Congress; Oct CPI release.", "new chart: DOL + BLS")
    # Thu Nov 19
    add("Employment", ch["bw"], """
Black unemployment in October: 6.6%. White unemployment: 3.7%.

This chart goes back to 1972. Booms, recessions, recoveries. The gap barely moves.""",
        "October jobs report (Nov 6).", "new chart: BLS")
    add("Housing", ch["homeless"], """
HUD is calling its new count the biggest drop in homelessness on record, down 6.3%.

Maybe. But last year HUD led with a 3.3% drop too, and buried the fact that chronic homelessness hit its highest level ever.

I'll wait for the full data before I celebrate a press release.""",
        "HUD point-in-time announcement (Nov 7-10); ties to my July reporting.", "my chart: homelessness")
    add("Housing", ch["rent_map"], """
Florida renters now spend a median 35.5% of their income on rent. Highest in the country, and it isn't close.

California is next at 32.9%. North Dakota is the lowest at 23.8%.""",
        "ACS 2025 1-year estimates.", "new map: Census ACS")
    # Fri Nov 20
    add("Housing", st["buyer"], """
The typical first-time homebuyer in America is now 40 years old. In 1981 it was 29.

And a record share of first-time buyers paid all cash this year. That money isn't coming from paychecks. It's coming from parents.""",
        "NAR Profile of Home Buyers and Sellers (Nov 5).", "big stat: NAR")
    add("Housing", ch["valinc"], """
In Hawaii, the typical home costs 8.6 times the typical household income. California: 7.5x.

West Virginia: 2.9x.

The old rule of thumb was a home should cost about 3 years of income. Most of the country left that behind a long time ago.""",
        "Follows the NAR first-time buyer news; ACS 2025.", "new chart: Census ACS")
    add("Housing", ch["severe"], """
11.4 million renter households now spend more than half their income on rent.

In Florida it's nearly 1 in 3 renters.""",
        "ACS 2025 1-year estimates.", "new chart: Census ACS")
    # Sat Nov 21
    add("Housing", ch["insurance"], """
Rent: up 30% from 2018 to 2024.
Home insurance premiums: up 71%.

Insurers say it's climate. Their loss ratios say they paid out about 55 cents of every premium dollar in 2025. The historical average is 80.""",
        "Evergreen from my insurance piece; open enrollment/renewal season.", "my chart: stealth tax")
    add("Employment", ch["profit"], """
Corporate profits are now a bigger share of the economy than at any point on record.

Earlier this week: workers' share just hit a record low.

Same economy.""",
        "BEA Q2 data; callback to Monday's labor share note.", "new chart: BEA")
    add("Housing", ch["rentwage"], """
Since 2006, rent is up 103%. Hourly pay is up 90%.

That gap doesn't sound huge until you remember it compounds every month for 20 years.""",
        "Weekend evening; Oct CPI and jobs data.", "new chart: BLS")
    # Sun Nov 22
    add("Incomes", ch["corptax"], """
In the early 1950s, corporate income taxes made up about a third of federal tax revenue. Today it's 14%.

And California voters just rejected a billionaire tax too. The bill keeps shifting to paychecks.""",
        "Prop 40 aftermath; BEA Q2 data.", "new chart: BEA")
    add("Incomes", ch["ppi"], """
Wholesale prices are up 6.5% from a year ago, the fastest pace since 2022.

That's what businesses pay. It shows up on store shelves a few months later, right around the holidays.

Inflation hits hardest at the bottom, where families spend nearly everything they make.""",
        "PPI release (Nov 13); Fed signaling a December hike.", "new chart: BLS")
    add("Incomes", ch["income"], """
Some actual good news: real median household income hit a record $87,460 in 2025.

Now put it next to the other record from this week. The top 1% hold 32.5% of all wealth.

Both are true at the same time.""",
        "Census income data; balances the record-inequality notes earlier in the week.", "new chart: Census")
    # Mon Nov 23
    add("Healthcare", ch["kids"], """
4.6 million kids in America have no health insurance. In Texas it's 1 in 8.

Most uninsured kids already qualify for Medicaid or CHIP. Their families just aren't enrolled. Open enrollment runs through January 15.""",
        "2027 ACA open enrollment; ACS 2025 shows uninsured kids rising in 32 states.", "new map: Census ACS")
    add("Housing", st["burdened"], """
Half of all renters in America are now cost burdened. 22.5 million households, per new Census data.

That used to be the crisis scenario. Now it's the baseline.""",
        "ACS 2025 1-year estimates.", "big stat: Census ACS")
    add("Housing", ch["mortgage"], """
Same median-priced new home. Same 20% down.

2021 monthly payment: $1,285
Today: $2,117

$830 more every month, and prices barely came down.""",
        "Mortgage rates back above 7%; Fed hike expected.", "new chart: Census/HUD + Freddie Mac")
    # Tue Nov 24
    add("Incomes", ch["snapmap"], """
Two days before Thanksgiving, here's who relies on SNAP right now.

15.4 million households got food assistance in 2025. In New Mexico it's nearly 1 in 5. In Oregon, West Virginia and New York, about 1 in 6.

The USDA wants to cut 6.3 million people from the program.""",
        "Thanksgiving week; USDA proposed SNAP rule (Nov 10).", "new map: Census ACS")
    add("Education", st["homeless_kids"], """
Public schools counted 1.5 million homeless students. HUD's count of homeless kids: about 134,000.

That's an 11x gap. HUD doesn't count families doubled up with relatives or sleeping on a friend's couch. Schools do.

How you define a problem decides how big it looks.""",
        "HUD's 'record drop' announcement; follow-up to Thursday's note.", "big stat: Ed + HUD")
    add("Housing", ch["rentjump"], """
The biggest rent increases last year weren't in New York or California.

New Hampshire: +11.8%. Maine: +9.8%. South Carolina: +9.7%. Then the Dakotas and Wyoming.

The national average was 4.7%. When everyone moves somewhere cheap, it stops being cheap.""",
        "ACS 2025 vs 2024; Realtor.com rent-hike coverage (Nov 12).", "new chart: Census ACS")
    # Wed Nov 25
    add("Incomes", ch["gas"], """
Driving to Thanksgiving? Gas is averaging $4.00 a gallon. A year ago it was $3.06.

That's a 31% jump, and it hits hardest for people who can't work from home.""",
        "Thanksgiving travel day; EIA weekly prices.", "new chart: EIA")
    add("Incomes", ch["grocery"], """
The Farm Bureau says Thanksgiving dinner got slightly cheaper this year. Good.

Groceries overall still cost 28% more than they did in January 2021. That's the number families are actually living with.""",
        "Farm Bureau Thanksgiving survey (Nov 9); Oct CPI.", "new chart: BLS")
    add("Incomes", ch["giving"], """
91% of affluent households gave to charity a decade ago. In 2024 it was 81%.

For everyone else it fell from 56% to 41%. That part isn't stinginess. Rent and groceries come first.""",
        "Thanksgiving / Giving Tuesday run-up.", "my chart: philanthropy")
    # Thu Nov 26 (Thanksgiving)
    add("Incomes", ch["povrace"], """
Happy Thanksgiving. It's also Native American Heritage Month.

18.1% of American Indian and Alaska Native people live below the poverty line, per new Census data. Black Americans: 19.9%. White Americans: 9.4%.""",
        "Thanksgiving + Native American Heritage Month; ACS 2025.", "new chart: Census ACS")
    add("Employment", st["tipped"], """
If you're eating out today, the federal minimum wage for your server is $2.13 an hour.

It hasn't changed since 1991.""",
        "Thanksgiving restaurant traffic.", "big stat: DOL")
    add("Employment", ch["labor"], """
Bringing one chart to the family economics debate tonight? This would be mine.

Workers' share of the economy is the lowest it's been since BLS started measuring in 1947.

What's yours?""",
        "Thanksgiving night; reply-bait question on a proven chart.", "new chart: BLS (reused)")
    # Fri Nov 27 (Black Friday)
    add("Incomes", ch["saving"], """
Americans are saving 3.8% of their income, the lowest since 2022.

Expect record Black Friday headlines anyway. A lot of that spending comes from the top. For most families, the cushion is getting thin.""",
        "Black Friday; BEA personal income release.", "new chart: BEA")
    add("Housing", st["insurers"], """
Property insurers collected $1.03 trillion in premiums last year. The most ever, and more than the entire US military budget.

Meanwhile the five biggest home insurers didn't pay out on 44% of claims.""",
        "Evergreen insurance stat.", "big stat: NAIC/Vanderbilt")
    add("Housing", st["starter"], """
There are now 242 cities in America where a typical starter home costs $1 million or more.

A starter home.""",
        "Zillow/Fortune report (Nov 7).", "big stat: Zillow")
    # Sat Nov 28
    add("Incomes", st["top1"], """
Share of all US wealth held by the top 1%:

1989: 22.8%
2000: 27.9%
2008: 28.9%
2020: 29.0%
2026: 32.5%

It only goes one direction.""",
        "Ladder format (my CEO-pay ladder note was a top performer).", "big stat: Federal Reserve")
    add("Employment", ch["edu"], """
Unemployment for adults without a high school diploma: 4.9%. With a bachelor's degree: 2.6%. (Three-month averages through October.)

The gap has been there for as long as this data has existed.""",
        "October jobs report.", "new chart: BLS")
    add("Incomes", ch["gini_bars"], """
Quick one: the five most unequal states in America, and the five most equal, from new Census data.

Only one of the top five voted for Trump.""",
        "ACS 2025; weekend-evening engagement format.", "new chart: Census ACS")
    # Sun Nov 29
    add("Incomes", st["transfer"], """
$84 trillion is going to pass from older Americans to their heirs by 2045. The biggest wealth transfer in history.

It's mostly going to the people who already had a head start.""",
        "Holiday weekend family/estate conversations.", "big stat: Cerulli")
    add("Employment", ch["productivity"], """
Since 1973, American workers have become 163% more productive.

Their real pay per hour is up 64%.

Where did the rest go? See: corporate profits, record high. Top 1% share of wealth, record high.""",
        "Wrap-up of the month's labor-share thread.", "new chart: BLS")
    add("Housing", ch["rent_map"], """
Back to work tomorrow, so one more from the new Census data.

Median rent as a share of income: 35.5% in Florida, 23.8% in North Dakota. Same country, wildly different math.

What should I map next?""",
        "Sunday evening reply-bait.", "new map: Census ACS (reused)")
    return N


def main():
    ch, st = build()
    items = notes(ch, st)
    assert len(items) == 42, len(items)
    rng = random.Random(BATCH)
    cal = []
    for i, it in enumerate(items):
        day = START + timedelta(days=i // 3)
        block = (["morning", "midday", "evening"] if day.weekday() >= 5 else ["morning", "midday", "afternoon"])[i % 3]
        t = pick_time(day, block, rng)
        nid = f"{t:%Y%m%d}-{i % 3 + 1}"
        cal.append(dict(id=nid, scheduled_et=t.isoformat(), day=f"{t:%a %b %-d}", time_et=f"{t:%-I:%M %p}",
                        block=block, status="Scheduled", pillar=it["pillar"], text=it["text"],
                        chart=str(Path(it["chart"]).relative_to(ROOT)), why_now=it["why_now"],
                        source_kind=it["source_kind"]))
    (ROOT / "calendar").mkdir(exist_ok=True)
    (ROOT / "calendar" / f"{BATCH}.json").write_text(json.dumps(cal, indent=1))
    print(f"wrote {len(cal)} notes")


if __name__ == "__main__":
    main()
