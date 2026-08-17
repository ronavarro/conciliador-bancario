"""Configuración base para reglas extendidas de conciliación."""

from __future__ import annotations

DEFAULT_RECONCILIATION_CONFIG = {
    "amount_tolerance": 0.02,
    # Conceptos del mayor que, cuando tienen valor en Debe, corresponden a la
    # ACREDITACIÓN de un cheque propio (asiento banco/banco). El Haber de ese
    # asiento concilia contra el débito del banco; el Debe queda suelto y NO debe
    # tratarse como faltante ni descartarse: se separa en el bucket "Cheques Debe
    # sin conciliar" para cruzarlo por monto contra el Haber sin conciliar del mes
    # de emisión (el pago al proveedor, que en el mayor aparece como pago normal).
    "cheque_acreditacion_debe_patterns": [
        "acreditacion de cheques propios",
    ],
    # (compat) alias histórico — se sigue leyendo si el nuevo no está presente.
    "mayor_debe_ignore_patterns": [
        "acreditacion de cheques propios",
    ],
    # Renta financiera: retención de IIBB sobre la ganancia del rescate de FCI.
    # Se identifica por la contrapartida en el mayor (el ERP la etiqueta así),
    # no por el concepto del banco (que es ambiguo: RET. IB, RRSIRCREB, etc.).
    "renta_financiera_mayor_patterns": ["ret renta financiera"],
    "renta_financiera_date_tolerance_days": 5,
    "consolidated_amount_tolerance": 1.0,
    "transfer_date_tolerance_days": 3,
    "end_of_month_tolerance_days": 5,
    # Depósito de cheques: concepto banco comienza con este patrón → buscar en mayor con prefijo MB
    "deposit_cheque_bank_pattern": "depos.chq",
    "deposit_cheque_mayor_prefix": "mb",
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
            # "cje. interno" (canje interno) se sacó de special: es un movimiento
            # reconciliable normal contra el mayor. "oper. fdo.co" pasó a fci_patterns.
            "special_patterns": [],
            # Movimientos de FCI: se separan SIEMPRE a "Movimientos Financieros"
            # (matcheen o no), fuera del circuito operativo.
            "fci_patterns": ["oper. fdo.co"],
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
            # No se observaron movimientos de FCI en BNA; se puede completar más adelante.
            "fci_patterns": [],
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
            "fci_patterns": ["fdo.com.in"],
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
            "fci_patterns": ["suscri.fci", "resc.fci"],
        },
    },
}
