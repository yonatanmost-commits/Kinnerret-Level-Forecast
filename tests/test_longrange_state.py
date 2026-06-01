# tests/test_longrange_state.py
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


def test_api_decays_without_rain():
    """With no rain, API decays geometrically by factor k each day."""
    from longrange_state import antecedent_precip_index
    P = np.array([100.0, 0.0, 0.0, 0.0])
    A = antecedent_precip_index(P, k=0.9, a0=0.0)
    assert abs(A[0] - 100.0) < 1e-9
    assert abs(A[1] - 90.0) < 1e-9
    assert abs(A[2] - 81.0) < 1e-9


def test_bucket_dry_soil_produces_no_runoff():
    """The J-fix, half 1: dry soil soaks rain (low runoff) -> fixes 2023-style
    drought over-prediction."""
    from longrange_state import soil_moisture_bucket
    P = np.array([20.0])
    ET = np.array([2.0])
    S, Q = soil_moisture_bucket(P, ET, S_max=200.0, S0=0.0)
    assert Q[0] == 0.0           # all absorbed, nothing overflows
    assert abs(S[0] - 18.0) < 1e-9


def test_bucket_saturated_soil_spills_to_runoff():
    """The J-fix, half 2: saturated soil spills rain straight to runoff -> fixes
    2021-style wet under-prediction. Same rain, opposite outcome vs dry soil."""
    from longrange_state import soil_moisture_bucket
    P = np.array([20.0])
    ET = np.array([2.0])
    S, Q = soil_moisture_bucket(P, ET, S_max=200.0, S0=200.0)
    assert abs(Q[0] - 18.0) < 1e-9     # 200 + 20 - 2 - 200 = 18 overflow
    assert abs(S[0] - 200.0) < 1e-9    # stays capped at S_max


def test_bucket_never_below_zero():
    """ET on an empty bucket can't drive storage negative."""
    from longrange_state import soil_moisture_bucket
    P = np.array([0.0, 0.0])
    ET = np.array([10.0, 10.0])
    S, Q = soil_moisture_bucket(P, ET, S_max=200.0, S0=5.0)
    assert (S >= 0).all()
    assert (Q == 0).all()
