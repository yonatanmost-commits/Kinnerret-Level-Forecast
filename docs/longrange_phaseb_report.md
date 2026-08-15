# Long-Range Forecast - Phase B Bake-off (temperature-only, with ablation)

**Question:** does adding a temperature block to a season + antecedent-state
model improve a 14-30 day forecast of cumulative Kinneret volume change,
and does either beat a day-of-year climatology baseline?

**Protocol:** walk-forward by held-out year (2021-2024); fresh forecast every
7 days; target = cumulative volume change V(t+h)-V(t) [Mm3]; SS = 1 - MSE_a/MSE_b. Future temperature is OBSERVED - a **perfect-prognosis
upper bound** (the live product can only do worse).

Four predictors: **clim** (day-of-year harmonic of cumulative change), **base** (GBR on season + level + antecedent 30-day rain), **temp** (base +
cloud_index, DTR, Tmax anomaly, Hargreaves ET0 over the horizon), and **tempbucket** (temp + the soil-moisture bucket's antecedent saturation state S and trailing-30d overflow Q - 'Architecture J done right'). The two decisive numbers: **SS_temp_marginal_vs_base** (what temperature adds) and **SS_bucket_marginal_vs_temp** (what the saturation-state bucket adds ON TOP of the flat rainfall_30d sum that Architecture J could not beat).

## Headline (leads 14-30 d, pooled)

| Season | n | SS base vs clim | SS temp vs clim | **SS temp marginal (vs base)** | **SS bucket marginal (vs temp)** |
|---|---|---|---|---|---|
| Wet (Nov-Mar) | 247 | -0.093 | +0.121 | **+0.196** | **+0.260** |
| Dry (Apr-Oct) | 360 | -0.571 | -1.228 | **-0.418** | **+0.279** |

**'Architecture J done right' verdict (wet-season 14-30d): bucket marginal = +0.260** (S_max=150mm, untuned v0). Positive => the saturation-state bucket beats the flat 30-day sum and J is healed; <=0 => an honest second negative.

## Per-lead

| Lead | Season | n | RMSE clim | RMSE base | RMSE temp | RMSE tempbucket | SS base | SS temp | SS temp marginal | SS bucket marginal |
|---|---|---|---|---|---|---|---|---|---|---|
| 7 | wet | 81 | 12.107 | 18.025 | 15.207 | 12.117 | -1.217 | -0.578 | +0.288 | +0.365 |
| 14 | wet | 82 | 21.402 | 24.1 | 20.957 | 18.471 | -0.268 | +0.041 | +0.244 | +0.223 |
| 21 | wet | 82 | 29.962 | 32.533 | 29.431 | 24.369 | -0.179 | +0.035 | +0.182 | +0.314 |
| 30 | wet | 83 | 40.615 | 40.583 | 36.58 | 31.96 | +0.002 | +0.189 | +0.188 | +0.237 |
| 7 | dry | 119 | 3.183 | 5.423 | 5.864 | 5.962 | -1.904 | -2.394 | -0.169 | -0.034 |
| 14 | dry | 119 | 5.904 | 7.267 | 8.652 | 7.629 | -0.515 | -1.147 | -0.417 | +0.223 |
| 21 | dry | 119 | 8.816 | 11.226 | 13.197 | 10.776 | -0.621 | -1.241 | -0.382 | +0.333 |
| 30 | dry | 122 | 12.376 | 15.451 | 18.522 | 15.886 | -0.559 | -1.240 | -0.437 | +0.264 |