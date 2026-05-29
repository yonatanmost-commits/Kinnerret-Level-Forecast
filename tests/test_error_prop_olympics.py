# tests/test_error_prop_olympics.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))

from model_lib import S2_DIRECT_FEATURES, S2_DIRECT_NO_INFLOW_FEATURES


def test_no_inflow_features_excludes_predicted_inflow():
    assert "predicted_inflow_m3" not in S2_DIRECT_NO_INFLOW_FEATURES


def test_no_inflow_features_is_subset_of_direct_features():
    assert set(S2_DIRECT_NO_INFLOW_FEATURES) < set(S2_DIRECT_FEATURES)


def test_no_inflow_features_length():
    assert len(S2_DIRECT_NO_INFLOW_FEATURES) == len(S2_DIRECT_FEATURES) - 1
