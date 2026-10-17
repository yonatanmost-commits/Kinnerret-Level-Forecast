"""
cfc_compare.py  -  score the three contenders on one bench: CfC (B14), GRU (B14gru), GBR (G).

Reads one or more result folders written by cfc_tournament.py, keeps the forecasts every
compared (model, weather) pair has in common, and prints per-horizon errors plus paired
bootstrap 90% intervals (resampled test years) against the CfC.

    python Automation/cfc_compare.py docs/experiments/cfc_ims_ext
    python Automation/cfc_compare.py docs/experiments/cfc_seas5 --weather clim,seas5,obs
    python Automation/cfc_compare.py <folder> --suffix h        # the --no-humidity runs

Negative "vs CfC" = better than the CfC.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfc_tournament_report as r  # noqa: E402

SHORT = [7, 13, 26]


def compare(folders, weathers=("clim", "obs"), suffix="", years=None) -> str:
    d = pd.concat([r.load(Path(f)) for f in folders])
    d = d[~d["weather"].str.contains(r"\|")]
    if years:
        d = d[d["year"].between(*years)]
    models = {"CfC": f"B14{suffix}", "GRU": f"B14gru{suffix}", "GBR": f"G{suffix}"}
    have = set(d["method"])
    models = {k: v for k, v in models.items() if v in have}
    keys = [f"{m}/{w}" for w in weathers for m in models.values()]
    keys = [k for k in keys if k in set(d["key"])]
    refs = [f"{x}/-" for x in r.REFS if f"{x}/-" in set(d["key"])]
    c = r.common(d, keys + refs)
    hs = sorted(set(c["H"]))
    long = [h for h in r.LONG if h in hs]
    lines = [f"{c['year'].nunique()} test years ({c['year'].min()}-{c['year'].max()}), "
             f"{c.groupby('start').ngroups} starts, models: {', '.join(f'{k}={v}' for k, v in models.items())}",
             "", f"{'model/weather':22s}" + "".join(f"{h:>8d}" for h in hs) + f"{'7-26':>8s}{'130-365':>9s}"]
    for k in keys + refs:
        row = [r.mae(c, k, [h]) for h in hs]
        lines.append(f"{k:22s}" + "".join(f"{v:8.3f}" for v in row)
                     + f"{r.mae(c, k, SHORT):8.3f}{r.mae(c, k, long):9.3f}")
    lines += ["", "vs CfC, same weather: difference [90% interval over test years]"]
    cfc = models.get("CfC")
    for w in weathers:
        for name, m in models.items():
            if name == "CfC" or f"{m}/{w}" not in keys or f"{cfc}/{w}" not in keys:
                continue
            s = r.boot(c, f"{m}/{w}", f"{cfc}/{w}", SHORT)
            l = r.boot(c, f"{m}/{w}", f"{cfc}/{w}", long)
            lines.append(f"  {name:4s} {w:6s} 7-26 d {s[0]:+.3f} [{s[1]:+.3f}, {s[2]:+.3f}]   "
                         f"130-365 d {l[0]:+.3f} [{l[1]:+.3f}, {l[2]:+.3f}]")
    if "clim" in weathers:
        for w in weathers:
            if w in ("clim", "obs"):
                continue
            lines.append(f"\n{w} vs average weather, same model:")
            for name, m in models.items():
                if f"{m}/{w}" in keys and f"{m}/clim" in keys:
                    s = r.boot(c, f"{m}/{w}", f"{m}/clim", SHORT)
                    l = r.boot(c, f"{m}/{w}", f"{m}/clim", long)
                    lines.append(f"  {name:4s} 7-26 d {s[0]:+.3f} [{s[1]:+.3f}, {s[2]:+.3f}]   "
                                 f"130-365 d {l[0]:+.3f} [{l[1]:+.3f}, {l[2]:+.3f}]")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--weather", default="clim,obs")
    ap.add_argument("--suffix", default="", help="label suffix, e.g. h for --no-humidity runs")
    ap.add_argument("--years", default="", help="first,last test year")
    a = ap.parse_args()
    yrs = tuple(int(y) for y in a.years.split(",")) if a.years else None
    print(compare(a.folders, tuple(a.weather.split(",")), a.suffix, yrs))
