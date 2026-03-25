"""
app.py — Conciliador Bancario
Streamlit app — sube extracto + mayor, descargá el Excel conciliado.
"""

import streamlit as st
import pandas as pd
import io
from datetime import datetime

from concepts import DEFAULT_CONCEPTS_PATH, load_bank_concepts
from parsers import BANK_PARSERS, detect_bank, parse_mayor
from engine  import reconcile
from exporter import build_excel


if "uploader_nonce" not in st.session_state:
    st.session_state.uploader_nonce = 0
if "last_reconciliation" not in st.session_state:
    st.session_state.last_reconciliation = None

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Conciliador Bancario",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS personalizado ────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }

  .main { background: #F7F8FC; }

  /* Header hero */
  .hero {
    background: linear-gradient(135deg, #1A2B5F 0%, #0F4C81 60%, #1565C0 100%);
    border-radius: 16px;
    padding: 40px 48px;
    margin-bottom: 32px;
    color: white;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 280px; height: 280px;
    border-radius: 50%;
    background: rgba(255,255,255,0.04);
  }
  .hero::after {
    content: '';
    position: absolute;
    bottom: -80px; left: 40%;
    width: 200px; height: 200px;
    border-radius: 50%;
    background: rgba(255,255,255,0.03);
  }
  .hero h1 { font-size: 2.2rem; font-weight: 600; margin: 0 0 8px 0; letter-spacing: -0.5px; }
  .hero p  { font-size: 1rem; opacity: 0.75; margin: 0; font-weight: 300; }

  /* Upload cards */
  .upload-card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    border: 1.5px dashed #CBD5E1;
    transition: border-color 0.2s;
  }
  .upload-card:hover { border-color: #0F4C81; }
  .upload-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #64748B;
    margin-bottom: 8px;
  }

  /* Stat cards */
  .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .stat-card {
    background: white;
    border-radius: 12px;
    padding: 20px 24px;
    border-left: 4px solid #E2E8F0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .stat-card.ok    { border-left-color: #22C55E; }
  .stat-card.warn  { border-left-color: #F59E0B; }
  .stat-card.error { border-left-color: #EF4444; }
  .stat-card.info  { border-left-color: #3B82F6; }
  .stat-label { font-size: 0.72rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.8px; }
  .stat-value { font-size: 2rem; font-weight: 600; color: #1E293B; line-height: 1.1; margin-top: 4px; }
  .stat-sub   { font-size: 0.82rem; color: #64748B; margin-top: 2px; }

  /* Progress bar */
  .prog-wrap { background: #E2E8F0; border-radius: 99px; height: 8px; margin: 8px 0 4px 0; overflow: hidden; }
  .prog-bar  { height: 100%; border-radius: 99px; background: linear-gradient(90deg, #22C55E, #16A34A); transition: width 0.6s ease; }

  /* Section headers */
  .section-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #94A3B8;
    margin: 28px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #E2E8F0;
  }

  /* Alert banners */
  .alert {
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.9rem;
  }
  .alert-error  { background: #FEF2F2; border: 1px solid #FECACA; color: #991B1B; }
  .alert-warn   { background: #FFFBEB; border: 1px solid #FDE68A; color: #92400E; }
  .alert-ok     { background: #F0FDF4; border: 1px solid #BBF7D0; color: #14532D; }

  /* Bank badge */
  .bank-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: #EFF6FF; color: #1D4ED8;
    border: 1px solid #BFDBFE;
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 0.82rem;
    font-weight: 600;
  }

  /* Streamlit overrides */
  .stButton > button {
    background: linear-gradient(135deg, #1A2B5F, #0F4C81) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 12px 32px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    font-family: 'DM Sans', sans-serif !important;
    transition: opacity 0.2s !important;
    width: 100%;
  }
  .stButton > button:hover { opacity: 0.88 !important; }

  .stDownloadButton > button {
    background: linear-gradient(135deg, #15803D, #16A34A) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-family: 'DM Sans', sans-serif !important;
    width: 100%;
  }

  div[data-testid="stFileUploader"] {
    background: transparent !important;
    border: none !important;
  }

  .stTabs [data-baseweb="tab"] { font-family: 'DM Sans', sans-serif !important; }
  .stDataFrame { border-radius: 10px; overflow: hidden; }

  .footer {
    text-align: center;
    color: #94A3B8;
    font-size: 0.78rem;
    margin-top: 48px;
    padding-top: 20px;
    border-top: 1px solid #E2E8F0;
  }
</style>
""", unsafe_allow_html=True)


# ── Hero header ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🏦 Conciliador Bancario</h1>
  <p>Subí el extracto del banco y el Mayor de Cuentas del ERP — el sistema valida cada movimiento automáticamente.</p>
</div>
""", unsafe_allow_html=True)


# ── Upload section ───────────────────────────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown('<div class="upload-label">📄 Extracto Bancario</div>', unsafe_allow_html=True)
    bank_file = st.file_uploader(
        "Extracto del banco", type=["xls", "xlsx"],
        key=f"bank_{st.session_state.uploader_nonce}", label_visibility="collapsed"
    )
    if bank_file:
        detected = detect_bank(bank_file)
        bank_file.seek(0)
        if detected:
            st.markdown(f'<div class="bank-badge">🏦 Detectado: {detected}</div>', unsafe_allow_html=True)
        else:
            st.warning("No se pudo detectar el banco automáticamente.")

with col2:
    st.markdown('<div class="upload-label">📊 Mayor de Cuentas (ERP)</div>', unsafe_allow_html=True)
    mayor_file = st.file_uploader(
        "Mayor de cuentas", type=["xlsx"],
        key=f"mayor_{st.session_state.uploader_nonce}", label_visibility="collapsed"
    )
    if mayor_file:
        st.markdown('<div class="bank-badge" style="background:#F0FDF4;color:#15803D;border-color:#BBF7D0;">✓ Archivo cargado</div>', unsafe_allow_html=True)

# Selector manual de banco (por si la detección falla)
banco_manual = None
if bank_file and not detect_bank(bank_file):
    bank_file.seek(0)
    banco_manual = st.selectbox(
        "Seleccioná el banco manualmente",
        list(BANK_PARSERS.keys()),
        key=f"banco_manual_{st.session_state.uploader_nonce}",
    )

# Período (opcional, informativo)
periodo_input = st.text_input(
    "Período (opcional, para el nombre del archivo)",
    placeholder="ej: Diciembre 2025",
    label_visibility="visible",
    key=f"periodo_{st.session_state.uploader_nonce}",
)

# ── Botón de análisis ─────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
has_result = st.session_state.last_reconciliation is not None
cta_col, _ = st.columns([1, 2])
with cta_col:
    action_label = "Nueva Conciliación" if has_result else "▶  Ejecutar Conciliación"
    action_clicked = st.button(action_label, use_container_width=True)

if action_clicked and has_result:
    st.session_state.uploader_nonce += 1
    st.session_state.last_reconciliation = None
    st.rerun()

# ── Procesamiento ─────────────────────────────────────────────────────────────
if action_clicked and not has_result:
    if not bank_file or not mayor_file:
        st.markdown('<div class="alert alert-error">⚠ Necesitás subir ambos archivos antes de ejecutar.</div>', unsafe_allow_html=True)
        st.stop()

    # Detectar banco
    bank_file.seek(0)
    banco = detect_bank(bank_file) or banco_manual
    if not banco:
        st.error("No se pudo identificar el banco. Seleccionalo manualmente.")
        st.stop()

    banco_icon = {"BBVA": "🟦", "BNA": "🟩", "Macro": "🟧", "Santander": "🟥"}.get(banco, "🏦")

    with st.spinner("Procesando..."):
        try:
            bank_file.seek(0)
            bank_df  = BANK_PARSERS[banco](bank_file)
            mayor_df = parse_mayor(mayor_file)
            bank_concepts = load_bank_concepts().get(banco, [])
            result   = reconcile(bank_df, mayor_df, bank_concepts=bank_concepts)

            periodo = periodo_input.strip() or (
                f"{bank_df['Fecha'].min().strftime('%d/%m/%Y')} — {bank_df['Fecha'].max().strftime('%d/%m/%Y')}"
                if not bank_df.empty else "—"
            )
            st.session_state.last_reconciliation = {
                "result": result,
                "banco": banco,
                "periodo": periodo,
            }
            st.rerun()

        except Exception as e:
            st.error(f"Error al procesar los archivos: {e}")
            st.stop()

current_reconciliation = st.session_state.last_reconciliation

if current_reconciliation:
    result = current_reconciliation["result"]
    banco = current_reconciliation["banco"]
    periodo = current_reconciliation["periodo"]
    banco_icon = {"BBVA": "🟦", "BNA": "🟩", "Macro": "🟧", "Santander": "🟥"}.get(banco, "🏦")

    # ── Banner de resultado ────────────────────────────────────────────────
    total_alertas = result.total_faltantes + result.total_pendientes_agrupados
    if total_alertas == 0:
        st.markdown('<div class="alert alert-ok">✅ <strong>Conciliación perfecta</strong> — Todos los movimientos del banco están registrados en el sistema.</div>', unsafe_allow_html=True)
    elif total_alertas <= 10:
        st.markdown(f'<div class="alert alert-warn">⚠ <strong>{total_alertas} alerta(s) de conciliación</strong> — Revisá los detalles abajo.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alert alert-error">🚨 <strong>{total_alertas} alertas de conciliación</strong> — Requiere atención.</div>', unsafe_allow_html=True)

    # ── KPI cards ─────────────────────────────────────────────────────────
    pct = result.pct_conciliado
    prog_color = "#22C55E" if pct >= 95 else "#F59E0B" if pct >= 80 else "#EF4444"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="stat-card info">
          <div class="stat-label">{banco_icon} Banco</div>
          <div class="stat-value">{result.banco_total}</div>
          <div class="stat-sub">movimientos totales</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="stat-card ok">
          <div class="stat-label">✓ Conciliados</div>
          <div class="stat-value">{result.conciliados}</div>
          <div class="prog-wrap"><div class="prog-bar" style="width:{pct:.0f}%;background:{prog_color}"></div></div>
          <div class="stat-sub">{pct:.1f}% del extracto</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="stat-card {'error' if total_alertas > 0 else 'ok'}">
          <div class="stat-label">⚠ Alertas</div>
          <div class="stat-value">{total_alertas}</div>
          <div class="stat-sub">directas + agrupadas</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        total_falt_amt = result.monto_faltantes_creditos + result.monto_faltantes_debitos
        st.markdown(f"""
        <div class="stat-card {'error' if total_falt_amt != 0 else 'ok'}">
          <div class="stat-label">$ Diferencia</div>
          <div class="stat-value" style="font-size:1.4rem;">${abs(total_falt_amt):,.0f}</div>
          <div class="stat-sub">monto no registrado</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs de detalle ────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        f"🚨 Faltantes y agrupados ({total_alertas})",
        f"📋 Extracto completo ({result.banco_total})",
        f"📒 Mayor sin banco ({len(result.mayor_sin_banco_debe) + len(result.mayor_sin_banco_haber)})",
        "📥 Descargar",
    ])

    with tab1:
        if total_alertas == 0:
            st.success("✅ No hay movimientos pendientes. La conciliación está completa.")
        else:
            if not result.gastos_impuestos_resumen.empty:
                st.markdown('<div class="section-title">Impuestos y gastos bancarios conciliados en forma agrupada mensual</div>', unsafe_allow_html=True)
                st.dataframe(
                    result.gastos_impuestos_resumen.style.format({"Monto": "${:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
                if not result.gastos_impuestos_detalle.empty:
                    st.caption("Los conceptos clasificados por la planilla externa se excluyen de la conciliación directa y se consolidan por mes.")

            if not result.faltantes_creditos.empty:
                st.markdown('<div class="section-title">Créditos en banco sin asiento en mayor</div>', unsafe_allow_html=True)
                st.dataframe(
                    result.faltantes_creditos.style.format({"Credito": "${:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
                st.caption(f"Total: **${result.monto_faltantes_creditos:,.2f}**")

            if not result.faltantes_debitos.empty:
                st.markdown('<div class="section-title">Débitos en banco sin asiento en mayor</div>', unsafe_allow_html=True)
                st.dataframe(
                    result.faltantes_debitos.style.format({"Debito": "${:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
                st.caption(f"Total: **${result.monto_faltantes_debitos:,.2f}**")

    with tab2:
        st.markdown('<div class="section-title">Todos los movimientos del extracto bancario</div>', unsafe_allow_html=True)

        def highlight_estado(row):
            if row.get("Estado") in {"⚠ No en sistema", "⚠ Agrupado mensual pendiente"}:
                return ["background-color: #FEF2F2"] * len(row)
            if row.get("Estado") == "✓ Conciliado agrupado mensual":
                return ["background-color: #FFF7ED"] * len(row)
            return ["background-color: #F0FDF4" if i % 2 == 0 else "" for i in range(len(row))]

        styled = result.banco_completo.style.apply(highlight_estado, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)

    with tab3:
        if result.mayor_sin_banco_debe.empty and result.mayor_sin_banco_haber.empty:
            st.success("✅ Todos los asientos del mayor tienen correspondencia en el banco.")
        else:
            if not result.mayor_sin_banco_debe.empty:
                st.markdown('<div class="section-title">Asientos Debe en mayor sin movimiento en banco</div>', unsafe_allow_html=True)
                st.dataframe(
                    result.mayor_sin_banco_debe.style.format({"Debe": "${:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
            if not result.mayor_sin_banco_haber.empty:
                st.markdown('<div class="section-title">Asientos Haber en mayor sin movimiento en banco</div>', unsafe_allow_html=True)
                st.dataframe(
                    result.mayor_sin_banco_haber.style.format({"Haber": "${:,.2f}"}),
                    use_container_width=True, hide_index=True
                )

    with tab4:
        st.markdown('<div class="section-title">Exportar informe completo</div>', unsafe_allow_html=True)
        st.markdown("""
        El archivo Excel incluye:
        - **Resumen ejecutivo** con KPIs y estado general
        - **Gastos e Impuestos Agrupados** conciliados por mes contra el mayor
        - **Faltantes Créditos** y **Faltantes Débitos** destacados
        - **Mayor sin Banco** — asientos que están en el sistema pero no en el extracto
        - **Extracto Completo** con cada movimiento marcado como conciliado o faltante
        """)

        if not DEFAULT_CONCEPTS_PATH.exists():
            st.warning(f"No se encontró el archivo de configuración de conceptos en {DEFAULT_CONCEPTS_PATH}.")

        excel_bytes = build_excel(result, banco, periodo)
        fname = f"Conciliacion_{banco}_{periodo.replace(' ', '_').replace('/', '-')}.xlsx"

        st.download_button(
            label="⬇  Descargar Excel de Conciliación",
            data=excel_bytes,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

st.markdown("""
<div class="footer">
  Conciliador Bancario by Ascent
</div>
""", unsafe_allow_html=True)
