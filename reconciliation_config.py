"""Configuración base para reglas extendidas de conciliación."""

from __future__ import annotations

DEFAULT_RECONCILIATION_CONFIG = {
    "amount_tolerance": 0.02,
    # Conceptos del mayor que, cuando tienen valor en Debe, deben ignorarse por completo
    # (no se concilian ni aparecen en "Mayor sin banco").
    "mayor_debe_ignore_patterns": [
        "acreditacion de cheques propios",
    ],
    "consolidated_amount_tolerance": 1.0,
    "transfer_date_tolerance_days": 3,
    "end_of_month_tolerance_days": 5,
    "transfer_include_patterns": ["transfer", "trf", "cte a cte", "interbank"],
    "fund_patterns": ["fondo comun", "money market", "fci", "resc", "suscrip"],
    "cheque_patterns": ["cheque", "chq"],
    "bank_rules": {
        "BBVA": {
            "include_patterns": [
                "comision", "iva", "percepcion", "impuesto", "ley", "interes",
                "sellos", "gasto bancario",
                # desde el Excel:
                "sellado", "int.cob.acue", "reg rec sirc", "gp-comision",
                "gp-com.trans", "gp-cable tra", "gp-gastos ou", "gp-iva tasa",
                "gp-percep.iv", "comi. transf",
                # desde gastos_bancarios.csv:
                "impuesto ley", "com.transf comision", "iva tasa gra", "comision tra",
                "gp-comision cumpl impo", "percepcion i", "comision ext efectivo",
                "gp-comision altseg despacho", "iva tasa red", "ley nro 25.4",
                "comision ges", "com.transfer comision", "comision man", "comision mov",
            ],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip", "ch/clear"],
            "special_patterns": [
                # Movimientos entre cuentas / fondos comunes de inversión — revisión manual
                "cje. interno",
                "oper. fdo.co",
            ],
        },
        "BNA": {
            "include_patterns": [
                "comision", "iva", "impuesto", "gasto", "cargo", "interes", "sellos",
                # desde el Excel:
                "gravamen ley", "reg.rec.sircreb", "reten. i.v.a.", "debito automatico",
                "reintegro ley", "com transfe electronica", "comis. canje",
                # detectados en extracto:
                "i.b.reg re", "co.trf.ele", "ch/recib48",
                "trf.red", "deb.aut.se", "ch/de inte",
                # desde gastos_bancarios.csv:
                "gravamen ley 25413 s/deb", "gravamen ley 25413 s/cred",
                "comision paquetes", "i.v.a. base", "reten. i.v.a. rg.2408",
                "comision deb. transf. ibk", "comis. canje o/bancos",
                "reintegro ley 25413/deb", "comis. gasto chequera",
                "com.ch clearing o aplic.a",
            ],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip", "pgo.t/cred"],
            "amount_threshold_patterns": [
                # "debitos" ≤ 1500 → gasto bancario; > 1500 → conciliar normalmente
                {"pattern": "debitos", "max_amount": 1500},
            ],
            "special_patterns": [
                # Movimientos entre cuentas / operaciones especiales — revisión manual
                "abono interpyme",
            ],
        },
        "Macro": {
            "include_patterns": [
                "comision", "iva", "impuesto", "cargo", "interes", "sellos", "debito",
                # desde el Excel:
                "rrsircreb", "com.serv",
                # desde gastos_bancarios.csv:
                "impuesto al debito", "impuesto al credito", "iva 21%",
            ],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
        "Santander": {
            "include_patterns": [
                "comision", "iva", "impuesto", "cargo", "interes", "sellos", "gasto bancario",
                # desde el Excel:
                "rrsircreb", "co.trf.ele", "com.v/cob", "iva percep", "a/mant.c.a",
                # desde gastos_bancarios.csv:
                "impuesto al debito", "impuesto al credito", "impuestos",
            ],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
    },
}
