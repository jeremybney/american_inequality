"""Net-new charts for the Nov 16 batch (replacing most reused American Inequality charts)."""
from aiq_notes import charts as C
from aiq_notes.acs import load_state
from aiq_notes.fred import series as S

BLUE, RED, GREY, SUB = C.BLUE, C.RED, C.GREY, C.SUB
ACS25 = "U.S. Census Bureau, American Community Survey 2025 1-year estimates"
NAMES = {'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','DC':'Washington, D.C.','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'}


def _f(t, y, c):
    return load_state(t, y)[c].astype(float)


def _x(s):
    return [d.year + (d.month - 1) / 12 for d in s.index]


def electricity(P):
    e, cpi = S("CUSR0000SEHF01").loc["2019":], S("CPIAUCSL").loc["2019":]
    ei, ci = 100 * e / e.loc["2021-01-01"] - 100, (100 * cpi / cpi.loc["2021-01-01"] - 100).reindex(e.index)
    return C.lines(P("electricity"), "Electricity bills have outrun inflation since 2021",
                   "Price change since January 2021",
                   [dict(x=_x(ei), y=list(ei.values), color=RED, label="Electricity"),
                    dict(x=_x(ci), y=list(ci.values), color=BLUE, label="All prices")],
                   "U.S. Bureau of Labor Statistics, CPI, via FRED (CUSR0000SEHF01, CPIAUCSL), through Oct. 2026",
                   yfmt="+{:.0f}%", xfmt="{:.0f}", label_fmt="+{:.0f}%")


def snap_map(P):
    s = (_f("b22003", 2025, "B22003_E002") / _f("b22003", 2025, "B22003_E001") * 100)
    return C.state_map(P("snap_map"), "In New Mexico, nearly 1 in 5 households get SNAP",
                       "Share of households that received SNAP (food stamps) in the past year, 2025",
                       s.drop(["US", "PR"], errors="ignore").to_dict(), f"{ACS25} (Table B22003)",
                       bins=[8, 10, 12, 14, 100], labels=["Under 8%", "8-10%", "10-12%", "12-14%", "14%+"],
                       legend_title="Blue = fewer households, red = more")


def credit_cards(P):
    b = S("CCLACBW027SBOG").loc["2015":] / 1000
    return C.lines(P("credit_card_debt"), "Americans now owe a record $1.1 trillion on credit cards",
                   "Credit card and revolving plan balances at U.S. commercial banks, trillions",
                   [dict(x=_x(b), y=list(b.values), color=BLUE)],
                   "Federal Reserve H.8 via FRED (CCLACBW027SBOG), through Nov. 4, 2026. Interest rate: Federal Reserve G.19 (TERMCBCCALLNS)",
                   end_labels=False, yfmt="${:.1f}T", xfmt="{:.0f}", ylim=(0.6, 1.2),
                   notes=[dict(text=f"${b.iloc[-1]:.2f}T, record high\naverage rate: 21%", xy=(_x(b)[-1], b.iloc[-1]),
                               xytext=(_x(b)[-1] - 4.2, 1.15), color=RED, bold=True)])


def child_poverty(P):
    c = load_state("b17020", 2025)
    v = {k: c["B17020_" + k].astype(float) for k in ["E003", "E004", "E005", "E011", "E012", "E013"]}
    cp = (v["E003"] + v["E004"] + v["E005"]) / (v["E003"] + v["E004"] + v["E005"] + v["E011"] + v["E012"] + v["E013"]) * 100
    return C.state_map(P("child_poverty_map"), "In Louisiana and Mississippi, 1 in 4 kids lives in poverty",
                       "Share of children under 18 living below the poverty line, 2025",
                       cp.drop(["US", "PR"], errors="ignore").to_dict(), f"{ACS25} (Table B17020). U.S. average: {cp['US']:.1f}%",
                       bins=[11, 14, 17, 20, 100], labels=["Under 11%", "11-14%", "14-17%", "17-20%", "20%+"],
                       legend_title="Blue = lower child poverty, red = higher")


def value_income(P):
    vi = _f("b25077", 2025, "B25077_E001") / _f("b19013", 2025, "B19013_E001")
    s = vi.drop(["US", "PR"], errors="ignore").sort_values(ascending=False)
    top, low = s.head(6), s.tail(4)
    labs = [NAMES[k] for k in top.index] + ["U.S. average"] + [NAMES[k] for k in low.index]
    vals = list(top.values) + [vi["US"]] + list(low.values)
    return C.hbars(P("home_value_income"), "In Hawaii, a home costs 8.6 years of income",
                   "Median home value divided by median household income, 2025",
                   labs, vals, f"{ACS25} (Tables B25077, B19013)",
                   highlight=tuple(range(6)), grey=(6,), fmt="{:.1f}x", xlim=(0, 9.6))


def rent_wages(P):
    r, w = S("CUSR0000SEHA").loc["2006-03":], S("CES0500000003")
    ri, wi = 100 * r / r.iloc[0] - 100, 100 * w / w.iloc[0] - 100
    return C.lines(P("rent_vs_wages"), "Rent has grown faster than paychecks for 20 years",
                   "Change since March 2006",
                   [dict(x=_x(ri), y=list(ri.values), color=RED, label="Rent"),
                    dict(x=_x(ri), y=list(wi.reindex(ri.index).values), color=BLUE, label="Hourly pay")],
                   "BLS CPI rent of primary residence and average hourly earnings, private sector, via FRED, through Oct. 2026",
                   yfmt="+{:.0f}%", xfmt="{:.0f}", label_fmt="+{:.0f}%")


def corp_tax(P):
    ct, pt = S("B075RC1Q027SBEA"), S("W006RC1Q027SBEA")
    sh = (ct / pt * 100).dropna().rolling(4).mean().dropna()
    return C.lines(P("corporate_tax_share"), "Corporations used to pay a third of federal taxes",
                   "Corporate income taxes as a share of federal current tax receipts, 4-quarter average",
                   [dict(x=_x(sh), y=list(sh.values), color=BLUE)],
                   "U.S. Bureau of Economic Analysis via FRED (B075RC1Q027SBEA, W006RC1Q027SBEA), through Q2 2026",
                   end_labels=False, yfmt="{:.0f}%", xfmt="{:.0f}", ylim=(0, sh.max() * 1.12),
                   notes=[dict(text=f"{sh.loc['1950':'1955'].mean():.0f}% in the early 1950s", xy=(1954.5, sh.loc['1950':'1955'].mean()),
                               xytext=(1966, sh.max() * 1.05), color=BLUE, bold=True),
                          dict(text=f"Today: {sh.iloc[-1]:.0f}%", xy=(_x(sh)[-1], sh.iloc[-1]),
                               xytext=(_x(sh)[-1] - 6, sh.iloc[-1] + 12), color=RED, bold=True)])


def kids_uninsured(P):
    k = _f("b27010", 2025, "B27010_E017") / _f("b27010", 2025, "B27010_E002") * 100
    return C.state_map(P("kids_uninsured_map"), "In Texas, 1 in 8 kids has no health insurance",
                       "Share of children under 19 with no health insurance, 2025",
                       k.drop(["US", "PR"], errors="ignore").to_dict(), f"{ACS25} (Table B27010). U.S. average: {k['US']:.1f}%",
                       bins=[4, 5.5, 7, 9, 100], labels=["Under 4%", "4-5.5%", "5.5-7%", "7-9%", "9%+"],
                       legend_title="Blue = fewer uninsured kids, red = more")


def median_income(P):
    m = S("MEHOINUSA672N")
    x = [d.year for d in m.index]
    return C.lines(P("median_income"), "Median household income just hit a record",
                   "Real median household income, 2025 dollars",
                   [dict(x=x, y=list(m.values), color=BLUE)],
                   "U.S. Census Bureau, Current Population Survey ASEC, via FRED (MEHOINUSA672N), through 2025",
                   end_labels=False, yfmt="${:,.0f}", xfmt="{:.0f}",
                   notes=[dict(text=f"2025: ${m.iloc[-1]:,.0f}", xy=(x[-1], m.iloc[-1]),
                               xytext=(x[-1] - 7, m.iloc[-1] + 1500), color=RED, bold=True)])


def rent_jumps(P):
    r, r24 = _f("b25064", 2025, "B25064_E001"), _f("b25064", 2024, "B25064_E001")
    rc = ((r / r24 - 1) * 100).drop(["US", "PR"], errors="ignore").sort_values(ascending=False).head(8)
    us = (r["US"] / r24["US"] - 1) * 100
    labs = [NAMES[k] for k in rc.index] + ["U.S. average"]
    return C.hbars(P("rent_jumps"), "The biggest rent jumps weren't where you'd think",
                   "Change in median gross rent, 2024 to 2025, top 8 states",
                   labs, list(rc.values) + [us], f"{ACS25} and 2024 1-year estimates (Table B25064)",
                   highlight=(0,), grey=(8,), fmt="+{:.1f}%", xlim=(0, 14), inside=True)


def gas(P):
    g = S("GASREGW").loc["2021":]
    return C.lines(P("gas_prices"), "Gas is $4 again", "U.S. regular gasoline, average retail price per gallon",
                   [dict(x=_x(g), y=list(g.values), color=BLUE)],
                   "U.S. Energy Information Administration via FRED (GASREGW), week of Nov. 9, 2026",
                   end_labels=False, yfmt="${:.2f}", xfmt="{:.0f}",
                   notes=[dict(text=f"${g.iloc[-1]:.2f}\nyear ago: ${g.iloc[-53]:.2f}", xy=(_x(g)[-1], g.iloc[-1]),
                               xytext=(_x(g)[-1] - 1.3, g.iloc[-1] + 0.75), color=RED, bold=True)])


def poverty_race(P):
    rows = [("Black", "b17001b"), ("American Indian\nand Alaska Native", "b17001c"), ("Hispanic", "b17001i"),
            ("All Americans", "b17001"), ("White", "b17001a"), ("Asian", "b17001d")]
    vals = [_f(t, 2025, f"{t.upper()}_E002")["US"] / _f(t, 2025, f"{t.upper()}_E001")["US"] * 100 for _, t in rows]
    return C.hbars(P("poverty_by_race"), "Black and Native Americans are twice as likely to be poor",
                   "Share of people living below the poverty line",
                   [r[0] for r in rows], vals, f"{ACS25} (B17001, B17001A-I). Hispanic may be of any race",
                   highlight=(0, 1), grey=(3,), fmt="{:.1f}%", xlim=(0, 24), inside=True)
