from __future__ import annotations

from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class NeuralMemoryBank(nn.Module):
    """External differentiable memory with usage-based replacement."""

    def __init__(self, memory_size: int = 1000, key_size: int = 256, value_size: int = 64):
        super().__init__()
        self.memory_size = int(memory_size)
        self.key_size = int(key_size)
        self.value_size = int(value_size)

        self.register_buffer("keys", torch.zeros(memory_size, key_size))
        self.register_buffer("values", torch.zeros(memory_size, value_size))
        self.register_buffer("usage", torch.zeros(memory_size))

        self.read_key_net = nn.Linear(key_size, key_size)
        self.write_key_net = nn.Linear(key_size, key_size)
        self.erase_net = nn.Linear(key_size, value_size)
        self.add_net = nn.Linear(key_size, value_size)

    def read(self, query: torch.Tensor, top_k: int = 5) -> Tuple[torch.Tensor, torch.Tensor]:
        # query: (B, key_size)
        if query.dim() == 1:
            query = query.unsqueeze(0)
        read_key = self.read_key_net(query)
        key_bank = self.keys.unsqueeze(0).expand(query.size(0), -1, -1)
        sim = F.cosine_similarity(read_key.unsqueeze(1).expand(-1, self.memory_size, -1), key_bank, dim=-1)
        if 0 < top_k < self.memory_size:
            top_vals, top_idx = torch.topk(sim, k=top_k, dim=-1)
            masked = torch.full_like(sim, fill_value=-1e9)
            masked.scatter_(1, top_idx, top_vals)
            weights = F.softmax(masked, dim=-1)
        else:
            weights = F.softmax(sim * 10.0, dim=-1)
        val_bank = self.values.unsqueeze(0).expand(query.size(0), -1, -1)
        retrieved = torch.bmm(weights.unsqueeze(1), val_bank).squeeze(1)
        return retrieved, weights

    @torch.no_grad()
    def write(self, key: torch.Tensor, value: torch.Tensor) -> None:
        if key.dim() == 1:
            key = key.unsqueeze(0)
        if value.dim() == 1:
            value = value.unsqueeze(0)
        bsz = key.size(0)
        for i in range(bsz):
            idx = int(torch.argmin(self.usage).item())
            wk = self.write_key_net(key[i])
            erase = torch.sigmoid(self.erase_net(wk))
            add = torch.tanh(self.add_net(wk))
            self.keys[idx] = wk
            self.values[idx] = self.values[idx] * (1.0 - erase) + add
            self.usage *= 0.99
            self.usage[idx] = 1.0

    def save(self, path: str = "mecos_memory_bank.pt") -> None:
        torch.save({"keys": self.keys, "values": self.values, "usage": self.usage}, path)

    def load(self, path: str = "mecos_memory_bank.pt") -> None:
        from pathlib import Path

        p = Path(path)
        if not p.exists():
            return
        state = torch.load(str(p), map_location="cpu")
        self.keys.copy_(state["keys"])
        self.values.copy_(state["values"])
        self.usage.copy_(state["usage"])
