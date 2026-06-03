from __future__ import annotations

from typing import Dict, Tuple

import torch
import torch.nn as nn


class GatedResidualNetwork(nn.Module):
    """TFT gated residual building block."""

    def __init__(self, input_size: int, hidden_size: int, output_size: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size)
        self.gate = nn.Linear(hidden_size, output_size)
        self.norm = nn.LayerNorm(output_size)
        self.dropout = nn.Dropout(dropout)
        self.skip = nn.Linear(input_size, output_size) if input_size != output_size else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.fc1(x))
        h = self.dropout(h)
        out = self.fc2(h)
        gate = torch.sigmoid(self.gate(h))
        return self.norm(gate * out + self.skip(x))


class VariableSelectionNetwork(nn.Module):
    """Learns dynamic feature weights for a set of variables."""

    def __init__(self, n_vars: int, d_model: int, hidden_size: int):
        super().__init__()
        self.n_vars = int(n_vars)
        self.grns = nn.ModuleList([GatedResidualNetwork(d_model, hidden_size, d_model) for _ in range(n_vars)])
        self.softmax = nn.Softmax(dim=-1)
        self.weight_net = nn.Linear(n_vars * d_model, n_vars)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # x: (B, n_vars, d_model)
        processed = torch.stack([grn(x[:, i, :]) for i, grn in enumerate(self.grns)], dim=1)
        flat = x.reshape(x.size(0), -1)
        weights = self.softmax(self.weight_net(flat))
        selected = (processed * weights.unsqueeze(-1)).sum(dim=1)
        return selected, weights


class TemporalFusionTransformer(nn.Module):
    """TFT variant for multi-horizon quantile forecasting."""

    def __init__(
        self,
        n_past_vars: int = 10,
        n_static_vars: int = 5,
        d_model: int = 128,
        hidden_size: int = 256,
        n_heads: int = 4,
        dropout: float = 0.1,
        n_horizons: int = 4,
        n_quantiles: int = 3,
    ):
        super().__init__()
        self.n_past_vars = int(n_past_vars)
        self.n_static_vars = int(n_static_vars)
        self.n_horizons = int(n_horizons)
        self.n_quantiles = int(n_quantiles)
        self.d_model = int(d_model)
        self.hidden_size = int(hidden_size)
        self.lstm_layers = 2

        self.past_proj = nn.Linear(n_past_vars, n_past_vars * d_model)
        self.static_proj = nn.Linear(n_static_vars, n_static_vars * d_model)
        self.past_vsn = VariableSelectionNetwork(n_past_vars, d_model, hidden_size)
        self.static_vsn = VariableSelectionNetwork(n_static_vars, d_model, hidden_size)

        self.lstm = nn.LSTM(
            input_size=d_model,
            hidden_size=hidden_size,
            batch_first=True,
            num_layers=self.lstm_layers,
            dropout=dropout,
            bidirectional=False,
        )
        self.static_context_h = GatedResidualNetwork(d_model, hidden_size, hidden_size)
        self.static_context_c = GatedResidualNetwork(d_model, hidden_size, hidden_size)
        self.attention = nn.MultiheadAttention(hidden_size, n_heads, dropout=dropout, batch_first=True)
        self.attn_gate = GatedResidualNetwork(hidden_size, hidden_size, hidden_size)
        self.ffn = GatedResidualNetwork(hidden_size, hidden_size * 2, hidden_size)
        self.output = nn.Linear(hidden_size, n_horizons * n_quantiles)

    def forward(self, past_x: torch.Tensor, static_x: torch.Tensor) -> Dict[str, torch.Tensor]:
        # past_x: (B, T, V), static_x: (B, S)
        bsz, seq_len, n_vars = past_x.shape
        if n_vars != self.n_past_vars:
            raise ValueError(f"Expected {self.n_past_vars} past vars, got {n_vars}")
        if static_x.shape[1] != self.n_static_vars:
            raise ValueError(f"Expected {self.n_static_vars} static vars, got {static_x.shape[1]}")

        past_emb = self.past_proj(past_x).view(bsz, seq_len, self.n_past_vars, self.d_model)
        static_emb = self.static_proj(static_x).view(bsz, self.n_static_vars, self.d_model)

        _, past_weights = self.past_vsn(past_emb.mean(dim=1))
        static_sel, static_weights = self.static_vsn(static_emb)
        selected_seq = (past_emb * past_weights.unsqueeze(1).unsqueeze(-1)).sum(dim=2)

        h0 = self.static_context_h(static_sel).unsqueeze(0).repeat(self.lstm_layers, 1, 1).contiguous()
        c0 = self.static_context_c(static_sel).unsqueeze(0).repeat(self.lstm_layers, 1, 1).contiguous()
        lstm_out, _ = self.lstm(selected_seq, (h0, c0))

        attn_out, attn_weights = self.attention(lstm_out, lstm_out, lstm_out)
        x = self.attn_gate(lstm_out + attn_out)
        x = self.ffn(x)
        out = self.output(x[:, -1, :])
        return {
            "predictions": out.view(bsz, self.n_horizons, self.n_quantiles),
            "past_importance": past_weights,
            "static_importance": static_weights,
            "attention_weights": attn_weights,
        }
