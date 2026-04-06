#!/usr/bin/env python3
"""
Cap Rate Builder – Hotel Investment
====================================
streamlit run cap_rate_builder_app.py

Fonctionnalités :
  • Build-up de cap rate par ajustements (âge, marque, condition, localisation, taux, prime)
  • Tables de référence 100 % éditables dans l'interface
  • Saisie / import / export de transactions comparables
  • Moyenne, médiane, écart-type des cap rates issus des comps
  • Valorisation : valeur totale, valeur / clé, valeur / m²
  • Table de sensibilité
  • Waterfall Plotly
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date
from typing import Optional

# ════════════════════════════════════════════════════════════════
#  FORMATTING
# ════════════════════════════════════════════════════════════════

def _is_missing(x) -> bool:
    if x is None:
        return True
    try:
        return np.isnan(x) or np.isinf(x)
    except (TypeError, ValueError):
        return False


def fmt_pct(x, d: int = 2) -> str:
    return f"{x:.{d}%}" if not _is_missing(x) else "—"

def fmt_bps(x) -> str:
    return f"{x:+.0f} bps" if not _is_missing(x) else "—"

def fmt_eur(x) -> str:
    if _is_missing(x):
        return "—"
    return f"{x:,.0f} €".replace(",", " ")


# ════════════════════════════════════════════════════════════════
#  DEFAULT REFERENCE TABLES
# ════════════════════════════════════════════════════════════════

def _default_base_rates() -> pd.DataFrame:
    return pd.DataFrame({
        "Segment": [
            "Luxury / Upper-Upscale",
            "Upscale / Full-Service",
            "Select-Service / Upper-Midscale",
            "Limited-Service récent",
            "Limited-Service standard",
            "Limited-Service ancien",
        ],
        "Cap_Rate_Base_Bps": [650, 750, 800, 850, 950, 1050],
    })

def _default_age_table() -> pd.DataFrame:
    return pd.DataFrame({
        "Label": ["Neuf (0-5)", "Récent (6-15)", "Mature (16-25)", "Ancien (26+)"],
        "Age_Min": [0, 6, 16, 26],
        "Age_Max": [5, 15, 25, 200],
        "Adj_Bps": [-75, 25, 100, 200],
    })

def _default_brand_table() -> pd.DataFrame:
    return pd.DataFrame({
        "Brand_Class": ["Premium", "Upper-Midscale", "Midscale", "Economy", "Indépendant"],
        "Adj_Bps": [-75, -25, 0, 150, 250],
    })

def _default_condition_table() -> pd.DataFrame:
    return pd.DataFrame({
        "Condition": ["Rénové < 3 ans", "Bon état", "Standard", "Non rénové", "Mauvais état / PIP lourd"],
        "Adj_Bps": [-100, -25, 0, 125, 275],
    })

def _default_location_table() -> pd.DataFrame:
    return pd.DataFrame({
        "Location_Class": ["CBD / Prime", "Urbain secondaire", "Périphérie / Tertiaire", "Autoroute / rural"],
        "Adj_Bps": [-100, 0, 150, 275],
    })

def _default_comps() -> pd.DataFrame:
    return pd.DataFrame({
        "Nom": [
            "Hilton Garden Inn Lyon Part-Dieu",
            "Ibis Styles Paris Gare du Nord",
            "Novotel Marseille Vieux-Port",
            "B&B Hôtel Bordeaux Centre",
            "Mercure Toulouse Centre Compans",
            "Holiday Inn Express Lille Centre",
            "Marriott Courtyard Nice",
            "Moxy Paris CDG Airport",
        ],
        "Date": ["2024-06", "2024-03", "2024-01", "2023-11", "2023-09", "2023-06", "2023-03", "2023-01"],
        "Segment": [
            "Select-Service / Upper-Midscale",
            "Limited-Service récent",
            "Upscale / Full-Service",
            "Limited-Service standard",
            "Upscale / Full-Service",
            "Limited-Service récent",
            "Upscale / Full-Service",
            "Select-Service / Upper-Midscale",
        ],
        "Localisation": [
            "Urbain secondaire", "CBD / Prime", "CBD / Prime", "Périphérie / Tertiaire",
            "Urbain secondaire", "Urbain secondaire", "CBD / Prime", "Autoroute / rural",
        ],
        "Clés": [152, 210, 183, 98, 144, 122, 165, 200],
        "Surface_m2": [6100, 7800, 7400, 3100, 5900, 4300, 6800, 7200],
        "Prix_EUR": [
            22_800_000, 36_750_000, 28_050_000, 7_840_000,
            18_720_000, 12_810_000, 30_000_000, 18_000_000,
        ],
        "NOI_EUR": [
            1_824_000, 2_940_000, 2_103_750, 744_800,
            1_497_600, 1_089_000, 2_100_000, 1_530_000,
        ],
    })


# ════════════════════════════════════════════════════════════════
#  SESSION STATE
# ════════════════════════════════════════════════════════════════

_STATE_DEFAULTS = {
    "base_rates":      _default_base_rates,
    "age_table":       _default_age_table,
    "brand_table":     _default_brand_table,
    "condition_table": _default_condition_table,
    "location_table":  _default_location_table,
    "comps":           _default_comps,
}

def _init_state():
    for key, factory in _STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = factory()


# ════════════════════════════════════════════════════════════════
#  LOOKUPS
# ════════════════════════════════════════════════════════════════

def _lookup_age(age: int, tbl: pd.DataFrame) -> float:
    row = tbl[(tbl["Age_Min"] <= age) & (tbl["Age_Max"] >= age)]
    return float(row["Adj_Bps"].iloc[0]) if not row.empty else 0.0

def _lookup(val: str, tbl: pd.DataFrame, key_col: str) -> float:
    row = tbl[tbl[key_col] == val]
    return float(row["Adj_Bps"].iloc[0]) if not row.empty else 0.0


# ════════════════════════════════════════════════════════════════
#  CAP RATE ENGINE
# ════════════════════════════════════════════════════════════════

def compute_cap_rate(p: dict) -> dict:
    """Build-up du cap rate à partir des paramètres et des tables en session."""
    br = st.session_state.base_rates
    at = st.session_state.age_table
    bt = st.session_state.brand_table
    ct = st.session_state.condition_table
    lt = st.session_state.location_table

    br_row = br[br["Segment"] == p["segment"]]
    base_bps = float(br_row["Cap_Rate_Base_Bps"].iloc[0]) if not br_row.empty else 900.0

    adj = {
        "age":       _lookup_age(p["age_for_adj"], at),
        "brand":     _lookup(p["brand_class"], bt, "Brand_Class"),
        "condition": _lookup(p["condition"], ct, "Condition"),
        "location":  _lookup(p["location_class"], lt, "Location_Class"),
        "taux":      round((p["taux10y"] - p["taux10y_ref"]) * p["elasticite"] * 10_000, 1),
        "prime":     float(p["prime_bps"]),
    }
    adj_total = sum(adj.values())
    cap_final_bps = max(0.0, base_bps + adj_total)
    cap_base  = base_bps / 10_000
    cap_final = cap_final_bps / 10_000

    noi, rooms, surf = p["noi"], p["rooms"], p["surface_m2"]
    val_final = noi / cap_final if cap_final > 0 else None
    val_base  = noi / cap_base  if cap_base  > 0 else None

    return dict(
        base_bps=base_bps, adj=adj, adj_total=adj_total,
        cap_final_bps=cap_final_bps, cap_base=cap_base, cap_final=cap_final,
        noi=noi, rooms=rooms, surface_m2=surf,
        val_base=val_base, val_final=val_final,
        val_delta=(val_final - val_base) if (val_final and val_base) else None,
        val_key=val_final / rooms if (val_final and rooms) else None,
        val_m2=val_final / surf  if (val_final and surf)  else None,
        noi_key=noi / rooms if rooms else None,
    )


# ════════════════════════════════════════════════════════════════
#  COMPS ANALYTICS
# ════════════════════════════════════════════════════════════════

def enrich_comps(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = raw.copy()
    for c in ["Prix_EUR", "NOI_EUR", "Clés", "Surface_m2"]:
        if c not in df.columns:
            df[c] = np.nan

    hp = df["Prix_EUR"].fillna(0) > 0
    hn = df["NOI_EUR"].fillna(0) > 0
    hk = df["Clés"].fillna(0) > 0
    hs = df["Surface_m2"].fillna(0) > 0

    df["Cap_Rate"]     = np.where(hp & hn, df["NOI_EUR"] / df["Prix_EUR"], np.nan)
    df["Cap_Rate_Pct"] = df["Cap_Rate"] * 100
    df["Prix_Par_Clé"] = np.where(hp & hk, df["Prix_EUR"] / df["Clés"], np.nan)
    df["Prix_Par_m2"]  = np.where(hp & hs, df["Prix_EUR"] / df["Surface_m2"], np.nan)
    df["NOI_Par_Clé"]  = np.where(hn & hk, df["NOI_EUR"]  / df["Clés"], np.nan)

    stats: dict = {}
    cr = df["Cap_Rate"].dropna()
    if len(cr):
        stats.update(n=len(cr), cr_mean=cr.mean(), cr_median=cr.median(),
                     cr_std=cr.std() if len(cr) > 1 else 0.0,
                     cr_min=cr.min(), cr_max=cr.max())
    pk = df["Prix_Par_Clé"].dropna()
    if len(pk):
        stats.update(pk_mean=pk.mean(), pk_median=pk.median(),
                     pk_min=pk.min(), pk_max=pk.max())
    pm = df["Prix_Par_m2"].dropna()
    if len(pm):
        stats.update(pm_mean=pm.mean(), pm_median=pm.median(),
                     pm_min=pm.min(), pm_max=pm.max())
    nk = df["NOI_Par_Clé"].dropna()
    if len(nk):
        stats.update(nk_mean=nk.mean(), nk_median=nk.median())

    return df, stats


# ════════════════════════════════════════════════════════════════
#  PLOTLY CHARTS
# ════════════════════════════════════════════════════════════════

def _waterfall(r: dict) -> go.Figure:
    a = r["adj"]
    labels   = ["Base", "Âge", "Marque", "Condition", "Localisation", "Taux", "Prime", "Final"]
    measures = ["absolute"] + ["relative"] * 6 + ["total"]
    values   = [r["base_bps"], a["age"], a["brand"], a["condition"],
                a["location"], a["taux"], a["prime"], 0]
    texts = []
    for v, m in zip(values, measures):
        if m == "total":
            texts.append(f"{r['cap_final_bps']:.0f}")
        elif m == "absolute":
            texts.append(f"{v:.0f}")
        else:
            texts.append(f"{v:+.0f}")

    fig = go.Figure(go.Waterfall(
        orientation="v", measure=measures, x=labels, y=values,
        text=texts, textposition="outside",
        connector=dict(line=dict(color="rgba(80,80,80,.35)", width=1)),
        increasing=dict(marker=dict(color="#EF553B")),
        decreasing=dict(marker=dict(color="#00CC96")),
        totals=dict(marker=dict(color="#636EFA")),
    ))
    fig.update_layout(title="Build-up du Cap Rate (bps)", yaxis_title="bps",
                      showlegend=False, height=440, margin=dict(t=50, b=40))
    return fig


def _scatter_comps(comps: pd.DataFrame, subj_cr: float) -> Optional[go.Figure]:
    df = comps.dropna(subset=["Cap_Rate"]).copy()
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Nom"], y=df["Cap_Rate_Pct"],
        marker_color="#636EFA", opacity=0.8,
        text=df["Cap_Rate_Pct"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside", name="Comparables",
    ))
    fig.add_hline(y=subj_cr * 100, line_dash="dash", line_color="#EF553B",
                  annotation_text=f"Sujet : {subj_cr*100:.2f}%",
                  annotation_position="top right")
    m = df["Cap_Rate_Pct"].mean()
    fig.add_hline(y=m, line_dash="dot", line_color="#00CC96",
                  annotation_text=f"Moyenne : {m:.2f}%",
                  annotation_position="bottom right")
    fig.update_layout(title="Cap Rates – Comparables vs Sujet",
                      yaxis_title="Cap Rate (%)", height=420, showlegend=True)
    return fig


def _histogram_comps(comps: pd.DataFrame, subj_cr: float) -> Optional[go.Figure]:
    df = comps.dropna(subset=["Cap_Rate"])
    if len(df) < 3:
        return None
    fig = go.Figure(go.Histogram(
        x=df["Cap_Rate_Pct"], nbinsx=12,
        marker_color="#636EFA", opacity=.75,
    ))
    fig.add_vline(x=subj_cr * 100, line_dash="dash", line_color="#EF553B",
                  annotation_text=f"Sujet : {subj_cr*100:.2f}%")
    fig.update_layout(title="Distribution des Cap Rates",
                      xaxis_title="Cap Rate (%)", yaxis_title="Nb",
                      height=360)
    return fig


def _box_comps(comps: pd.DataFrame, subj_cr: float) -> Optional[go.Figure]:
    df = comps.dropna(subset=["Cap_Rate"])
    if len(df) < 3:
        return None
    fig = go.Figure()
    fig.add_trace(go.Box(
        y=df["Cap_Rate_Pct"], boxmean="sd",
        marker_color="#636EFA", name="Comparables",
    ))
    fig.add_hline(y=subj_cr * 100, line_dash="dash", line_color="#EF553B",
                  annotation_text=f"Sujet : {subj_cr*100:.2f}%")
    fig.update_layout(title="Box Plot – Cap Rates",
                      yaxis_title="Cap Rate (%)", height=360, showlegend=False)
    return fig


# ════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(page_title="Cap Rate Builder – Hotel Investment",
                       page_icon="🏨", layout="wide")
    _init_state()
    YEAR = date.today().year

    # ─── SIDEBAR ──────────────────────────────────────────────
    with st.sidebar:
        st.title("🏨 Paramètres")

        st.header("Actif")
        asset   = st.text_input("Nom de l'actif", "Hotel Alpha")
        rooms   = st.number_input("Nombre de clés", 1, 5_000, 120)
        surf    = st.number_input("Surface totale (m²)", 0, 200_000, 4_800, step=100)
        segment = st.selectbox("Segment",
                               st.session_state.base_rates["Segment"].tolist(), index=4)

        age_phys = st.slider("Âge physique (années)", 0, 80, 22)
        yr_reno  = st.number_input("Année dernière rénovation", 1950, YEAR, 2020)
        yrs_reno = max(0, YEAR - int(yr_reno))
        age_adj  = min(age_phys, yrs_reno) if yrs_reno > 0 else age_phys

        brand     = st.selectbox("Classe de marque",
                                 st.session_state.brand_table["Brand_Class"].tolist(), index=2)
        condition = st.selectbox("Condition",
                                 st.session_state.condition_table["Condition"].tolist(), index=2)
        location  = st.selectbox("Localisation",
                                 st.session_state.location_table["Location_Class"].tolist(), index=1)

        st.header("Marché")
        t10y     = st.slider("Taux 10Y actuel (%)", 0.0, 10.0, 4.25, .05)
        t10y_ref = st.slider("Taux 10Y référence (%)", 0.0, 10.0, 4.00, .05)
        elast    = st.slider("Élasticité cap / taux", 0.0, 1.0, 0.25, .05)
        prime    = st.slider("Prime locale (bps)", 0, 300, 50, 5)

        st.header("Revenus")
        noi = st.number_input("NOI stabilisé (€)", 0.0,
                              value=1_000_000.0, step=50_000.0, format="%.0f")

    # ─── COMPUTE ──────────────────────────────────────────────
    p = dict(
        segment=segment, rooms=rooms, surface_m2=surf,
        age_for_adj=age_adj, brand_class=brand,
        condition=condition, location_class=location,
        taux10y=t10y / 100, taux10y_ref=t10y_ref / 100,
        elasticite=elast, prime_bps=prime, noi=noi,
    )
    R = compute_cap_rate(p)
    CE, CS = enrich_comps(st.session_state.comps)

    # ─── HEADER ───────────────────────────────────────────────
    st.title("🏨 Cap Rate Builder – Hotel Investment")
    st.caption(f"**{asset}** · {rooms} clés · {surf:,} m² · {segment}".replace(",", " "))

    tab1, tab2, tab3 = st.tabs([
        "📊 Résultat & Valorisation",
        "⚙️ Tables de référence (éditables)",
        "🏢 Transactions comparables",
    ])

    # ══════════════ TAB 1 : RÉSULTAT ══════════════════════════
    with tab1:

        # --- top KPIs ---
        k = st.columns(7)
        k[0].metric("Cap Rate Base",  fmt_pct(R["cap_base"]))
        k[1].metric("Cap Rate Final", fmt_pct(R["cap_final"]), fmt_bps(R["adj_total"]))
        k[2].metric("Valeur",         fmt_eur(R["val_final"]))
        k[3].metric("Valeur / clé",   fmt_eur(R["val_key"]))
        k[4].metric("Valeur / m²",    fmt_eur(R["val_m2"]))
        k[5].metric("NOI / clé",      fmt_eur(R["noi_key"]))
        if "cr_mean" in CS:
            spread = (R["cap_final"] - CS["cr_mean"]) * 10_000
            k[6].metric("Spread vs comps", fmt_bps(spread),
                        f"Moy comps {CS['cr_mean']*100:.1f}%")
        else:
            k[6].metric("Spread vs comps", "—")

        st.info(f"Âge retenu pour ajustement : **{age_adj} ans** "
                f"(physique {age_phys} · {yrs_reno} ans depuis réno {yr_reno})")

        # --- waterfall + detail ---
        c1, c2 = st.columns([3, 2])
        with c1:
            st.plotly_chart(_waterfall(R), use_container_width=True)

        with c2:
            st.subheader("Détail des ajustements")
            a = R["adj"]
            det = pd.DataFrame({
                "Composant": ["Base", "Âge", "Marque", "Condition",
                              "Localisation", "Taux", "Prime locale", "**Final**"],
                "bps": [R["base_bps"], a["age"], a["brand"], a["condition"],
                        a["location"], a["taux"], a["prime"], R["cap_final_bps"]],
            })
            det["Taux"] = det["bps"] / 10_000
            st.dataframe(
                det.style.format({"bps": "{:+.0f}", "Taux": "{:.2%}"}),
                use_container_width=True, hide_index=True)

        # --- comparaison modèle vs comps ---
        if "cr_mean" in CS:
            st.subheader("Valorisation – Modèle vs Comparables")
            v_mean = noi / CS["cr_mean"] if CS["cr_mean"] > 0 else None
            v_med  = noi / CS["cr_median"] if CS.get("cr_median", 0) > 0 else None
            rows_comp = []
            for label, cr_val, val in [
                ("Modèle (build-up)", R["cap_final"], R["val_final"]),
                ("Moyenne comps",     CS["cr_mean"],  v_mean),
                ("Médiane comps",     CS["cr_median"], v_med),
            ]:
                rows_comp.append({
                    "Approche": label,
                    "Cap Rate": fmt_pct(cr_val),
                    "Valeur": fmt_eur(val),
                    "Valeur / clé": fmt_eur(val / rooms if (val and rooms) else None),
                    "Valeur / m²": fmt_eur(val / surf if (val and surf) else None),
                })
            st.dataframe(pd.DataFrame(rows_comp),
                         use_container_width=True, hide_index=True)

        # --- sensitivity ---
        st.subheader("Sensibilité")
        deltas = [-200, -150, -100, -50, -25, 0, 25, 50, 100, 150, 200]
        sens = []
        for d in deltas:
            cr_b = R["cap_final_bps"] + d
            cr   = cr_b / 10_000
            v    = noi / cr if cr > 0 else None
            sens.append({
                "Δ bps": d,
                "Cap Rate": cr,
                "Valeur": v,
                "Valeur / clé": v / rooms if (v and rooms) else None,
                "Valeur / m²": v / surf  if (v and surf)  else None,
            })
        sdf = pd.DataFrame(sens)

        def _hl(row):
            bg = "background-color: #dbeafe; font-weight: bold" if row["Δ bps"] == 0 else ""
            return [bg] * len(row)

        st.dataframe(
            sdf.style
               .format({
                   "Δ bps": "{:+.0f}",
                   "Cap Rate": "{:.2%}",
                   "Valeur": lambda x: fmt_eur(x),
                   "Valeur / clé": lambda x: fmt_eur(x),
                   "Valeur / m²": lambda x: fmt_eur(x),
               }, na_rep="—")
               .apply(_hl, axis=1),
            use_container_width=True, hide_index=True)

        # --- hypothèses ---
        with st.expander("Hypothèses retenues"):
            hyp = pd.DataFrame({
                "Variable": ["Segment", "Âge physique", "Dernière réno", "Marque",
                              "Condition", "Localisation", "Taux 10Y", "Taux réf.",
                              "Élasticité", "Prime locale", "NOI"],
                "Valeur": [segment, age_phys, yr_reno, brand, condition, location,
                           f"{t10y:.2f}%", f"{t10y_ref:.2f}%", elast,
                           f"{prime} bps", fmt_eur(noi)],
            })
            st.dataframe(hyp, use_container_width=True, hide_index=True)

        # --- download ---
        export = pd.DataFrame([{
            "Actif": asset, "Segment": segment, "Clés": rooms,
            "Surface_m2": surf, "Âge_physique": age_phys,
            "Rénovation": yr_reno, "Marque": brand,
            "Condition": condition, "Localisation": location,
            "Taux_10Y_%": t10y, "Taux_10Y_ref_%": t10y_ref,
            "Élasticité": elast, "Prime_bps": prime, "NOI_EUR": noi,
            "CR_Base_bps": R["base_bps"], "Adj_Total_bps": R["adj_total"],
            "CR_Final_bps": R["cap_final_bps"],
            "CR_Final_%": round(R["cap_final"] * 100, 2),
            "Valeur_EUR": R["val_final"],
            "Valeur_par_clé": R["val_key"],
            "Valeur_par_m2": R["val_m2"],
        }])
        st.download_button("📥 Télécharger résultat (CSV)",
                           export.to_csv(index=False).encode("utf-8"),
                           f"caprate_{asset.replace(' ','_')}.csv", "text/csv")

    # ══════════════ TAB 2 : TABLES ÉDITABLES ══════════════════
    with tab2:
        st.subheader("Tables de référence – Éditables")
        st.caption("Modifiez directement les valeurs. Les changements sont pris en "
                   "compte immédiatement dans le calcul.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Cap Rates de base par segment")
            st.session_state.base_rates = st.data_editor(
                st.session_state.base_rates, key="ed_br",
                use_container_width=True, hide_index=True, num_rows="dynamic")
            if st.button("↻ Réinitialiser", key="rst_br"):
                st.session_state.base_rates = _default_base_rates(); st.rerun()

        with c2:
            st.markdown("##### Ajustements – Âge")
            st.session_state.age_table = st.data_editor(
                st.session_state.age_table, key="ed_age",
                use_container_width=True, hide_index=True, num_rows="dynamic")
            if st.button("↻ Réinitialiser", key="rst_age"):
                st.session_state.age_table = _default_age_table(); st.rerun()

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("##### Ajustements – Marque")
            st.session_state.brand_table = st.data_editor(
                st.session_state.brand_table, key="ed_br2",
                use_container_width=True, hide_index=True, num_rows="dynamic")
            if st.button("↻ Réinitialiser", key="rst_br2"):
                st.session_state.brand_table = _default_brand_table(); st.rerun()

        with c4:
            st.markdown("##### Ajustements – Condition")
            st.session_state.condition_table = st.data_editor(
                st.session_state.condition_table, key="ed_co",
                use_container_width=True, hide_index=True, num_rows="dynamic")
            if st.button("↻ Réinitialiser", key="rst_co"):
                st.session_state.condition_table = _default_condition_table(); st.rerun()

        st.markdown("##### Ajustements – Localisation")
        st.session_state.location_table = st.data_editor(
            st.session_state.location_table, key="ed_lo",
            use_container_width=True, hide_index=True, num_rows="dynamic")
        if st.button("↻ Réinitialiser", key="rst_lo"):
            st.session_state.location_table = _default_location_table(); st.rerun()

        st.markdown("---")
        if st.button("🔄 Tout réinitialiser aux valeurs par défaut", type="primary"):
            for k, fn in _STATE_DEFAULTS.items():
                if k != "comps":
                    st.session_state[k] = fn()
            st.rerun()

    # ══════════════ TAB 3 : COMPARABLES ═══════════════════════
    with tab3:
        st.subheader("Transactions comparables")
        st.caption("Saisissez, importez ou exportez des transactions de marché. "
                   "Le cap rate et les métriques par clé / m² sont calculés automatiquement.")

        # --- Import ---
        ci1, ci2 = st.columns([3, 1])
        with ci2:
            mode = st.radio("Mode", ["Remplacer", "Ajouter"], horizontal=True,
                            label_visibility="collapsed")
        with ci1:
            up = st.file_uploader(
                "📂 Importer CSV",
                type=["csv"],
                help="Colonnes : Nom, Date, Segment, Localisation, "
                     "Clés, Surface_m2, Prix_EUR, NOI_EUR",
            )
        if up:
            try:
                imp = pd.read_csv(up)
                if mode == "Ajouter":
                    st.session_state.comps = pd.concat(
                        [st.session_state.comps, imp], ignore_index=True)
                else:
                    st.session_state.comps = imp
                st.success(f"{len(imp)} transaction(s) importée(s) ({mode.lower()}).")
            except Exception as e:
                st.error(f"Erreur : {e}")

        # template download
        tpl = pd.DataFrame({
            "Nom": ["Exemple Hôtel"], "Date": ["2024-01"],
            "Segment": ["Limited-Service standard"],
            "Localisation": ["Urbain secondaire"],
            "Clés": [100], "Surface_m2": [4000],
            "Prix_EUR": [10_000_000], "NOI_EUR": [850_000],
        })
        st.download_button("📄 Modèle CSV vide",
                           tpl.to_csv(index=False).encode("utf-8"),
                           "template_comps.csv", "text/csv")

        # --- Editable comps ---
        st.markdown("##### Saisie / édition des comparables")
        st.session_state.comps = st.data_editor(
            st.session_state.comps, key="ed_cmp",
            use_container_width=True, hide_index=True, num_rows="dynamic",
            column_config={
                "Prix_EUR":   st.column_config.NumberColumn("Prix (€)", format="%.0f"),
                "NOI_EUR":    st.column_config.NumberColumn("NOI (€)",  format="%.0f"),
                "Clés":       st.column_config.NumberColumn("Clés",     format="%d"),
                "Surface_m2": st.column_config.NumberColumn("m²",       format="%d"),
            })
        if st.button("↻ Réinitialiser les comparables", key="rst_cmp"):
            st.session_state.comps = _default_comps(); st.rerun()

        # recompute after potential edit
        CE, CS = enrich_comps(st.session_state.comps)

        # --- enriched display ---
        st.markdown("##### Tableau enrichi (colonnes calculées)")
        show = ["Nom", "Date", "Segment", "Localisation", "Clés", "Surface_m2",
                "Prix_EUR", "NOI_EUR", "Cap_Rate_Pct",
                "Prix_Par_Clé", "Prix_Par_m2", "NOI_Par_Clé"]
        show = [c for c in show if c in CE.columns]
        st.dataframe(
            CE[show].style.format({
                "Prix_EUR":     lambda x: fmt_eur(x),
                "NOI_EUR":      lambda x: fmt_eur(x),
                "Cap_Rate_Pct": "{:.2f}%",
                "Prix_Par_Clé": lambda x: fmt_eur(x),
                "Prix_Par_m2":  lambda x: fmt_eur(x),
                "NOI_Par_Clé":  lambda x: fmt_eur(x),
            }, na_rep="—"),
            use_container_width=True, hide_index=True)

        # --- statistics ---
        st.markdown("---")
        st.subheader("Statistiques des transactions")

        n = CS.get("n", 0)
        if n > 0:
            s = st.columns(6)
            s[0].metric("Nb transactions", n)
            s[1].metric("Cap rate moyen",   fmt_pct(CS["cr_mean"]))
            s[2].metric("Cap rate médian",  fmt_pct(CS["cr_median"]))
            s[3].metric("Écart-type",       fmt_bps(CS["cr_std"] * 10_000))
            s[4].metric("Min",              fmt_pct(CS["cr_min"]))
            s[5].metric("Max",              fmt_pct(CS["cr_max"]))

            # value metrics
            s2 = st.columns(6)
            for i, (lab, key) in enumerate([
                ("Prix moy / clé", "pk_mean"),
                ("Prix méd / clé", "pk_median"),
                ("Prix moy / m²",  "pm_mean"),
                ("Prix méd / m²",  "pm_median"),
                ("NOI moy / clé",  "nk_mean"),
                ("NOI méd / clé",  "nk_median"),
            ]):
                if key in CS:
                    s2[i].metric(lab, fmt_eur(CS[key]))

            # --- sujet vs comps ---
            st.markdown("---")
            st.subheader("Positionnement du sujet vs Comparables")

            v_mean = noi / CS["cr_mean"]   if CS["cr_mean"]   > 0 else None
            v_med  = noi / CS["cr_median"] if CS["cr_median"] > 0 else None
            # ± 1 σ
            cr_lo = CS["cr_mean"] + CS["cr_std"]
            cr_hi = CS["cr_mean"] - CS["cr_std"]
            v_lo  = noi / cr_lo if cr_lo > 0 else None
            v_hi  = noi / cr_hi if cr_hi > 0 else None

            comp_rows = [
                ("Modèle (build-up)", R["cap_final"], R["val_final"]),
                ("Moyenne comps",     CS["cr_mean"],  v_mean),
                ("Médiane comps",     CS["cr_median"], v_med),
                ("Moy + 1σ (conservateur)", cr_lo, v_lo),
                ("Moy – 1σ (agressif)",     cr_hi, v_hi),
            ]
            comp_tbl = []
            for label, cr, v in comp_rows:
                comp_tbl.append({
                    "Approche": label,
                    "Cap Rate": fmt_pct(cr),
                    "Valeur": fmt_eur(v),
                    "Valeur / clé": fmt_eur(v / rooms if (v and rooms) else None),
                    "Valeur / m²": fmt_eur(v / surf if (v and surf) else None),
                })
            st.dataframe(pd.DataFrame(comp_tbl),
                         use_container_width=True, hide_index=True)

            # --- charts ---
            ch1, ch2 = st.columns(2)
            with ch1:
                fig = _scatter_comps(CE, R["cap_final"])
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            with ch2:
                fig = _box_comps(CE, R["cap_final"])
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

            fig_h = _histogram_comps(CE, R["cap_final"])
            if fig_h:
                st.plotly_chart(fig_h, use_container_width=True)

        else:
            st.warning("Aucune transaction exploitable. "
                       "Saisissez au moins un comparable avec Prix et NOI renseignés.")

        # --- download ---
        st.markdown("---")
        st.download_button(
            "📥 Télécharger comparables enrichis (CSV)",
            CE.to_csv(index=False).encode("utf-8"),
            "comps_enrichis.csv", "text/csv")

    # ─── FOOTER ───────────────────────────────────────────────
    with st.expander("📝 Notes méthodologiques"):
        st.markdown("""
| Composant | Description |
|-----------|-------------|
| **Base rate** | Déterminé par segment (luxury → limited-service ancien) |
| **Âge** | Min(âge physique, années depuis réno) – pénalise l'obsolescence |
| **Marque** | Franchise value : premium = spread négatif, indépendant = prime |
| **Condition** | PIP réalisé vs à réaliser, état physique |
| **Localisation** | CBD / prime vs autoroute / rural |
| **Taux longs** | (Taux actuel – Taux réf.) × Élasticité |
| **Prime locale** | Risque pays, liquidité du marché, réglementation |

**Valorisation** : Valeur = NOI stabilisé ÷ Cap Rate

**Limites** : modèle simplifié. Un underwriting complet intègre
ADR, RevPAR, GOP, management fees, FF&E reserve, CAPEX/PIP, IRR, equity multiple.
Les tables doivent être recalibrées avec des transactions locales.
        """)


if __name__ == "__main__":
    main()
