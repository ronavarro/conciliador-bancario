"""Configuración base para reglas extendidas de conciliación."""

from __future__ import annotations

DEFAULT_RECONCILIATION_CONFIG = {
    "amount_tolerance": 0.02,
    "consolidated_amount_tolerance": 1.0,
    "transfer_date_tolerance_days": 3,
    "end_of_month_tolerance_days": 5,
    "transfer_include_patterns": ["transfer", "trf", "cte a cte", "interbank"],
    "fund_patterns": ["fondo comun", "money market", "fci", "resc", "suscrip"],
    "cheque_patterns": ["cheque", "chq"],
    "bank_rules": {
        "BBVA": {
            "include_patterns": ["comision", "iva", "percepcion", "impuesto", "ley", "interes", "sellos", "gasto bancario"],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
        "BNA": {
            "include_patterns": ["comision", "iva", "impuesto", "gasto", "cargo", "interes", "sellos"],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
        "Macro": {
            "include_patterns": ["comision", "iva", "impuesto", "cargo", "interes", "sellos", "debito"],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
        "Santander": {
            "include_patterns": ["comision", "iva", "impuesto", "cargo", "interes", "sellos", "gasto bancario"],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
    },
}
