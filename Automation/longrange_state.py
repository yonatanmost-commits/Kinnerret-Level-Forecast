# Automation/longrange_state.py
"""
longrange_state.py - Antecedent catchment-state variables (Group 6).

The soil-moisture bucket is "Architecture J done right": flat 30/45-day rainfall
sums (Arch J) could not encode catchment saturation, so they failed in opposite
directions (2023 drought over-predicted runoff, 2021 wet under-predicted it). The
bucket's S_max cap + overflow term Q ARE that saturation threshold:
  - dry soil (low S)  -> rain refills storage, little Q -> low inflow  (fixes 2023)
  - wet soil (S~S_max) -> rain spills to Q -> high inflow              (fixes 2021)
"""
from __future__ import annotations

import numpy as np


def antecedent_precip_index(rainfall_mm, k=0.90, a0=0.0):
    """API_t = k * API_{t-1} + P_t   (Group 6). Returns array same length as input."""
    P = np.asarray(rainfall_mm, dtype=float)
    A = np.empty(P.shape[0], dtype=float)
    prev = a0
    for i in range(P.shape[0]):
        prev = k * prev + P[i]
        A[i] = prev
    return A


def soil_moisture_bucket(rainfall_mm, et_mm, S_max=200.0, S0=None):
    """Bucket model (Group 6). Returns (S, Q):
      S_t = clip(S_{t-1} + P_t - ET_t, 0, S_max)         storage [mm]
      Q_t = max(0, S_{t-1} + P_t - ET_t - S_max)         overflow/runoff [mm]
    S0 defaults to half capacity if not given (spin-up should override in practice).
    """
    P = np.asarray(rainfall_mm, dtype=float)
    ET = np.asarray(et_mm, dtype=float)
    n = P.shape[0]
    S = np.empty(n, dtype=float)
    Q = np.empty(n, dtype=float)
    s = 0.5 * S_max if S0 is None else float(S0)
    for i in range(n):
        avail = s + P[i] - ET[i]
        q = max(0.0, avail - S_max)
        s = min(max(avail, 0.0), S_max)
        S[i] = s
        Q[i] = q
    return S, Q
