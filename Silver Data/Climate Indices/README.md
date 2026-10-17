# Climate indices (monthly)

`climate_indices_monthly.csv`: tidy long format, columns `date` (month start), `index`, `value`.
Covers 1990-01 to the latest month each source has. Retrieved 2026-10-16.

| index | meaning | source | coverage |
|---|---|---|---|
| `ONI` | Oceanic Niño Index, °C anomaly (3-month running mean) | NOAA CPC, https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt | 1990-01 to 2026-08 |
| `NINO34_ANOM` | Niño-3.4 SST anomaly, °C (monthly, OISST) | NOAA CPC, https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices | 1990-01 to 2026-09 |
| `NAO` | North Atlantic Oscillation, standardized (1981-2010 clim) | NOAA CPC, https://ftp.cpc.ncep.noaa.gov/wd52dg/data/indices/tele_index.nh | 1990-01 to 2026-09 |
| `EA` | East Atlantic pattern, standardized | same CPC table | 1990-01 to 2026-09 |
| `EA_WR` | East Atlantic / West Russia pattern, standardized | same CPC table | 1990-01 to 2026-09 |
| `WEMOI` | Western Mediterranean Oscillation index (San Fernando − Padua pressure) | CRU-hosted copy of the Univ. Barcelona series, https://crudata.uea.ac.uk/cru/data/moi/Web_WeMOi-2020.txt | 1990-01 to 2020-12 |

Notes:
- **ONI dating:** each 3-month season is stored at its centre month (DJF of year Y → Y-01, NDJ of Y → Y-12). So the ONI value in a month already uses the following month's SST. Lag it before using it as a predictor.
- **CPC teleconnections:** the table marks a pattern −99.9 when it is not a leading mode that month. Those become empty values; none fall in 1990+ for NAO, EA or EA/WR.
- **WeMOi:** the University of Barcelona page (http://www.ub.edu/gc/wemo/) returned HTTP 500 on 2026-10-16, so the series stops at 2020. Reference: Martin-Vide & Lopez-Bustins (2006), Int. J. Climatol.
- No accounts were used. All sources are public.
