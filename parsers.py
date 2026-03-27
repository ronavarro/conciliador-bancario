"""
parsers.py — Un parser por banco, todos normalizan al mismo esquema:
    Fecha | Concepto | Comprobante | Credito | Debito | Importe
"""

from __future__ import annotations
import pandas as pd
import numpy as np


# ──────────────────────────────────────────────
# Schema canónico de salida
# ──────────────────────────────────────────────
SCHEMA = ["Fecha", "Concepto", "Comprobante", "Credito", "Debito", "Importe"]


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Garantiza columnas canónicas y tipos correctos."""
    for col in SCHEMA:
        if col not in df.columns:
            df[col] = np.nan
    df = df[SCHEMA].copy()
    df["Fecha"]       = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    df["Concepto"]    = df["Concepto"].astype(str).str.strip()
    df["Comprobante"] = df["Comprobante"].astype(str).str.strip().replace("nan", "")
    df["Credito"]     = pd.to_numeric(df["Credito"], errors="coerce").fillna(0)
    df["Debito"]      = pd.to_numeric(df["Debito"],  errors="coerce").fillna(0)
    df["Importe"]     = df["Credito"] + df["Debito"]
    df = df[df["Fecha"].notna()].reset_index(drop=True)
    return df


# ──────────────────────────────────────────────
# BBVA
# Archivo: .xls/.xlsx  |  Hoja: "Movimientos Históricos"
# Header en fila 6, datos desde fila 7
# Columnas separadas Crédito / Débito
# ──────────────────────────────────────────────
def parse_bbva(file) -> pd.DataFrame:
    raw = pd.read_excel(file, sheet_name="Movimientos Históricos", header=None)
    df  = raw.iloc[7:].copy()
    df.columns = [
        "Fecha", "Fecha_Valor", "Concepto", "Codigo",
        "Comprobante", "Oficina", "Credito", "Debito", "Detalle", "Extra"
    ]
    df["Debito"]  = pd.to_numeric(df["Debito"],  errors="coerce").fillna(0)
    df["Credito"] = pd.to_numeric(df["Credito"], errors="coerce").fillna(0)
    # BBVA exporta débitos como valores positivos; el motor espera negativos
    df["Debito"] = -df["Debito"].abs()
    return _clean_df(df)


# ──────────────────────────────────────────────
# BNA / MACRO / SANTANDER
# Archivo: .xlsx  |  Hoja: "principal"
# Header en fila 12, datos desde fila 14 (fila 13 = saldo inicial)
# Una sola columna Importe con signo +/-
# ──────────────────────────────────────────────
def _parse_generic_erp(file) -> pd.DataFrame:
    raw = pd.read_excel(file, sheet_name="principal", header=None)
    df  = raw.iloc[14:].copy()
    df.columns = [
        "Concepto", "Fecha", "Comprobante", "Sucursal",
        "Importe", "Descripcion", "CodOp", "CUIT", "Denominacion", "Saldo"
    ]
    df["Importe"] = pd.to_numeric(df["Importe"], errors="coerce")
    df = df[df["Importe"].notna()].copy()

    # Último renglón es "Saldo Final:" — lo descartamos
    df = df[df["Concepto"].astype(str).str.strip() != "nan"].copy()

    df["Credito"] = df["Importe"].apply(lambda x: x if x > 0 else 0)
    df["Debito"]  = df["Importe"].apply(lambda x: x if x < 0 else 0)
    return _clean_df(df)


def parse_bna(file)       -> pd.DataFrame: return _parse_generic_erp(file)
def parse_macro(file)     -> pd.DataFrame: return _parse_generic_erp(file)
def parse_santander(file) -> pd.DataFrame: return _parse_generic_erp(file)


# ──────────────────────────────────────────────
# Mayor de Cuentas (ERP)  — mismo formato siempre
# Header en fila 5, datos desde fila 7
# Columnas Debe / Haber separadas
# ──────────────────────────────────────────────
def parse_mayor(file) -> pd.DataFrame:
    raw = pd.read_excel(file, header=None)
    df  = raw.iloc[7:].copy()
    df.columns = [
        "Fecha", "Asiento", "Nro_Cuenta", "Descripcion",
        "C5", "C6", "C7", "C8", "Debe", "Haber", "Saldo", "Extra"
    ]
    df = df[df["Fecha"] != "Fecha"].copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
    df["Debe"]  = pd.to_numeric(df["Debe"],  errors="coerce").fillna(0)
    df["Haber"] = pd.to_numeric(df["Haber"], errors="coerce").fillna(0)
    df = df[df["Fecha"].notna()].copy()
    df = df[~df["Descripcion"].astype(str).str.contains("Saldo Inicial", na=False)].copy()
    df["Descripcion"] = df["Descripcion"].astype(str).str.strip()
    df["Asiento"]     = df["Asiento"].astype(str).str.strip()
    return df.reset_index(drop=True)


def parse_supplier_table(file) -> pd.DataFrame:
    """Tabla opcional de proveedores para enriquecer matching de transferencias."""
    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in ["cuit", "company_name", "alias"]:
        if col not in df.columns:
            df[col] = ""
    df = df[["cuit", "company_name", "alias"]].copy()
    df["cuit"] = df["cuit"].astype(str).str.replace(r"\D", "", regex=True)
    df["company_name"] = df["company_name"].astype(str).str.strip()
    df["alias"] = df["alias"].astype(str).str.strip()
    return df[df[["cuit", "company_name", "alias"]].any(axis=1)].reset_index(drop=True)


def parse_cheques_aux(file) -> pd.DataFrame:
    """Archivo auxiliar de cheques emitidos (opcional)."""
    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in ["cheque_number", "issue_date", "amount", "bank", "supplier", "status"]:
        if col not in df.columns:
            df[col] = ""
    df = df[["cheque_number", "issue_date", "amount", "bank", "supplier", "status"]].copy()
    df["cheque_number"] = df["cheque_number"].astype(str).str.replace(r"\D", "", regex=True)
    df["issue_date"] = pd.to_datetime(df["issue_date"], dayfirst=True, errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["bank"] = df["bank"].astype(str).str.strip()
    df["supplier"] = df["supplier"].astype(str).str.strip()
    df["status"] = df["status"].astype(str).str.strip()
    return df[df["cheque_number"] != ""].reset_index(drop=True)


# ──────────────────────────────────────────────
# Auto-detección del banco por contenido del archivo
# ──────────────────────────────────────────────
BANK_PARSERS = {
    "BBVA":      parse_bbva,
    "BNA":       parse_bna,
    "Macro":     parse_macro,
    "Santander": parse_santander,
}

def detect_bank(file) -> str | None:
    """
    Detecta el banco leyendo las primeras filas del archivo.

    Firmas por banco (número de cuenta en fila 5, columna 1):
      BBVA       → hoja "Movimientos Históricos"
      BNA        → "33.500" en nro. de cuenta
      Macro      → "3-321" en nro. de cuenta
      Santander  → "334-0" en nro. de cuenta
    """
    try:
        xl = pd.ExcelFile(file)

        # BBVA tiene hoja propia
        if "Movimientos Históricos" in xl.sheet_names:
            return "BBVA"

        # BNA / Macro / Santander — hoja "principal"
        if "principal" not in xl.sheet_names:
            return None

        raw = pd.read_excel(file, sheet_name="principal", header=None, nrows=12)

        # Texto completo de todas las celdas no-nulas
        all_text = " ".join(
            str(v) for v in raw.values.flatten() if str(v) != "nan"
        )

        # Número de cuenta es el discriminador más confiable
        if "33.500" in all_text:          return "BNA"
        if "3-321"  in all_text:          return "Macro"
        if "334-0"  in all_text:          return "Santander"

        # Fallback por nombre si algún día cambia el nro. de cuenta
        if "NACION" in all_text.upper():  return "BNA"
        if "MACRO"  in all_text.upper():  return "Macro"
        if "SANTANDER" in all_text.upper(): return "Santander"

    except Exception:
        pass
    return None
