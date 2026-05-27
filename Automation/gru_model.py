"""
gru_model.py  -  PyTorch GRU multi-task model for Kinneret forecasting.

Predicts Jordan River inflow (m³/day) and lake volume change (Mm³/day)
jointly from a 21-day sequence window + per-horizon scalar.

Kept separate from model_lib.py so PyTorch is not imported on every
dashboard page load.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

SEQUENCE_LEN = 21

GRU_SEQ_FEATURES = [
    "temp_mean_C", "temp_max_C", "temp_min_C",
    "rainfall_mm", "humidity_pct", "wind_speed_ms", "et0_mm", "rainfall_7d_mm",
    "level_m", "volume_change_Mm3", "inflow_obstacle_m3",
    "season_sin", "season_cos", "daylength_hrs",
]
N_SEQ_FEATURES = len(GRU_SEQ_FEATURES)   # 14


# ─────────────────────────────────────────────────────────────────────────────
# Neural network
# ─────────────────────────────────────────────────────────────────────────────

class KinneretGRU(nn.Module):
    """
    GRU backbone with two output heads.

    Forward args
    ------------
    seq      : FloatTensor [batch, 21, 14]  — daily feature sequence
    horizon  : FloatTensor [batch, 1]       — forecast horizon (1-7)

    Returns
    -------
    inflow_pred : FloatTensor [batch]  (raw, denormalize externally)
    dvol_pred   : FloatTensor [batch]
    """

    def __init__(self, input_size: int = N_SEQ_FEATURES,
                 hidden_size: int = 64, dropout: float = 0.2):
        super().__init__()
        # num_layers=1: PyTorch dropout only fires between layers,
        # so we apply it in the dense block instead.
        self.gru = nn.GRU(input_size, hidden_size,
                          num_layers=1, batch_first=True)
        self.shared = nn.Sequential(
            nn.Linear(hidden_size + 1, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
        )
        self.inflow_head = nn.Linear(32, 1)
        self.dvol_head   = nn.Linear(32, 1)

    def forward(self, seq: torch.Tensor,
                horizon: torch.Tensor):
        _, h_n      = self.gru(seq)          # h_n: [1, B, H]
        h           = h_n.squeeze(0)         # [B, H]
        x           = torch.cat([h, horizon], dim=1)   # [B, H+1]
        shared      = self.shared(x)         # [B, 32]
        inflow_pred = self.inflow_head(shared).squeeze(1)
        dvol_pred   = self.dvol_head(shared).squeeze(1)
        return inflow_pred, dvol_pred


# ─────────────────────────────────────────────────────────────────────────────
# Sequence builder
# ─────────────────────────────────────────────────────────────────────────────

def build_gru_sequences(df: pd.DataFrame, horizon: int):
    """
    Build fixed-length (SEQUENCE_LEN) input sequences for one forecast horizon.

    For each anchor row t where targets at t+horizon are valid:
      - sequence   = df[GRU_SEQ_FEATURES] rows [t-20 : t+1], zero-padded if needed
      - horizon_h  = [[float(horizon)]]
      - inflow_tgt = inflow_obstacle_m3 at t+horizon
      - dvol_tgt   = volume_change_Mm3  at t+horizon
      - anchor_idx = integer row index t in df

    Returns five arrays (all float32):
      sequences     [N, 21, 14]
      horizons      [N, 1]
      inflow_tgts   [N]
      dvol_tgts     [N]
      anchor_indices [N]  — int64 row indices into df
    """
    df   = df.reset_index(drop=True)
    n    = len(df)
    feat = np.nan_to_num(
        df[GRU_SEQ_FEATURES].values.astype(np.float32), nan=0.0
    )
    inflow_col = df["inflow_obstacle_m3"].values.astype(np.float32)
    dvol_col   = df["volume_change_Mm3"].values.astype(np.float32)

    sequences, horizons_out, inflow_tgts, dvol_tgts, anc_idx = [], [], [], [], []

    for t in range(n - horizon):
        ti = float(inflow_col[t + horizon])
        td = float(dvol_col[t + horizon])
        if np.isnan(ti) or np.isnan(td):
            continue

        start = t - SEQUENCE_LEN + 1
        if start >= 0:
            seq = feat[start: t + 1].copy()
        else:
            pad = np.zeros((-start, N_SEQ_FEATURES), dtype=np.float32)
            seq = np.vstack([pad, feat[: t + 1]])

        sequences.append(seq)
        horizons_out.append([float(horizon)])
        inflow_tgts.append(ti)
        dvol_tgts.append(td)
        anc_idx.append(t)

    return (
        np.array(sequences,    dtype=np.float32),
        np.array(horizons_out, dtype=np.float32),
        np.array(inflow_tgts,  dtype=np.float32),
        np.array(dvol_tgts,    dtype=np.float32),
        np.array(anc_idx,      dtype=np.int64),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Trainer  (fit / predict_horizon / save / load)
# ─────────────────────────────────────────────────────────────────────────────

class GRUTrainer:
    """
    Wraps KinneretGRU with a sklearn-style fit/predict API.
    Handles z-score normalisation of both targets internally.
    """

    def __init__(self, epochs: int = 150, lr: float = 1e-3,
                 batch_size: int = 64):
        self.epochs     = epochs
        self.lr         = lr
        self.batch_size = batch_size
        self.device     = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: KinneretGRU | None = None
        self.inflow_mean = self.inflow_std = None
        self.dvol_mean   = self.dvol_std   = None

    # ------------------------------------------------------------------
    def fit(self, df: pd.DataFrame) -> "GRUTrainer":
        """Train on df (builds sequences for all horizons 1-7 internally)."""
        all_seqs, all_h, all_inf, all_dv = [], [], [], []
        for h in range(1, 8):
            s, hs, inf, dv, _ = build_gru_sequences(df, h)
            all_seqs.append(s);  all_h.append(hs)
            all_inf.append(inf); all_dv.append(dv)

        seqs    = np.concatenate(all_seqs)
        hs      = np.concatenate(all_h)
        inflows = np.concatenate(all_inf)
        dvols   = np.concatenate(all_dv)

        self.inflow_mean = float(np.nanmean(inflows))
        self.inflow_std  = max(float(np.nanstd(inflows)), 1e-8)
        self.dvol_mean   = float(np.nanmean(dvols))
        self.dvol_std    = max(float(np.nanstd(dvols)), 1e-8)

        inf_n = (inflows - self.inflow_mean) / self.inflow_std
        dv_n  = (dvols   - self.dvol_mean)   / self.dvol_std

        dev    = self.device
        X_seq  = torch.tensor(seqs,  device=dev)
        X_h    = torch.tensor(hs,    device=dev)
        y_inf  = torch.tensor(inf_n, device=dev)
        y_dv   = torch.tensor(dv_n,  device=dev)

        self.model = KinneretGRU().to(dev)
        opt = torch.optim.Adam(self.model.parameters(), lr=self.lr)

        n = len(seqs)
        for epoch in range(self.epochs):
            self.model.train()
            perm       = torch.randperm(n, device=dev)
            epoch_loss = 0.0
            n_batches  = 0
            for start in range(0, n, self.batch_size):
                idx = perm[start: start + self.batch_size]
                opt.zero_grad()
                p_inf, p_dv = self.model(X_seq[idx], X_h[idx])
                loss = (F.mse_loss(p_inf, y_inf[idx]) +
                        F.mse_loss(p_dv,  y_dv[idx]))
                loss.backward()
                opt.step()
                epoch_loss += loss.item()
                n_batches  += 1
            if (epoch + 1) % 30 == 0:
                print(f"    GRU epoch {epoch+1}/{self.epochs}  "
                      f"loss={epoch_loss / n_batches:.4f}", flush=True)
        return self

    # ------------------------------------------------------------------
    def predict_horizon(self, full_df: pd.DataFrame,
                        horizon: int, test_year: int | None = None):
        """
        Predict inflow and dvol for one horizon.

        full_df   : gold DataFrame (may span multiple years; sequences use
                    history across the train-test boundary — correct behaviour)
        horizon   : 1-7
        test_year : if given, return only rows where anchor is in that year

        Returns (inflow_pred, dvol_pred, anchor_dates, dvol_actuals) — all
        aligned arrays (float32 / datetime64).
        """
        seqs, hs, inf_tgts, dv_tgts, anc_idx = build_gru_sequences(full_df, horizon)
        if len(seqs) == 0:
            empty = np.array([], dtype=np.float32)
            return empty, empty, np.array([]), empty

        if test_year is not None:
            mask    = full_df.iloc[anc_idx]["date"].dt.year.values == test_year
            seqs    = seqs[mask];    hs       = hs[mask]
            inf_tgts = inf_tgts[mask]; dv_tgts = dv_tgts[mask]
            anc_idx  = anc_idx[mask]

        self.model.eval()
        dev = self.device
        with torch.no_grad():
            p_inf, p_dv = self.model(
                torch.tensor(seqs, device=dev),
                torch.tensor(hs,   device=dev),
            )
        p_inf = p_inf.cpu().numpy() * self.inflow_std + self.inflow_mean
        p_dv  = p_dv.cpu().numpy()  * self.dvol_std   + self.dvol_mean
        p_inf = np.clip(p_inf, 0, None)

        anchor_dates = full_df.iloc[anc_idx]["date"].values
        return p_inf, p_dv, anchor_dates, dv_tgts

    # ------------------------------------------------------------------
    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "model_state": self.model.state_dict(),
            "inflow_mean": self.inflow_mean, "inflow_std": self.inflow_std,
            "dvol_mean":   self.dvol_mean,   "dvol_std":   self.dvol_std,
            "epochs": self.epochs, "lr": self.lr,
        }, path)

    @classmethod
    def load(cls, path: str | Path) -> "GRUTrainer":
        ckpt    = torch.load(path, map_location="cpu", weights_only=False)
        trainer = cls(epochs=ckpt["epochs"], lr=ckpt["lr"])
        trainer.model = KinneretGRU()
        trainer.model.load_state_dict(ckpt["model_state"])
        trainer.model.eval()
        trainer.inflow_mean = ckpt["inflow_mean"]
        trainer.inflow_std  = ckpt["inflow_std"]
        trainer.dvol_mean   = ckpt["dvol_mean"]
        trainer.dvol_std    = ckpt["dvol_std"]
        return trainer
