"""Canonical serialization and tamper-evident hashes for V2 runs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROTOCOL_CONTRACT = {
    "benchmark": "fixed-topology Perceval catalog heralded CNOT calibration",
    "candidate": "8 additive radians: 6 BS then 2 PS",
    "inputs": ["00", "01", "10", "11"],
    "primary_metric": "q25 of P(correct logical output and herald)",
    "noise": ["static BS offset", "phase error", "mode-specific LC loss"],
    "leakage_rule": "heldout evaluation unavailable before freeze",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def config_hash(config: dict[str, Any]) -> str:
    return sha256_json(config)


def protocol_hash(config: dict[str, Any]) -> str:
    return sha256_json({"contract": PROTOCOL_CONTRACT, "config": config})
