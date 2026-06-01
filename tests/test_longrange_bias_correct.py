# tests/test_longrange_bias_correct.py
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Automation"))


def test_quantile_map_shifts_distribution_onto_reference():
    """Mapping a biased source onto a reference matches the reference mean closely."""
    from longrange_bias_correct import quantile_map
    rng = np.random.default_rng(0)
    ref = rng.normal(20.0, 2.0, 2000)     # station truth
    src = rng.normal(23.0, 2.0, 2000)     # ERA5, +3 warm bias
    corrected = quantile_map(src, ref)
    assert abs(np.mean(corrected) - np.mean(ref)) < 0.3
    assert abs(np.std(corrected) - np.std(ref)) < 0.3


def test_quantile_map_is_monotonic():
    """Quantile mapping preserves ordering of source values."""
    from longrange_bias_correct import quantile_map
    rng = np.random.default_rng(1)
    ref = rng.normal(0, 1, 500)
    src = np.array([1.0, 2.0, 3.0, 4.0])
    out = quantile_map(src, ref)
    assert np.all(np.diff(out) >= 0)
