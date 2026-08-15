Here's a complete breakdown of all the APIs and endpoints I found for the **לב כנרת (Lev Kineret) station — Station ID: 115**:

---

## Station Details

| Field | Value |
|---|---|
| Station ID | **115** |
| Name | **לב כנרת** (Lev Kineret) |
| Coordinates | Lat: 32.816, Lon: 35.599 |
| Active since | 2003-11-26 |
| Data resolution | T-10 (10-minute intervals) |

**Available channels (monitors):**
Rain (1), WSmax (2), WDmax (3), WS (4), WD (5), STDwd (6), TD-temperature (7), RH (8), TDmax (9), TDmin (10), WS1mm (12), Ws10mm (13), Time (14)

---

## API Endpoints

### 1. ✅ Real-time / Latest Measurement (BEST OPTION)

```
GET https://ims.gov.il/he/envista_station_data/115
```
or in English:
```
GET https://ims.gov.il/en/envista_station_data/115
```

**No authentication required.** Returns the latest 10-minute reading for all channels.

**Sample response (as of 2026-05-28T07:10:00+03:00):**
```json
{
  "data": {
    "stationId": 115,
    "data": [{
      "datetime": "2026-05-28T07:10:00+03:00",
      "channels": [
        {"id": 2, "name": "WSmax", "value": 4.9, "valid": true},
        {"id": 4, "name": "WS",    "value": 2.8, "valid": true},
        {"id": 5, "name": "WD",    "value": 144, "valid": true},
        {"id": 7, "name": "TD",    "value": 24,  "valid": true},
        {"id": 8, "name": "RH",    "value": 72,  "valid": true},
        ...
      ]
    }]
  }
}
```

---

### 2. ✅ Historical Archive Data (via IMS → data.gov.il)

```
GET https://ims.gov.il/he/archive_data/T-10/{stationId}/{channelId}/{fromDateHour}/{toDateHour}/{byType}/
```

**Example** – temperature (channel 7) for station 115, from 2026-05-27 00:00 to 2026-05-28 10:00:
```
GET https://ims.gov.il/he/archive_data/T-10/115/7/2026052700/2026052810/1/
```

This returns a JSON with a `basic_url` field pointing to the **data.gov.il CKAN API** — which the page then uses to fetch the actual tabular data. The `basic_url` template looks like:
```
http://eapi.data.gov.il/api/action/datastore_search?resource_id=&limit=150000
  &fields=stn_num,time_obs,7
  &filters={"year":["2026"],"month":["05"],"day":["27","28"],"stn_num":["115"]}
  &sort=time_obs, stn_num
```
> Note: the `resource_id=` is empty in this endpoint — the site JS fills it in from the `archive_station_info` endpoint.

---

### 3. ✅ Station List / Metadata

```
GET https://ims.gov.il/he/envista_station_info/
```
Returns all active Envista stations with their channel IDs, coordinates, and open/close dates.

---

### 4. Time-Range Endpoint (for 10-minute data, partially working)

The site JS constructs a URL like:
```
GET https://ims.gov.il/he/envista_station_data_time_range/{stationId}/{channelId}/{fromDateHour}00/{toDateHour}{toMin}/{byType}/{clock}/{tempUnit}/{windUnit}/{radUnit}
```
Example:
```
/he/envista_station_data_time_range/115/7/2026052700/2026052810/1/3/C/M/W
```
**⚠️ This currently returns 404** — the Drupal routing on ims.gov.il truncates URLs with more than 6 path segments, stripping the units/clock parameters. The real-time endpoint (`envista_station_data/115`) is the reliable alternative for current data.

---

## Quick Python Scrape Example

```python
import requests

# Get latest measurement from לב כנרת
url = "https://ims.gov.il/en/envista_station_data/115"
response = requests.get(url)
data = response.json()

latest = data["data"]["data"][0]
print(f"Time: {latest['datetime']}")
for ch in latest["channels"]:
    if ch["valid"]:
        print(f"  {ch['name']}: {ch['value']}")
```

---

**Summary:** The most reliable option is **`/en/envista_station_data/115`** for current data (no auth required, returns clean JSON). For historical data, use the **`/archive_data/T-10/...`** endpoint to get the data.gov.il query URL, then call that API separately.