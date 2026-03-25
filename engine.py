"""
engine.py — Motor de conciliación bancaria.

Lógica: para cada movimiento del banco (identificado por fecha + importe),
busca una contrapartida en el Mayor de Cuentas.
  - Crédito banco  ↔  Debe en mayor
  - Débito banco   ↔  Haber en mayor
Tolerancia de diferencia: $0.02 (redondeos)
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from concepts import is_bank_charge


@dataclass
class ReconciliationResult:
    banco_total:              int   = 0
    banco_creditos:           int   = 0
    banco_debitos:            int   = 0
    mayor_total:              int   = 0
    conciliados:              int   = 0
    conciliados_creditos:     int   = 0
    conciliados_debitos:      int   = 0

    # Banco → faltantes en sistema
    faltantes_creditos:  pd.DataFrame = field(default_factory=pd.DataFrame)
    faltantes_debitos:   pd.DataFrame = field(default_factory=pd.DataFrame)

    # Mayor → sin contrapartida en banco
    mayor_sin_banco_debe:  pd.DataFrame = field(default_factory=pd.DataFrame)
    mayor_sin_banco_haber: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Banco completo con estado
    banco_completo: pd.DataFrame = field(default_factory=pd.DataFrame)
    gastos_impuestos_resumen: pd.DataFrame = field(default_factory=pd.DataFrame)
    gastos_impuestos_detalle: pd.DataFrame = field(default_factory=pd.DataFrame)
    conciliados_agrupados: int = 0

    @property
    def total_faltantes(self):
        return len(self.faltantes_creditos) + len(self.faltantes_debitos)

    @property
    def total_pendientes_agrupados(self):
        if self.gastos_impuestos_resumen.empty:
            return 0
        return int((self.gastos_impuestos_resumen["Estado"] == "⚠ Pendiente en mayor").sum())

    @property
    def monto_faltantes_creditos(self):
        return self.faltantes_creditos["Credito"].sum() if not self.faltantes_creditos.empty else 0

    @property
    def monto_faltantes_debitos(self):
        return self.faltantes_debitos["Debito"].sum() if not self.faltantes_debitos.empty else 0

    @property
    def pct_conciliado(self):
        return (self.conciliados / self.banco_total * 100) if self.banco_total else 0


def reconcile(bank_df: pd.DataFrame, mayor_df: pd.DataFrame, bank_concepts: list[str] | None = None) -> ReconciliationResult:
    """
    Parámetros
    ----------
    bank_df  : output de cualquier parser de banco (schema canónico)
    mayor_df : output de parse_mayor()
    """
    TOL = 0.02

    bank_df = bank_df.copy()
    bank_df["_is_charge"] = bank_df["Concepto"].apply(lambda value: is_bank_charge(value, bank_concepts or []))

    # Filtrar período del banco en el mayor
    if not bank_df.empty:
        date_min = bank_df["Fecha"].min().to_period("M").to_timestamp(how="start").normalize()
        date_max = bank_df["Fecha"].max().to_period("M").to_timestamp(how="end").normalize()
        mayor_df = mayor_df[
            (mayor_df["Fecha"] >= date_min) &
            (mayor_df["Fecha"] <= date_max)
        ].copy()

    # Pools separados: Debe (ingresos al banco) y Haber (egresos del banco)
    pool_debe  = mayor_df[mayor_df["Debe"]  > 0][["Fecha", "Descripcion", "Debe",  "Asiento"]].copy().reset_index(drop=True)
    pool_haber = mayor_df[mayor_df["Haber"] > 0][["Fecha", "Descripcion", "Haber", "Asiento"]].copy().reset_index(drop=True)
    pool_debe["_used"]  = False
    pool_haber["_used"] = False

    bank_direct = bank_df[~bank_df["_is_charge"]].copy()
    bank_grouped = bank_df[bank_df["_is_charge"]].copy()

    bank_cred = bank_direct[bank_direct["Credito"] > 0].copy()
    bank_deb  = bank_direct[bank_direct["Debito"]  < 0].copy()
    bank_deb["_abs"] = bank_deb["Debito"].abs()

    matched_cred, unmatched_cred = [], []
    for _, row in bank_cred.iterrows():
        mask = (
            (pool_debe["Fecha"] == row["Fecha"]) &
            (abs(pool_debe["Debe"] - row["Credito"]) < TOL) &
            (~pool_debe["_used"])
        )
        hits = pool_debe[mask]
        if len(hits) > 0:
            pool_debe.loc[hits.index[0], "_used"] = True
            matched_cred.append(row)
        else:
            unmatched_cred.append(row)

    matched_deb, unmatched_deb = [], []
    for _, row in bank_deb.iterrows():
        mask = (
            (pool_haber["Fecha"] == row["Fecha"]) &
            (abs(pool_haber["Haber"] - row["_abs"]) < TOL) &
            (~pool_haber["_used"])
        )
        hits = pool_haber[mask]
        if len(hits) > 0:
            pool_haber.loc[hits.index[0], "_used"] = True
            matched_deb.append(row)
        else:
            unmatched_deb.append(row)

    grouped_matches = []
    grouped_pending = []
    grouped_status_map = {}
    grouped_detail = bank_grouped.copy()

    if not grouped_detail.empty:
        grouped_detail["Periodo"] = grouped_detail["Fecha"].dt.to_period("M").astype(str)
        grouped_detail["Tipo"] = np.where(grouped_detail["Credito"] > 0, "Credito", "Debito")
        grouped_detail["MontoGrupo"] = np.where(
            grouped_detail["Credito"] > 0,
            grouped_detail["Credito"],
            grouped_detail["Debito"].abs(),
        )

        grouped_summary = (
            grouped_detail.groupby(["Periodo", "Tipo"], dropna=False)
            .agg(
                Cantidad=("Concepto", "size"),
                Monto=("MontoGrupo", "sum"),
            )
            .reset_index()
        )

        for _, summary in grouped_summary.iterrows():
            period = pd.Period(summary["Periodo"], freq="M")
            month_end = period.to_timestamp(how="end").normalize()
            candidate_dates = {month_end, month_end - pd.Timedelta(days=1)}
            target_amount = float(summary["Monto"])

            if summary["Tipo"] == "Credito":
                pool = pool_debe
                amount_col = "Debe"
            else:
                pool = pool_haber
                amount_col = "Haber"

            mask = (
                pool["Fecha"].isin(candidate_dates) &
                (abs(pool[amount_col] - target_amount) < TOL) &
                (~pool["_used"])
            )
            hits = pool[mask]

            detail_mask = (
                (grouped_detail["Periodo"] == summary["Periodo"]) &
                (grouped_detail["Tipo"] == summary["Tipo"])
            )

            if len(hits) > 0:
                hit = hits.iloc[0]
                pool.loc[hit.name, "_used"] = True
                grouped_matches.append({
                    "Periodo": summary["Periodo"],
                    "Tipo": summary["Tipo"],
                    "Cantidad": int(summary["Cantidad"]),
                    "Monto": target_amount,
                    "FechaMayor": hit["Fecha"].strftime("%d/%m/%Y"),
                    "Asiento": hit["Asiento"],
                    "DescripcionMayor": hit["Descripcion"],
                    "Estado": "✓ Conciliado agrupado",
                })
                grouped_status_map[(summary["Periodo"], summary["Tipo"])] = "✓ Conciliado agrupado mensual"
            else:
                grouped_pending.append({
                    "Periodo": summary["Periodo"],
                    "Tipo": summary["Tipo"],
                    "Cantidad": int(summary["Cantidad"]),
                    "Monto": target_amount,
                    "FechaMayor": "",
                    "Asiento": "",
                    "DescripcionMayor": "",
                    "Estado": "⚠ Pendiente en mayor",
                })
                grouped_status_map[(summary["Periodo"], summary["Tipo"])] = "⚠ Agrupado mensual pendiente"
    else:
        grouped_summary = pd.DataFrame(columns=["Periodo", "Tipo", "Cantidad", "Monto"])

    # Construir DataFrames de resultado
    def _to_df(lst, cols):
        if not lst:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(lst)[cols].copy()
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%d/%m/%Y")
        return df.sort_values("Fecha").reset_index(drop=True)

    fc_cols = ["Fecha", "Concepto", "Comprobante", "Credito"]
    fd_cols = ["Fecha", "Concepto", "Comprobante", "Debito"]

    faltantes_cred = _to_df(unmatched_cred, fc_cols)
    faltantes_deb  = _to_df(unmatched_deb,  fd_cols)

    mayor_sb_debe  = pool_debe[~pool_debe["_used"]][["Fecha","Descripcion","Asiento","Debe"]].copy()
    mayor_sb_haber = pool_haber[~pool_haber["_used"]][["Fecha","Descripcion","Asiento","Haber"]].copy()
    for df in [mayor_sb_debe, mayor_sb_haber]:
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%d/%m/%Y")

    # Banco completo con estado
    unc_cred_keys = set(
        (r["Fecha"], r["Concepto"], round(r["Credito"], 2))
        for r in unmatched_cred
    )
    unc_deb_keys = set(
        (r["Fecha"], r["Concepto"], round(r["Debito"], 2))
        for r in unmatched_deb
    )

    banco_completo = bank_df.copy()
    if not grouped_detail.empty:
        banco_completo["Periodo"] = banco_completo["Fecha"].dt.to_period("M").astype(str)
        banco_completo["TipoMovimiento"] = np.where(banco_completo["Credito"] > 0, "Credito", "Debito")

    banco_completo["Estado"] = banco_completo.apply(
        lambda r: grouped_status_map.get((r.get("Periodo"), r.get("TipoMovimiento")))
        if r.get("_is_charge")
        else (
            "⚠ No en sistema"
            if (r["Fecha"], r["Concepto"], round(r["Credito"], 2)) in unc_cred_keys
            or (r["Fecha"], r["Concepto"], round(r["Debito"], 2)) in unc_deb_keys
            else "✓ Conciliado"
        ),
        axis=1,
    )
    banco_completo["Clasificacion"] = np.where(
        banco_completo["_is_charge"],
        "Impuestos/Gastos bancarios",
        "Conciliacion directa",
    )
    banco_completo["Fecha"] = banco_completo["Fecha"].dt.strftime("%d/%m/%Y")
    banco_completo = banco_completo.drop(columns=["_is_charge"], errors="ignore")
    banco_completo = banco_completo.drop(columns=["Periodo", "TipoMovimiento"], errors="ignore")

    grouped_detail_out = pd.DataFrame(columns=["Fecha", "Periodo", "Concepto", "Comprobante", "Credito", "Debito"])
    if not grouped_detail.empty:
        grouped_detail_out = grouped_detail[["Fecha", "Periodo", "Concepto", "Comprobante", "Credito", "Debito"]].copy()
        grouped_detail_out["Fecha"] = grouped_detail_out["Fecha"].dt.strftime("%d/%m/%Y")
        grouped_detail_out = grouped_detail_out.sort_values(["Periodo", "Fecha", "Concepto"]).reset_index(drop=True)

    grouped_result = pd.DataFrame(grouped_matches + grouped_pending)
    if not grouped_result.empty:
        grouped_result = grouped_result.sort_values(["Periodo", "Tipo"]).reset_index(drop=True)

    return ReconciliationResult(
        banco_total             = len(bank_df),
        banco_creditos          = len(bank_cred),
        banco_debitos           = len(bank_deb),
        mayor_total             = len(mayor_df),
        conciliados             = len(matched_cred) + len(matched_deb),
        conciliados_creditos    = len(matched_cred),
        conciliados_debitos     = len(matched_deb),
        faltantes_creditos      = faltantes_cred,
        faltantes_debitos       = faltantes_deb,
        mayor_sin_banco_debe    = mayor_sb_debe.reset_index(drop=True),
        mayor_sin_banco_haber   = mayor_sb_haber.reset_index(drop=True),
        banco_completo          = banco_completo,
        gastos_impuestos_resumen = grouped_result,
        gastos_impuestos_detalle = grouped_detail_out,
        conciliados_agrupados   = len(grouped_matches),
    )
