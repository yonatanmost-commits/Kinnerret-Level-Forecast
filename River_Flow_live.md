Yes, the flow rate (ספיקה) and water height data from this site can definitely be scraped. Here's a detailed breakdown of how it works:

---

## API Endpoints

The site loads its data from three internal PHP endpoints via POST requests:

**1. Flow/observations data (flow rate + water height time series):**
```
POST https://hydro.water.gov.il/db_requests/get_hydro_observations_A7f3Q.php
```
Returns a JSON array:
- `[0]` — observations dict: `{ "YYYY-MM-DD HH:mm:ss": { station_id: [flow_m3s, water_height_m] } }`
- `[1]` — radar data
- `[2]` — `flow_hours_max` (latest timestamp)

**2. Station metadata:**
```
POST https://hydro.water.gov.il/db_requests/get_hydro_stations_A7f3Q.php
Data: lang=he (or lang=en)
```

**3. Rain observations:**
```
POST https://hydro.water.gov.il/db_requests/get_rain_observations_A7f3Q.php
```

---

## Important Notes

- **Authentication**: The requests require a session token from a `<meta name="api-token">` tag on the page. You'd need to first load the main page to get this token, then include it as `X-SESSION-TOKEN` in the request headers.
- **Data window**: The observations endpoint appears to return the most recent ~48 hours of data at 10-minute intervals.
- **Station IDs**: The dropdown shows ~120 stations. The currently selected station ("ירדן-גשר הפקק") has ID `79`. Flow for this station is currently **8.15 m³/sec**.
- **Data format**: Each observation is keyed by timestamp string and contains `[flow_rate, water_height]`.

---

## Quick Python Approach

```python
import requests
from bs4 import BeautifulSoup

# Step 1: Get API token from page
session = requests.Session()
r = session.get("https://hydro.water.gov.il/index.php/?page=hydro_obs&lang=he")
soup = BeautifulSoup(r.text, "html.parser")
token = soup.find("meta", {"name": "api-token"})["content"]

# Step 2: Fetch observations
headers = {"X-SESSION-TOKEN": token}
obs_r = session.post(
    "https://hydro.water.gov.il/db_requests/get_hydro_observations_A7f3Q.php",
    headers=headers
)
data = obs_r.json()
observations = data[0]  # { timestamp: { station_id: [flow, wh] } }

# Extract flow for station 79 (ירדן-גשר הפקק)
for timestamp, stations in observations.items():
    if "79" in stations:
        flow, water_height = stations["79"]
        print(f"{timestamp}: flow={flow} m³/s, WH={water_height} m")
```

---

## Limitations

- The data appears to cover **~48 hours** at 10-minute resolution (or ~7 days at hourly). There's no obvious public endpoint for historical data beyond that window.
- The site is described as being in a "trial run" phase (האתר בתקופת הרצה), so the API may change.
- Be respectful of their terms of service — the disclaimer notes this is raw, unvalidated data for real-time operational purposes only.