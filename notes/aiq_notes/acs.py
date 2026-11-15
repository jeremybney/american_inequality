"""Read ACS table-based summary files (state rows) downloaded from www2.census.gov.

The Census API now requires a key in the URL; these bulk files do not.
fetch(table, year) downloads data/acs/<table>_<year>.dat (US + state rows only).
"""
import subprocess
from pathlib import Path
import pandas as pd

DIR = Path(__file__).resolve().parent.parent / "data" / "acs"
FIPS = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE','11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV','55':'WI','56':'WY','72':'PR'}


def fetch(table, year):
    DIR.mkdir(parents=True, exist_ok=True)
    out = DIR / f"{table}_{year}.dat"
    url = (f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/"
           f"data/1YRData/acsdt1y{year}-{table}.dat")
    cmd = f"curl -sSf -m 600 '{url}' | awk -F'|' 'NR==1 || $1 ~ /^0400000US|^0100000US/' > '{out}'"
    subprocess.run(cmd, shell=True, check=True)
    return out


def load_state(table, year):
    p = DIR / f"{table}_{year}.dat"
    if not p.exists():
        fetch(table, year)
    d = pd.read_csv(p, sep="|", dtype=str)
    d["st"] = d.GEO_ID.str[-2:].map(FIPS)
    d.loc[d.GEO_ID == "0100000US", "st"] = "US"
    return d.set_index("st")
