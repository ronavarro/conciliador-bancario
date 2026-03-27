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
            "include_patterns": [
                "comision", "iva", "percepcion", "impuesto", "ley", "interes",
                "sellos", "gasto bancario",
                # desde el Excel:
                "sellado", "int.cob.acue", "reg rec sirc", "gp-comision",
                "gp-com.trans", "gp-cable tra", "gp-gastos ou", "gp-iva tasa",
                "gp-percep.iv", "comi. transf", "cje. interno", "ch/clear.48",
                "oper. fdo.co",
            ],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
        "BNA": {
            "include_patterns": [
                "comision", "iva", "impuesto", "gasto", "cargo", "interes", "sellos",
                # desde el Excel:
                "gravamen ley", "reg.rec.sircreb", "reten. i.v.a.", "debito automatico",
                "reintegro ley", "com transfe electronica", "comis. canje",
                # nuevos patrones detectados en extracto:
                "i.b.reg re",    # Ingresos Brutos Régimen General
                "co.trf.ele",    # Comisión Transferencia Electrónica
                "debitos",       # Débitos varios bancarios
                "ch/recib48",    # Cheque/Recibo 48hs
                "pgo.t/cred",    # Pago tarjeta crédito
                "trf.red",       # Transferencia Red
                "abono interpyme",  # Abono Red Interpyme
                "deb.aut.se",    # Débito automático servicios
                "ch/de inte",    # Cheque de intereses
            ],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
        "Macro": {
            "include_patterns": [
                "comision", "iva", "impuesto", "cargo", "interes", "sellos", "debito",
                # desde el Excel:
                "rrsircreb", "com.serv",
            ],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
        "Santander": {
            "include_patterns": [
                "comision", "iva", "impuesto", "cargo", "interes", "sellos", "gasto bancario",
                # desde el Excel:
                "rrsircreb", "co.trf.ele", "com.v/cob", "iva percep", "a/mant.c.a",
            ],
            "exclude_patterns": ["transferencia", "cheque", "fondo comun", "afip"],
        },
    },
}
