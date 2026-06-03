from __future__ import annotations

import math
from typing import Dict, Optional

import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    """Injects sequence position information into transformer inputs."""

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / float(d_model)))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0), persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(x + self.pe[:, : x.size(1)])


class MarketTransformer(nn.Module):
    """
    Cross-signal transformer encoder for market state representation.
    Treats each signal source as a token.
    """

    def __init__(
        self,
        n_signals: int = 32,
        d_model: int = 256,
        n_heads: int = 8,
        n_layers: int = 6,
        d_ff: int = 1024,
        dropout: float = 0.1,
        n_actions: int = 5,
    ):
        super().__init__()
        self.n_signals = int(n_signals)
        self.d_model = int(d_model)
        self.signal_embedding = nn.Linear(1, d_model)
        self.signal_type_embedding = nn.Embedding(n_signals, d_model)
        self.pos_encoding = PositionalEncoding(d_model=d_model, dropout=dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_ff,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)

        self.action_head = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128, n_actions),
        )
        self.uncertainty_head = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )
        self.value_head = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Tanh(),
        )
        self._init_weights()

    def _init_weights(self) -> None:
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(
        self,
        signal_values: torch.Tensor,
        signal_ids: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        val_emb = self.signal_embedding(signal_values)
        type_emb = self.signal_type_embedding(signal_ids)
        x = self.pos_encoding(val_emb + type_emb)
        x = self.transformer(x, src_key_padding_mask=mask)
        cls = x.mean(dim=1)
        return {
            "action_logits": self.action_head(cls),
            "uncertainty": self.uncertainty_head(cls),
            "expected_value": self.value_head(cls),
            "signal_repr": cls,
        }
