"""08_national_comparison.py

All-US tornado intensity comparison for the merged manuscript's Table 3,
computed from the original project's SPC one-tornado tidy file with the
same definitions as the original pipeline step 06 (rating_stats). The
method reproduces the submitted paper's national rows exactly for the
study era (26,059 rated of 26,080; 21 unrated) and for the old
2016-2025 extension (11,659 rated; 1,525 unrated); it is run here for
the new extension era 2016-2023. Deterministic; no randomness.
"""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
RESULTS = HERE / "results"
SRC = Path.home() / "workspace/moore-pitch/angle2-tc-tornadoes/data/spc_tornadoes_tidy.parquet"

df = pd.read_parquet(SRC)
rows = []
for label, y0, y1 in [("study_1995_2015", 1995, 2015),
                      ("extension_2016_2023", 2016, 2023),
                      ("extension_2016_2025_check", 2016, 2025)]:
    s = df[(df["yr"] >= y0) & (df["yr"] <= y1)]
    m = s["rating"]
    counts = [int((m == i).sum()) for i in range(6)]
    rated = sum(counts)
    weak, strong, ef2 = counts[0] + counts[1], counts[2] + counts[3], sum(counts[2:])
    rows.append(dict(era=label, total=len(s), n_rated=rated, n_unknown=int(m.isna().sum()),
                     rating_0=counts[0], rating_1=counts[1], rating_2=counts[2],
                     rating_3=counts[3], rating_4=counts[4], rating_5=counts[5],
                     weak_pct=round(100 * weak / rated, 1), strong_pct=round(100 * strong / rated, 1),
                     ef2plus_pct=round(100 * ef2 / rated, 1),
                     deaths=int(s["fat"].sum()), injuries=int(s["inj"].sum())))
out = pd.DataFrame(rows)
out.to_csv(RESULTS / "national_intensity.csv", index=False)
print(out.to_string(index=False))
