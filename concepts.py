"""
concepts.py — Carga y clasificación de conceptos de impuestos/gastos bancarios.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
import re
from typing import Dict, List

DEFAULT_CONCEPTS_PATH = Path(__file__).with_name("bank_concepts.json")
SUPPORTED_BANKS = ("BBVA", "BNA", "Macro", "Santander")


def normalize_text(value: object) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"\s+", " ", text)
    return text


@lru_cache(maxsize=1)
def load_bank_concepts(path: str | None = None) -> Dict[str, List[str]]:
    config_path = Path(path) if path else DEFAULT_CONCEPTS_PATH
    if not config_path.exists():
        return {bank: [] for bank in SUPPORTED_BANKS}

    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    concepts: Dict[str, List[str]] = {}

    for bank in SUPPORTED_BANKS:
        bank_concepts: List[str] = []
        seen = set()

        for value in raw_config.get(bank, []):
            normalized = normalize_text(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                bank_concepts.append(normalized)

        concepts[bank] = sorted(bank_concepts, key=len, reverse=True)

    return concepts


def is_bank_charge(concepto: object, bank_concepts: List[str]) -> bool:
    normalized = normalize_text(concepto)
    if not normalized:
        return False

    return any(
        normalized == candidate
        or normalized.startswith(candidate)
        or (
            candidate.endswith("%")
            and normalized.startswith(candidate[:-1].strip())
        )
        or candidate in normalized
        for candidate in bank_concepts
    )
