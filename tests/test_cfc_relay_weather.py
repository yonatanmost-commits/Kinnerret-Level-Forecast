"""Bug: the relay (methods A, A1, G) dropped rain intensity from the weather it swaps
for climatology on EVERY table. On the IMS table intensity is a model input, so under
"clim" the relay read the real future intensity (look-ahead)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Automation"))
import cfc_tournament as ct  # noqa: E402

INTENSITY = "precip_intensity_mm_hr"


def test_ims_relay_swaps_intensity_for_climatology():
    assert INTENSITY in ct.relay_met("ims")


def test_era5_relay_has_no_intensity():
    assert INTENSITY not in ct.relay_met("era5")
