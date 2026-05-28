# kinneret_app/ims_forecast.py
import requests
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

IMS_URL = (
    "https://ims.gov.il/sites/default/files/ims_data/xml_files/"
    "isr_cities_1week_6hr_forecast.xml"
)
TIBERIAS_ID = 40


@st.cache_data(ttl=3600)
def _fetch_xml_root() -> ET.Element:
    resp = requests.get(IMS_URL, timeout=30)
    resp.raise_for_status()
    return ET.fromstring(resp.content)


def _find_tiberias(root: ET.Element) -> ET.Element:
    for loc in root.findall("Location"):
        if loc.findtext("LocationMetaData/LocationId") == str(TIBERIAS_ID):
            return loc
    raise ValueError(
        f"Tiberias (LocationId={TIBERIAS_ID}) not found in IMS forecast XML"
    )


def _aggregate_to_daily(location_elem: ET.Element, fc_dates: list) -> pd.DataFrame:
    rows = []
    for fc in location_elem.findall("LocationData/Forecast"):
        dt_date = pd.Timestamp(fc.findtext("ForecastTime")).date()
        rows.append({
            "date":             dt_date,
            "MaxTemp":          int(fc.findtext("MaxTemp")),
            "MinTemp":          int(fc.findtext("MinTemp")),
            "Rain":             float(fc.findtext("Rain")),
            "RelativeHumidity": int(fc.findtext("RelativeHumidity")),
            "WindSpeed":        int(fc.findtext("WindSpeed")),
        })

    agg = (
        pd.DataFrame(rows)
        .groupby("date")
        .agg(
            MaxTemp=("MaxTemp", "max"),
            MinTemp=("MinTemp", "min"),
            Rain=("Rain", "sum"),
            RelativeHumidity=("RelativeHumidity", "mean"),
            WindSpeed=("WindSpeed", "mean"),
        )
        .to_dict("index")
    ) if rows else {}

    out = []
    for d in fc_dates:
        key = pd.Timestamp(d).date()
        r = agg.get(key, {})
        out.append({
            "date":           pd.Timestamp(d),
            "temp_max_C":     r.get("MaxTemp",          float("nan")),
            "temp_min_C":     r.get("MinTemp",          float("nan")),
            "rainfall_mm":    r.get("Rain",             float("nan")),
            "humidity_pct":   r.get("RelativeHumidity", float("nan")),
            "wind_speed_ms":  r.get("WindSpeed",        float("nan")) / 3.6,
            "radiation_MJm2": float("nan"),
        })
    return pd.DataFrame(out)


def fetch_tiberias_7day(fc_dates: list) -> pd.DataFrame:
    root = _fetch_xml_root()
    location = _find_tiberias(root)
    return _aggregate_to_daily(location, fc_dates)
