"""
engine.py — Motor de conciliación bancaria.

Lógica base: para cada movimiento del banco (identificado por fecha + importe),
busca una contrapartida en el Mayor de Cuentas.
  - Crédito banco  ↔  Debe en mayor
  - Débito banco   ↔  Haber en mayor

Sobre esta base se agregan pases incrementales configurables para casos especiales:
  1) Cargos/impuestos bancarios consolidados
  2) Transferencias con tolerancia de fecha y agrupación
  3) Cheques de períodos previos (archivo auxiliar)
  4) Enriquecimiento opcional por CUIT/proveedor
  5) Detección de movimientos de fondos comunes
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field

import pandas as pd

from reconciliation_config import DEFAULT_RECONCILIATION_CONFIG


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

    # Trazabilidad
    decision_log: list[str] = field(default_factory=list)

    @property
    def total_faltantes(self):
        return len(self.faltantes_creditos) + len(self.faltantes_debitos)

    @property
    def monto_faltantes_creditos(self):
        return self.faltantes_creditos["Credito"].sum() if not self.faltantes_creditos.empty else 0

    @property
    def monto_faltantes_debitos(self):
        return self.faltantes_debitos["Debito"].sum() if not self.faltantes_debitos.empty else 0

    @property
    def pct_conciliado(self):
        return (self.conciliados / self.banco_total * 100) if self.banco_total else 0


def _norm_text(value: str) -> str:
    return str(value or "").strip().lower()


def _extract_cuit(text: str) -> str:
    found = re.findall(r"\b\d{11}\b", str(text or ""))
    return found[0] if found else ""


def _extract_cheque_number(text: str) -> str:
    m = re.search(r"(?:cheque|chq)\D*(\d{4,10})", str(text or ""), re.IGNORECASE)
    return m.group(1) if m else ""


def _is_transfer(text: str, transfer_patterns: list[str]) -> bool:
    tx = _norm_text(text)
    return any(pat in tx for pat in transfer_patterns)


def _is_fund_movement(text: str, fund_patterns: list[str]) -> bool:
    tx = _norm_text(text)
    return any(pat in tx for pat in fund_patterns)


def _bank_charge_candidate(text: str, include: list[str], exclude: list[str], fund_patterns: list[str]) -> bool:
    tx = _norm_text(text)
    if any(pat in tx for pat in exclude):
        return False
    if any(pat in tx for pat in fund_patterns):
        return False
    return any(pat in tx for pat in include)


def _build_df_from_indexes(bank_df: pd.DataFrame, idxs: list[int]) -> pd.DataFrame:
    cols = ["Fecha", "Concepto", "Comprobante", "Credito", "Debito"]
    if not idxs:
        return pd.DataFrame(columns=cols)
    out = bank_df.loc[idxs, cols].copy()
    out["Fecha"] = pd.to_datetime(out["Fecha"]).dt.strftime("%d/%m/%Y")
    return out.sort_values("Fecha").reset_index(drop=True)


def reconcile(
    bank_df: pd.DataFrame,
    mayor_df: pd.DataFrame,
    banco: str | None = None,
    config: dict | None = None,
    supplier_df: pd.DataFrame | None = None,
    cheques_df: pd.DataFrame | None = None,
) -> ReconciliationResult:
    cfg = {**DEFAULT_RECONCILIATION_CONFIG, **(config or {})}
    tol = float(cfg["amount_tolerance"])

    bank_df = bank_df.copy()
    mayor_df = mayor_df.copy()
    bank_df["_idx"] = bank_df.index
    bank_df["_matched"] = False
    bank_df["_match_type"] = ""
    bank_df["_match_reason"] = ""

    decision_log: list[str] = []

    # Filtrar período del banco en el mayor (lógica existente)
    if not bank_df.empty:
        date_min = bank_df["Fecha"].min()
        date_max = bank_df["Fecha"].max()
        mayor_df = mayor_df[(mayor_df["Fecha"] >= date_min) & (mayor_df["Fecha"] <= date_max)].copy()

    # Pools separados: Debe (ingresos al banco) y Haber (egresos del banco)
    pool_debe = mayor_df[mayor_df["Debe"] > 0][["Fecha", "Descripcion", "Debe", "Asiento"]].copy().reset_index(drop=True)
    pool_haber = mayor_df[mayor_df["Haber"] > 0][["Fecha", "Descripcion", "Haber", "Asiento"]].copy().reset_index(drop=True)
    pool_debe["_used"] = False
    pool_haber["_used"] = False

    bank_cred = bank_df[bank_df["Credito"] > 0].copy()
    bank_deb = bank_df[bank_df["Debito"] < 0].copy()
    bank_deb["_abs"] = bank_deb["Debito"].abs()

    # MATCH PASS 1: Lógica original exacta fecha+importe
    matched_cred_idx, unmatched_cred_idx = [], []
    for _, row in bank_cred.iterrows():
        mask = (
            (pool_debe["Fecha"] == row["Fecha"])
            & (abs(pool_debe["Debe"] - row["Credito"]) < tol)
            & (~pool_debe["_used"])
        )
        hits = pool_debe[mask]
        if len(hits) > 0:
            hidx = hits.index[0]
            pool_debe.loc[hidx, "_used"] = True
            matched_cred_idx.append(int(row["_idx"]))
            bank_df.loc[row["_idx"], ["_matched", "_match_type", "_match_reason"]] = [
                True,
                "exact_match",
                "Matched by original exact rule (date+amount, crédito↔debe)",
            ]
        else:
            unmatched_cred_idx.append(int(row["_idx"]))

    matched_deb_idx, unmatched_deb_idx = [], []
    for _, row in bank_deb.iterrows():
        mask = (
            (pool_haber["Fecha"] == row["Fecha"])
            & (abs(pool_haber["Haber"] - row["_abs"]) < tol)
            & (~pool_haber["_used"])
        )
        hits = pool_haber[mask]
        if len(hits) > 0:
            hidx = hits.index[0]
            pool_haber.loc[hidx, "_used"] = True
            matched_deb_idx.append(int(row["_idx"]))
            bank_df.loc[row["_idx"], ["_matched", "_match_type", "_match_reason"]] = [
                True,
                "exact_match",
                "Matched by original exact rule (date+amount, débito↔haber)",
            ]
        else:
            unmatched_deb_idx.append(int(row["_idx"]))

    # PASS 2: Cargos bancarios consolidados
    bank_name = banco or ""
    rules = cfg.get("bank_rules", {}).get(bank_name, {})
    include_patterns = rules.get("include_patterns", [])
    exclude_patterns = rules.get("exclude_patterns", [])
    fund_patterns = cfg.get("fund_patterns", [])
    eom_tol = int(cfg.get("end_of_month_tolerance_days", 5))
    cons_tol = float(cfg.get("consolidated_amount_tolerance", 1.0))

    debit_unmatched_df = bank_df.loc[unmatched_deb_idx].copy()
    charge_candidates = debit_unmatched_df[
        debit_unmatched_df["Concepto"].apply(
            lambda x: _bank_charge_candidate(x, include_patterns, exclude_patterns, fund_patterns)
        )
    ].copy()

    if not charge_candidates.empty:
        charge_candidates["_month"] = charge_candidates["Fecha"].dt.to_period("M")
        for month, grp in charge_candidates.groupby("_month"):
            grp_idxs = grp["_idx"].tolist()
            total_abs = float(grp["Debito"].abs().sum())
            m_end = month.to_timestamp("M")
            candidates = pool_haber[
                (~pool_haber["_used"])
                & (pool_haber["Fecha"].dt.to_period("M") == month)
                & ((pool_haber["Fecha"] - m_end).abs().dt.days <= eom_tol)
                & (abs(pool_haber["Haber"] - total_abs) <= cons_tol)
            ]

            if len(candidates) == 1:
                idx = candidates.index[0]
                pool_haber.loc[idx, "_used"] = True
                for bidx in grp_idxs:
                    bank_df.loc[bidx, ["_matched", "_match_type", "_match_reason"]] = [
                        True,
                        "reconciled_consolidated_bank_charges",
                        f"Matched as consolidated bank charges for {month} against single ledger entry",
                    ]
                    if bidx in unmatched_deb_idx:
                        unmatched_deb_idx.remove(bidx)
                decision_log.append(f"Matched as consolidated bank charges ({month}, {len(grp_idxs)} movimientos).")
            elif len(candidates) > 1:
                for bidx in grp_idxs:
                    bank_df.loc[bidx, ["_match_type", "_match_reason"]] = [
                        "multiple_possible_candidates",
                        f"Multiple possible consolidated ledger candidates for {month}",
                    ]
            else:
                near = pool_haber[
                    (~pool_haber["_used"])
                    & (pool_haber["Fecha"].dt.to_period("M") == month)
                    & ((pool_haber["Fecha"] - m_end).abs().dt.days <= eom_tol)
                    & (abs(pool_haber["Haber"] - total_abs) <= cons_tol * 5)
                ]
                status = "ledger_entry_found_amount_difference" if len(near) > 0 else "ledger_entry_not_found"
                for bidx in grp_idxs:
                    bank_df.loc[bidx, ["_match_type", "_match_reason"]] = [
                        status,
                        f"Consolidated charge candidate: {status} for {month}",
                    ]

    # PASS 3: Transferencias con tolerancia fecha + agrupación
    transfer_patterns = cfg.get("transfer_include_patterns", [])
    transfer_tol_days = int(cfg.get("transfer_date_tolerance_days", 3))

    transfer_unmatched = bank_df.loc[unmatched_deb_idx + unmatched_cred_idx].copy()
    transfer_unmatched = transfer_unmatched[
        transfer_unmatched["Concepto"].apply(lambda x: _is_transfer(x, transfer_patterns))
    ]

    for _, row in transfer_unmatched.iterrows():
        bidx = int(row["_idx"])
        if bank_df.loc[bidx, "_matched"]:
            continue

        amount = row["Credito"] if row["Credito"] > 0 else abs(row["Debito"])
        is_credit = row["Credito"] > 0
        pool = pool_debe if is_credit else pool_haber
        amount_col = "Debe" if is_credit else "Haber"

        exact = pool[(~pool["_used"]) & (abs(pool[amount_col] - amount) < tol) & (pool["Fecha"] == row["Fecha"])]
        if len(exact) > 0:
            idx = exact.index[0]
            pool.loc[idx, "_used"] = True
            bank_df.loc[bidx, ["_matched", "_match_type", "_match_reason"]] = [
                True,
                "exact_match",
                "Transfer matched by exact amount/date",
            ]
            if bidx in unmatched_cred_idx:
                unmatched_cred_idx.remove(bidx)
            if bidx in unmatched_deb_idx:
                unmatched_deb_idx.remove(bidx)
            continue

        tol_hits = pool[
            (~pool["_used"])
            & (abs(pool[amount_col] - amount) < tol)
            & ((pool["Fecha"] - row["Fecha"]).abs().dt.days <= transfer_tol_days)
        ]
        if len(tol_hits) == 1:
            idx = tol_hits.index[0]
            pool.loc[idx, "_used"] = True
            delta = int((pool.loc[idx, "Fecha"] - row["Fecha"]).days)
            bank_df.loc[bidx, ["_matched", "_match_type", "_match_reason"]] = [
                True,
                "match_with_date_tolerance",
                f"Matched transfer with {delta:+d} day tolerance",
            ]
            decision_log.append(f"Matched transfer with {delta:+d} day tolerance.")
            if bidx in unmatched_cred_idx:
                unmatched_cred_idx.remove(bidx)
            if bidx in unmatched_deb_idx:
                unmatched_deb_idx.remove(bidx)
            continue

        # Agrupación: movimientos del mismo día/concepto que sumen un asiento
        same_side_unmatched = bank_df.loc[
            [i for i in (unmatched_cred_idx if is_credit else unmatched_deb_idx) if i != bidx]
        ].copy()
        if not same_side_unmatched.empty:
            same_side_unmatched = same_side_unmatched[
                same_side_unmatched["Concepto"].apply(lambda x: _is_transfer(x, transfer_patterns))
            ]
            group_candidates = same_side_unmatched[same_side_unmatched["Fecha"] == row["Fecha"]]
            if not group_candidates.empty:
                row_amount_col = "Credito" if is_credit else "Debito"
                group_amount = amount + float(group_candidates[row_amount_col].abs().sum())
                grp_hits = pool[(~pool["_used"]) & (abs(pool[amount_col] - group_amount) <= tol)]
                if len(grp_hits) == 1:
                    idx = grp_hits.index[0]
                    pool.loc[idx, "_used"] = True
                    group_idxs = [bidx] + group_candidates["_idx"].astype(int).tolist()
                    for gidx in group_idxs:
                        bank_df.loc[gidx, ["_matched", "_match_type", "_match_reason"]] = [
                            True,
                            "match_by_grouping",
                            "Matched transfer by grouping multiple bank movements",
                        ]
                        if gidx in unmatched_cred_idx:
                            unmatched_cred_idx.remove(gidx)
                        if gidx in unmatched_deb_idx:
                            unmatched_deb_idx.remove(gidx)
                    decision_log.append("Matched transfer by grouping multiple bank movements.")
                    continue

        bank_df.loc[bidx, ["_match_type", "_match_reason"]] = [
            "possible_match_suggestion",
            "Transfer candidate found but not enough confidence to auto-match",
        ]

    # PASS 4: Cheques de períodos previos (si hay archivo auxiliar)
    cheque_patterns = cfg.get("cheque_patterns", [])
    if cheques_df is not None and not cheques_df.empty:
        for bidx in list(unmatched_deb_idx):
            row = bank_df.loc[bidx]
            tx = _norm_text(row["Concepto"])
            if not any(p in tx for p in cheque_patterns):
                continue
            chq_no = _extract_cheque_number(row["Concepto"])
            if not chq_no:
                continue
            hit = cheques_df[cheques_df["cheque_number"].astype(str) == chq_no]
            if hit.empty:
                continue
            amt = abs(float(row["Debito"]))
            amt_hits = hit[abs(hit["amount"] - amt) <= tol]
            if amt_hits.empty:
                continue

            bank_df.loc[bidx, ["_matched", "_match_type", "_match_reason"]] = [
                True,
                "reconciled_previous_period_cheque",
                "Matched cheque issued in previous period",
            ]
            unmatched_deb_idx.remove(bidx)
            decision_log.append("Matched cheque issued in previous period.")

    # PASS 5: Enriquecimiento opcional por CUIT/proveedor
    if supplier_df is not None and not supplier_df.empty:
        for bidx in unmatched_deb_idx + unmatched_cred_idx:
            row = bank_df.loc[bidx]
            cuit = _extract_cuit(row.get("Concepto", ""))
            if not cuit:
                continue
            sup = supplier_df[supplier_df["cuit"].astype(str) == cuit]
            if sup.empty:
                continue
            names = ", ".join(
                filter(None, (sup.iloc[0].get("company_name", ""), sup.iloc[0].get("alias", "")))
            )
            prev_reason = bank_df.loc[bidx, "_match_reason"]
            add = f"CUIT matched with supplier table: {names or cuit}"
            bank_df.loc[bidx, "_match_reason"] = f"{prev_reason} | {add}" if prev_reason else add

    # PASS 6: Detección fondos comunes — no clasificar como cargos
    for bidx in unmatched_deb_idx + unmatched_cred_idx:
        if bank_df.loc[bidx, "_matched"]:
            continue
        if _is_fund_movement(bank_df.loc[bidx, "Concepto"], fund_patterns):
            bank_df.loc[bidx, ["_match_type", "_match_reason"]] = [
                "possible_missing_ledger_entry_fund_movement",
                "Potential missing ledger entry (fund movement)",
            ]
            decision_log.append("Potential missing ledger entry.")

    # Construcción salida
    faltantes_cred = _build_df_from_indexes(bank_df, unmatched_cred_idx)
    faltantes_deb = _build_df_from_indexes(bank_df, unmatched_deb_idx)

    mayor_sb_debe = pool_debe[~pool_debe["_used"]][["Fecha", "Descripcion", "Asiento", "Debe"]].copy()
    mayor_sb_haber = pool_haber[~pool_haber["_used"]][["Fecha", "Descripcion", "Asiento", "Haber"]].copy()
    for df in [mayor_sb_debe, mayor_sb_haber]:
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%d/%m/%Y")

    banco_completo = bank_df.copy()

    def _estado(r):
        if r["_matched"]:
            return "✓ Conciliado"
        mt = r.get("_match_type", "")
        if mt:
            return f"⚠ {mt}"
        return "⚠ No en sistema"

    banco_completo["Estado"] = banco_completo.apply(_estado, axis=1)
    banco_completo["Traza"] = banco_completo["_match_reason"]
    banco_completo["Fecha"] = banco_completo["Fecha"].dt.strftime("%d/%m/%Y")
    banco_completo = banco_completo.drop(columns=["_idx", "_matched", "_match_type", "_match_reason"], errors="ignore")

    return ReconciliationResult(
        banco_total=len(bank_df),
        banco_creditos=len(bank_cred),
        banco_debitos=len(bank_deb),
        mayor_total=len(mayor_df),
        conciliados=int((banco_completo["Estado"] == "✓ Conciliado").sum()),
        conciliados_creditos=int(((bank_df["Credito"] > 0) & (bank_df["_matched"])).sum()),
        conciliados_debitos=int(((bank_df["Debito"] < 0) & (bank_df["_matched"])).sum()),
        faltantes_creditos=faltantes_cred,
        faltantes_debitos=faltantes_deb,
        mayor_sin_banco_debe=mayor_sb_debe.reset_index(drop=True),
        mayor_sin_banco_haber=mayor_sb_haber.reset_index(drop=True),
        banco_completo=banco_completo,
        decision_log=decision_log,
    )
