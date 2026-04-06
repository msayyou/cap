# cap_rate_builder_app.py
# Lance avec : streamlit run cap_rate_builder_app.py

import streamlit as st
import pandas as pd
import numpy as np
import random

# =========================
# Page config
# =========================
st.set_page_config(
    page_title="Cap Rate Builder – Hotel Investment",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# Custom CSS
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 {
    font-family: 'DM Serif Display', serif;
}

.main-title {
    font-family: 'DM Serif Display', serif;
    font-size: 2.4rem;
    color: #1a1a2e;
    border-bottom: 3px solid #c9a84c;
    padding-bottom: 0.4rem;
    margin-bottom: 0.2rem;
}

.subtitle {
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

.kpi-box {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    color: white;
    border-left: 4px solid #c9a84c;
    margin-bottom: 0.5rem;
}

.kpi-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #c9a84c;
    font-weight: 600;
}

.kpi-value {
    font-size: 1.7rem;
    font-family: 'DM Serif Display', serif;
    color: white;
    margin-top: 0.1rem;
}

.kpi-delta {
    font-size: 0.8rem;
    color: #aaa;
    margin-top: 0.1rem;
}

.section-title {
    font-family: 'DM Serif Display', serif;
    font-size: 1.3rem;
    color: #1a1a2e;
    border-left: 4px solid #c9a84c;
    padding-left: 0.7rem;
    margin-bottom: 0.8rem;
    margin-top: 1.5rem;
}

.comparable-card {
    background: #f8f7f2;
    border: 1px solid #e8e0cc;
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
}

.comparable-card .comp-name {
    font-weight: 600;
    color: #1a1a2e;
    font-size: 0.95rem;
}

.comparable-card .comp-tag {
    display: inline-block;
    background: #c9a84c;
    color: white;
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-left: 6px;
}

.scenario-card {
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.4rem;
    border-left: 5px solid;
}

.scenario-bear {
    background: #fff5f5;
    border-color: #e05c5c;
}

.scenario-base {
    background: #f5f8ff;
    border-color: #4a7fc1;
}

.scenario-bull {
    background: #f5fff7;
    border-color: #3aaa6e;
}

.tab-label {
    font-size: 0.85rem;
    font-weight: 600;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 0px;
    border-bottom: 2px solid #e8e0cc;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif;
    font-weight: 500;
    color: #666;
    padding: 0.5rem 1.2rem;
}

.stTabs [aria-selected="true"] {
    color: #1a1a2e !important;
    border-bottom: 3px solid #c9a84c !important;
    font-weight: 600;
}

div[data-testid="metric-container"] {
    background: #f8f7f2;
    border: 1px solid #e8e0cc;
    border-radius: 10px;
    padding: 0.8rem 1rem;
}

.highlight-box {
    background: #fffbef;
    border: 1px solid #c9a84c;
    border-radius: 10px;
    padding: 0.8rem 1.2rem;
    margin: 0.5rem 0;
    font-size: 0.88rem;
    color: #555;
}

.influence-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
}

.factor-up {
    color: #e05c5c;
    font-weight: 600;
}

.factor-down {
    color: #3aaa6e;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# =========================
# Formatting helpers
# =========================
def fmt_pct(x):
    return f"{x:.2%}" if pd.notna(x) else "N/A"

def fmt_bps(x):
    return f"{x:+.0f} bps" if pd.notna(x) else "N/A"

def fmt_eur(x, per_k=False):
    if pd.isna(x) or x is None:
        return "N/A"
    if per_k:
        return f"€ {x/1000:,.0f}k".replace(",", " ")
    if abs(x) >= 1_000_000:
        return f"€ {x/1_000_000:.2f}M".replace(".", ",")
    return f"€ {x:,.0f}".replace(",", " ")


# =========================
# Reference tables
# =========================
@st.cache_data
def build_base_rates():
    return pd.DataFrame({
        "Segment": [
            "Luxury / Upper-Upscale",
            "Upscale / Full-Service",
            "Limited-Service récent",
            "Limited-Service standard",
            "Limited-Service ancien",
        ],
        "CapRate_Base_Bps": [750, 800, 850, 950, 1050],
    })

@st.cache_data
def build_adjustment_tables():
    age_table = pd.DataFrame({
        "Age_Min": [0, 6, 16, 26],
        "Age_Max": [5, 15, 25, 200],
        "Adj_Age_Bps": [-75, 25, 100, 200],
    })
    brand_table = pd.DataFrame({
        "Brand_Class": ["Premium", "Midscale", "Economy", "Indépendant"],
        "Adj_Brand_Bps": [-50, 0, 150, 250],
    })
    condition_table = pd.DataFrame({
        "Condition": ["Rénové <3 ans", "Standard", "Non rénové", "Mauvais état"],
        "Adj_Condition_Bps": [-75, 0, 125, 250],
    })
    location_table = pd.DataFrame({
        "Location_Class": ["Primaire", "Secondaire", "Tertiaire", "Autoroute / rural"],
        "Adj_Location_Bps": [-75, 0, 150, 250],
    })
    return age_table, brand_table, condition_table, location_table


# =========================
# Market benchmarks
# =========================
@st.cache_data
def build_market_benchmarks():
    return pd.DataFrame({
        "Marché": [
            "Paris – Centre",
            "Paris – Périphérie",
            "Lyon",
            "Bordeaux",
            "Marseille",
            "Nice / Côte d'Azur",
            "Londres – Prime",
            "Londres – Secondary",
            "Madrid",
            "Barcelone",
            "Amsterdam",
            "Berlin",
            "Munich",
            "Dubaï",
            "Rome",
            "Milan",
        ],
        "Pays": [
            "France","France","France","France","France","France",
            "Royaume-Uni","Royaume-Uni",
            "Espagne","Espagne",
            "Pays-Bas",
            "Allemagne","Allemagne",
            "UAE",
            "Italie","Italie",
        ],
        "Cap_Rate_Min_Bps": [
            500, 650, 700, 750, 750, 650,
            450, 600,
            650, 600,
            600,
            650, 600,
            700,
            650, 600,
        ],
        "Cap_Rate_Max_Bps": [
            700, 850, 950, 1050, 1000, 900,
            650, 850,
            900, 850,
            850,
            900, 800,
            1000,
            900, 800,
        ],
        "RevPAR_Ref_EUR": [
            180, 90, 95, 80, 75, 130,
            200, 110,
            100, 120,
            130,
            90, 115,
            160,
            110, 130,
        ],
        "Tendance": [
            "→ Stable","↑ Compression","↑ Compression","→ Stable","→ Stable","↑ Compression",
            "↓ Expansion","→ Stable",
            "↑ Compression","↑ Compression",
            "→ Stable",
            "↓ Expansion légère","→ Stable",
            "↑ Compression",
            "→ Stable","→ Stable",
        ],
    })


# =========================
# Fictitious comparables
# =========================
@st.cache_data
def build_comparables():
    random.seed(42)
    np.random.seed(42)
    comps = [
        {"Nom": "Ibis Styles Lyon Part-Dieu", "Ville": "Lyon", "Pays": "France", "Segment": "Limited-Service récent", "Rooms": 145, "CapRate_Bps": 820, "Prix_M_EUR": 18.5, "Année": 2023, "Source": "JLL"},
        {"Nom": "Mercure Bordeaux Centre", "Ville": "Bordeaux", "Pays": "France", "Segment": "Upscale / Full-Service", "Rooms": 98, "CapRate_Bps": 780, "Prix_M_EUR": 22.0, "Année": 2023, "Source": "BNP RE"},
        {"Nom": "B&B Hôtel Marseille Est", "Ville": "Marseille", "Pays": "France", "Segment": "Limited-Service standard", "Rooms": 110, "CapRate_Bps": 950, "Prix_M_EUR": 9.8, "Année": 2022, "Source": "CBRE"},
        {"Nom": "Holiday Inn Express Nice", "Ville": "Nice", "Pays": "France", "Segment": "Limited-Service récent", "Rooms": 130, "CapRate_Bps": 720, "Prix_M_EUR": 28.0, "Année": 2024, "Source": "Cushman"},
        {"Nom": "Novotel Paris Bercy", "Ville": "Paris", "Pays": "France", "Segment": "Upscale / Full-Service", "Rooms": 200, "CapRate_Bps": 560, "Prix_M_EUR": 68.0, "Année": 2023, "Source": "JLL"},
        {"Nom": "Hampton by Hilton Berlin", "Ville": "Berlin", "Pays": "Allemagne", "Segment": "Limited-Service récent", "Rooms": 175, "CapRate_Bps": 790, "Prix_M_EUR": 32.0, "Année": 2023, "Source": "Savills"},
        {"Nom": "Marriott Courtyard Madrid", "Ville": "Madrid", "Pays": "Espagne", "Segment": "Upscale / Full-Service", "Rooms": 158, "CapRate_Bps": 740, "Prix_M_EUR": 41.0, "Année": 2024, "Source": "CBRE"},
        {"Nom": "Premier Inn London Bridge", "Ville": "Londres", "Pays": "Royaume-Uni", "Segment": "Limited-Service récent", "Rooms": 240, "CapRate_Bps": 510, "Prix_M_EUR": 85.0, "Année": 2023, "Source": "JLL"},
        {"Nom": "Kyriad Clermont-Ferrand", "Ville": "Clermont-Fd", "Pays": "France", "Segment": "Limited-Service standard", "Rooms": 88, "CapRate_Bps": 1020, "Prix_M_EUR": 7.2, "Année": 2022, "Source": "Knight Frank"},
        {"Nom": "AC Hotel Barcelona", "Ville": "Barcelone", "Pays": "Espagne", "Segment": "Upscale / Full-Service", "Rooms": 122, "CapRate_Bps": 640, "Prix_M_EUR": 52.0, "Année": 2024, "Source": "Savills"},
        {"Nom": "Ibis Budget Roissy CDG", "Ville": "Paris", "Pays": "France", "Segment": "Limited-Service ancien", "Rooms": 300, "CapRate_Bps": 1100, "Prix_M_EUR": 19.5, "Année": 2022, "Source": "BNP RE"},
        {"Nom": "Mövenpick Amsterdam", "Ville": "Amsterdam", "Pays": "Pays-Bas", "Segment": "Upscale / Full-Service", "Rooms": 188, "CapRate_Bps": 660, "Prix_M_EUR": 78.0, "Année": 2023, "Source": "CBRE"},
    ]
    df = pd.DataFrame(comps)
    df["Prix_Par_Cle_K_EUR"] = (df["Prix_M_EUR"] * 1000) / df["Rooms"]
    return df


# =========================
# Mapping helpers
# =========================
def map_age_adjustment(age, age_table):
    row = age_table[(age_table["Age_Min"] <= age) & (age_table["Age_Max"] >= age)]
    return float(row["Adj_Age_Bps"].iloc[0]) if not row.empty else 0.0

def map_exact_adjustment(value, table, key_col, value_col):
    row = table[table[key_col] == value]
    return float(row[value_col].iloc[0]) if not row.empty else 0.0


# =========================
# Core computation
# =========================
def compute_cap_rate(inputs_df, base_rates_df, age_table, brand_table, condition_table, location_table):
    df = inputs_df.merge(base_rates_df, on="Segment", how="left")
    df["Adj_Age_Bps"] = df["Age_For_Adjustment"].apply(lambda x: map_age_adjustment(x, age_table))
    df["Adj_Brand_Bps"] = df["Brand_Class"].apply(lambda x: map_exact_adjustment(x, brand_table, "Brand_Class", "Adj_Brand_Bps"))
    df["Adj_Condition_Bps"] = df["Condition"].apply(lambda x: map_exact_adjustment(x, condition_table, "Condition", "Adj_Condition_Bps"))
    df["Adj_Location_Bps"] = df["Location_Class"].apply(lambda x: map_exact_adjustment(x, location_table, "Location_Class", "Adj_Location_Bps"))
    df["Adj_Taux_Bps"] = (df["Taux10Y"] - df["Taux10Y_Ref"]) * df["Elasticite"] * 10000
    df["Adj_Prime_Locale_Bps"] = df["Prime_Risque_Locale_Bps"]
    df["Adj_Total_Bps"] = (
        df["Adj_Age_Bps"] + df["Adj_Brand_Bps"] + df["Adj_Condition_Bps"]
        + df["Adj_Location_Bps"] + df["Adj_Taux_Bps"] + df["Adj_Prime_Locale_Bps"]
    )
    df["CapRate_Final_Bps"] = (df["CapRate_Base_Bps"] + df["Adj_Total_Bps"]).clip(lower=0)
    df["CapRate_Base"] = df["CapRate_Base_Bps"] / 10000
    df["CapRate_Final"] = df["CapRate_Final_Bps"] / 10000
    df["Value_Base"] = np.where(df["CapRate_Base"] > 0, df["NOI"] / df["CapRate_Base"], np.nan)
    df["Value_Final"] = np.where(df["CapRate_Final"] > 0, df["NOI"] / df["CapRate_Final"], np.nan)
    df["Value_Delta"] = df["Value_Final"] - df["Value_Base"]
    df["Value_Per_Key"] = np.where(df["Rooms"] > 0, df["Value_Final"] / df["Rooms"], np.nan)
    return df


def build_asset_inputs(name, rooms, segment, age_physical, year_last_reno, brand_class, condition,
                        location_class, taux10y, taux10y_ref, elasticite, prime_locale_bps, noi):
    current_year = pd.Timestamp.today().year
    years_since_reno = max(0, current_year - int(year_last_reno))
    age_for_adj = min(age_physical, years_since_reno) if years_since_reno > 0 else age_physical
    return pd.DataFrame({
        "Asset_Name": [name], "Rooms": [rooms], "Segment": [segment],
        "Age_Physical": [age_physical], "Year_Last_Reno": [int(year_last_reno)],
        "Years_Since_Reno": [years_since_reno], "Age_For_Adjustment": [age_for_adj],
        "Brand_Class": [brand_class], "Condition": [condition], "Location_Class": [location_class],
        "Taux10Y": [taux10y / 100], "Taux10Y_Ref": [taux10y_ref / 100],
        "Elasticite": [elasticite], "Prime_Risque_Locale_Bps": [prime_locale_bps], "NOI": [noi],
    })


# =========================
# Scenario builder
# =========================
def build_scenarios(base_cap_rate_bps, noi, rooms):
    scenarios = {
        "🐻 Bear (stress)": {
            "cap_rate_bps": base_cap_rate_bps + 150,
            "noi_mult": 0.85,
            "color": "#e05c5c",
            "class": "scenario-bear",
        },
        "📊 Base": {
            "cap_rate_bps": base_cap_rate_bps,
            "noi_mult": 1.0,
            "color": "#4a7fc1",
            "class": "scenario-base",
        },
        "🐂 Bull (upside)": {
            "cap_rate_bps": base_cap_rate_bps - 100,
            "noi_mult": 1.15,
            "color": "#3aaa6e",
            "class": "scenario-bull",
        },
    }
    for k, v in scenarios.items():
        cr = max(v["cap_rate_bps"], 100) / 10000
        adj_noi = noi * v["noi_mult"]
        v["value"] = adj_noi / cr if cr > 0 else None
        v["value_per_key"] = v["value"] / rooms if rooms > 0 else None
        v["cap_rate"] = cr
        v["noi"] = adj_noi
    return scenarios


# =========================
# Influence factors display
# =========================
def display_influence_factors():
    factors = {
        "↑ Hausse des taux longs": ("Comprime les valorisations", "+"),
        "↓ Baisse du RevPAR": ("Réduit le NOI et la valeur", "+"),
        "⚠️ PIP / CAPEX important": ("Augmente le risque acheteur", "+"),
        "📉 Baisse de l'occupancy": ("Signal de demande faible", "+"),
        "🏗️ Vieillissement du bâti": ("Hausse des charges d'entretien", "+"),
        "🌟 Rénovation récente": ("Compression du cap rate", "-"),
        "📍 Localisation prime": ("Prime de liquidité", "-"),
        "🏷️ Marque forte (franchise)": ("Visibilité et RevPAR soutenu", "-"),
        "📈 Croissance du marché local": ("Upside sur NOI futur", "-"),
        "🏦 Liquidité du marché": ("Compétition acheteurs → compression", "-"),
    }
    st.markdown("""
    <div class='section-title'>Facteurs d'influence sur le cap rate</div>
    <table style='width:100%; font-size:0.84rem; border-collapse:collapse;'>
    <tr style='background:#1a1a2e; color:#c9a84c;'>
        <th style='padding:6px 10px; text-align:left;'>Facteur</th>
        <th style='padding:6px 10px; text-align:left;'>Impact</th>
        <th style='padding:6px 10px; text-align:center;'>Effet cap rate</th>
    </tr>
    """ + "".join([
        f"""<tr style='border-bottom:1px solid #eee;'>
        <td style='padding:5px 10px; font-weight:500;'>{f}</td>
        <td style='padding:5px 10px; color:#555;'>{desc}</td>
        <td style='padding:5px 10px; text-align:center;
            color: {"#e05c5c" if sign=="+" else "#3aaa6e"};
            font-weight:700;'>{("▲ Hausse" if sign=="+" else "▼ Baisse")}</td>
        </tr>"""
        for f, (desc, sign) in factors.items()
    ]) + "</table>", unsafe_allow_html=True)


# =========================
# MAIN APP
# =========================
def main():
    st.markdown("<div class='main-title'>🏨 Cap Rate Builder – Hotel Investment</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Outil d'estimation de cap rate hôtelier · Comparaison multi-actifs · Scénarios · Benchmarks de marché · Comparables fictifs</div>", unsafe_allow_html=True)

    base_rates = build_base_rates()
    age_table, brand_table, condition_table, location_table = build_adjustment_tables()
    market_benchmarks = build_market_benchmarks()
    comparables = build_comparables()
    current_year = pd.Timestamp.today().year

    SEGMENTS = base_rates["Segment"].tolist()
    BRANDS = ["Premium", "Midscale", "Economy", "Indépendant"]
    CONDITIONS = ["Rénové <3 ans", "Standard", "Non rénové", "Mauvais état"]
    LOCATIONS = ["Primaire", "Secondaire", "Tertiaire", "Autoroute / rural"]

    # -------------------------------------------------------
    # TABS
    # -------------------------------------------------------
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏢  Analyse actif", "📊  Multi-actifs", "🎯  Scénarios", "🌍  Benchmarks marché", "📋  Comparables"
    ])

    # =====================
    # TAB 1 – Single asset
    # =====================
    with tab1:
        col_sidebar, col_main = st.columns([1, 2.5])

        with col_sidebar:
            st.markdown("### Paramètres de l'actif")

            asset_name = st.text_input("Nom de l'actif", "Hotel A", key="a1_name")
            rooms = st.number_input("Nombre de chambres / clés", 1, 3000, 120, 1, key="a1_rooms")
            segment = st.selectbox("Segment", SEGMENTS, index=3, key="a1_seg")

            st.markdown("**Âge & rénovation**")
            age_physical = st.slider("Âge physique (années)", 0, 60, 22, key="a1_age")
            year_last_reno = st.number_input("Année dernière rénovation", 1950, current_year, 2020, key="a1_reno")
            years_since_reno = max(0, current_year - int(year_last_reno))
            age_for_adj = min(age_physical, years_since_reno) if years_since_reno > 0 else age_physical

            brand_class = st.selectbox("Classe de marque", BRANDS, index=1, key="a1_brand")
            condition = st.selectbox("Condition", CONDITIONS, index=2, key="a1_cond")
            location_class = st.selectbox("Localisation", LOCATIONS, index=2, key="a1_loc")

            st.markdown("**Marché & taux**")
            taux10y = st.slider("Taux 10Y actuel (%)", 0.0, 10.0, 4.25, 0.05, key="a1_tx")
            taux10y_ref = st.slider("Taux 10Y référence (%)", 0.0, 10.0, 4.00, 0.05, key="a1_txr")
            elasticite = st.slider("Élasticité cap rate / taux", 0.0, 1.0, 0.25, 0.05, key="a1_elas")
            prime_locale = st.slider("Prime de risque locale (bps)", 0, 300, 50, 5, key="a1_prime")

            st.markdown("**NOI**")
            noi = st.number_input("NOI stabilisé (€)", 0.0, value=1_000_000.0, step=50_000.0, format="%.0f", key="a1_noi")

        with col_main:
            inputs_df = build_asset_inputs(
                asset_name, rooms, segment, age_physical, year_last_reno,
                brand_class, condition, location_class, taux10y, taux10y_ref,
                elasticite, prime_locale, noi
            )
            calc = compute_cap_rate(inputs_df, base_rates, age_table, brand_table, condition_table, location_table)
            row = calc.iloc[0]

            # KPIs
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.metric("Cap Rate Base", fmt_pct(row["CapRate_Base"]))
            with k2:
                st.metric("Cap Rate Final", fmt_pct(row["CapRate_Final"]), fmt_bps(row["Adj_Total_Bps"]))
            with k3:
                st.metric("Valeur implicite", fmt_eur(row["Value_Final"]))
            with k4:
                st.metric("Valeur / clé", fmt_eur(row["Value_Per_Key"]))

            st.markdown(f"""
            <div class='highlight-box'>
            ℹ️ Âge retenu pour l'ajustement : <strong>{age_for_adj} ans</strong>
            (âge physique {age_physical} ans · {years_since_reno} ans depuis la dernière rénovation)
            </div>
            """, unsafe_allow_html=True)

            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("<div class='section-title'>Décomposition des ajustements</div>", unsafe_allow_html=True)
                detail = pd.DataFrame({
                    "Composant": ["Base", "Âge", "Marque", "Condition", "Localisation", "Taux longs", "Prime locale", "TOTAL FINAL"],
                    "bps": [
                        row["CapRate_Base_Bps"], row["Adj_Age_Bps"], row["Adj_Brand_Bps"],
                        row["Adj_Condition_Bps"], row["Adj_Location_Bps"], row["Adj_Taux_Bps"],
                        row["Adj_Prime_Locale_Bps"], row["CapRate_Final_Bps"]
                    ],
                })
                detail["%"] = detail["bps"] / 10000
                st.dataframe(detail.style.format({"bps": "{:+.0f}", "%": "{:.2%}"}), use_container_width=True, hide_index=True)

                st.markdown("<div class='section-title'>Contributions (bps)</div>", unsafe_allow_html=True)
                contrib = pd.DataFrame({
                    "Ajustement": ["Âge", "Marque", "Condition", "Localisation", "Taux", "Prime locale"],
                    "Impact_bps": [row["Adj_Age_Bps"], row["Adj_Brand_Bps"], row["Adj_Condition_Bps"],
                                   row["Adj_Location_Bps"], row["Adj_Taux_Bps"], row["Adj_Prime_Locale_Bps"]],
                }).set_index("Ajustement")
                st.bar_chart(contrib)

            with col_b:
                st.markdown("<div class='section-title'>Sensibilité cap rate → valeur</div>", unsafe_allow_html=True)
                sens_bps = [row["CapRate_Final_Bps"] + d for d in [-150, -75, 0, +75, +150]]
                sens = pd.DataFrame({"Cap Rate (bps)": sens_bps})
                sens["Cap Rate"] = sens["Cap Rate (bps)"] / 10000
                sens["Valeur implicite"] = np.where(sens["Cap Rate"] > 0, noi / sens["Cap Rate"], np.nan)
                sens["Valeur / clé"] = np.where(rooms > 0, sens["Valeur implicite"] / rooms, np.nan)
                sens["vs Base"] = sens["Valeur implicite"] - row["Value_Final"]
                st.dataframe(sens.style.format({
                    "Cap Rate (bps)": "{:.0f}", "Cap Rate": "{:.2%}",
                    "Valeur implicite": lambda x: fmt_eur(x),
                    "Valeur / clé": lambda x: fmt_eur(x),
                    "vs Base": lambda x: fmt_eur(x),
                }), use_container_width=True, hide_index=True)

                display_influence_factors()

            csv = calc.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Télécharger résultats CSV", csv, "cap_rate_results.csv", "text/csv")

    # =====================
    # TAB 2 – Multi-actifs
    # =====================
    with tab2:
        st.markdown("<div class='section-title'>Comparaison multi-actifs</div>", unsafe_allow_html=True)
        st.caption("Configurez jusqu'à 4 actifs pour les comparer côte à côte.")

        nb_assets = st.radio("Nombre d'actifs", [2, 3, 4], horizontal=True)

        asset_configs = []
        cols = st.columns(nb_assets)

        defaults = [
            {"name": "Hotel Alpha", "rooms": 120, "seg": 3, "age": 22, "reno": 2020, "brand": 1, "cond": 2, "loc": 2, "noi": 1_000_000},
            {"name": "Hotel Beta", "rooms": 85, "seg": 1, "age": 8, "reno": 2022, "brand": 0, "cond": 0, "loc": 0, "noi": 2_200_000},
            {"name": "Hotel Gamma", "rooms": 200, "seg": 4, "age": 35, "reno": 2010, "brand": 2, "cond": 3, "loc": 3, "noi": 800_000},
            {"name": "Hotel Delta", "rooms": 160, "seg": 2, "age": 14, "reno": 2019, "brand": 1, "cond": 1, "loc": 1, "noi": 1_500_000},
        ]

        for i, col in enumerate(cols):
            with col:
                d = defaults[i]
                st.markdown(f"**Actif {i+1}**")
                nm = st.text_input("Nom", d["name"], key=f"m{i}_name")
                rm = st.number_input("Chambres", 1, 3000, d["rooms"], key=f"m{i}_rooms")
                sg = st.selectbox("Segment", SEGMENTS, index=d["seg"], key=f"m{i}_seg")
                ag = st.slider("Âge (ans)", 0, 60, d["age"], key=f"m{i}_age")
                rn = st.number_input("Année réno", 1950, current_year, d["reno"], key=f"m{i}_reno")
                br = st.selectbox("Marque", BRANDS, index=d["brand"], key=f"m{i}_brand")
                cd = st.selectbox("Condition", CONDITIONS, index=d["cond"], key=f"m{i}_cond")
                lc = st.selectbox("Localisation", LOCATIONS, index=d["loc"], key=f"m{i}_loc")
                ni = st.number_input("NOI (€)", 0.0, value=float(d["noi"]), step=50_000.0, format="%.0f", key=f"m{i}_noi")
                asset_configs.append((nm, rm, sg, ag, rn, br, cd, lc, ni))

        # Shared market params
        with st.expander("Paramètres marché communs"):
            cm1, cm2, cm3, cm4 = st.columns(4)
            with cm1:
                m_tx = st.slider("Taux 10Y (%)", 0.0, 10.0, 4.25, 0.05, key="m_tx")
            with cm2:
                m_txr = st.slider("Taux 10Y réf (%)", 0.0, 10.0, 4.00, 0.05, key="m_txr")
            with cm3:
                m_elas = st.slider("Élasticité", 0.0, 1.0, 0.25, 0.05, key="m_elas")
            with cm4:
                m_prime = st.slider("Prime locale (bps)", 0, 300, 50, 5, key="m_prime")

        all_rows = []
        for (nm, rm, sg, ag, rn, br, cd, lc, ni) in asset_configs[:nb_assets]:
            inp = build_asset_inputs(nm, rm, sg, ag, rn, br, cd, lc, m_tx, m_txr, m_elas, m_prime, ni)
            res = compute_cap_rate(inp, base_rates, age_table, brand_table, condition_table, location_table)
            all_rows.append(res.iloc[0])

        # Comparison table
        st.markdown("<div class='section-title'>Tableau comparatif</div>", unsafe_allow_html=True)
        comp_table = pd.DataFrame({
            "Actif": [r["Asset_Name"] for r in all_rows],
            "Chambres": [int(r["Rooms"]) for r in all_rows],
            "Segment": [r["Segment"] for r in all_rows],
            "Cap Rate Base": [fmt_pct(r["CapRate_Base"]) for r in all_rows],
            "Ajustement Total": [fmt_bps(r["Adj_Total_Bps"]) for r in all_rows],
            "Cap Rate Final": [fmt_pct(r["CapRate_Final"]) for r in all_rows],
            "NOI": [fmt_eur(r["NOI"]) for r in all_rows],
            "Valeur Implicite": [fmt_eur(r["Value_Final"]) for r in all_rows],
            "Valeur / Clé": [fmt_eur(r["Value_Per_Key"]) for r in all_rows],
        })
        st.dataframe(comp_table, use_container_width=True, hide_index=True)

        # Bar charts comparison
        st.markdown("<div class='section-title'>Comparaison visuelle</div>", unsafe_allow_html=True)
        cc1, cc2, cc3 = st.columns(3)
        names = [r["Asset_Name"] for r in all_rows]

        with cc1:
            chart_cr = pd.DataFrame({"Cap Rate Final (bps)": [r["CapRate_Final_Bps"] for r in all_rows]}, index=names)
            st.caption("Cap Rate Final (bps)")
            st.bar_chart(chart_cr)
        with cc2:
            chart_val = pd.DataFrame({"Valeur (M€)": [r["Value_Final"] / 1e6 for r in all_rows]}, index=names)
            st.caption("Valeur implicite (M€)")
            st.bar_chart(chart_val)
        with cc3:
            chart_key = pd.DataFrame({"€/Clé (k€)": [r["Value_Per_Key"] / 1000 for r in all_rows]}, index=names)
            st.caption("Valeur par clé (k€)")
            st.bar_chart(chart_key)

    # =====================
    # TAB 3 – Scenarios
    # =====================
    with tab3:
        st.markdown("<div class='section-title'>Analyse de scénarios – Optimiste / Base / Pessimiste</div>", unsafe_allow_html=True)
        st.caption("Le scénario Bear applique +150 bps sur le cap rate et -15% sur le NOI. Le scénario Bull applique -100 bps et +15% sur le NOI.")

        sc1, sc2 = st.columns([1, 2])
        with sc1:
            sc_name = st.text_input("Nom de l'actif", "Hotel Référence", key="sc_name")
            sc_rooms = st.number_input("Chambres", 1, 3000, 120, key="sc_rooms")
            sc_seg = st.selectbox("Segment", SEGMENTS, index=3, key="sc_seg")
            sc_age = st.slider("Âge physique", 0, 60, 22, key="sc_age")
            sc_reno = st.number_input("Année rénovation", 1950, current_year, 2020, key="sc_reno")
            sc_brand = st.selectbox("Marque", BRANDS, index=1, key="sc_brand")
            sc_cond = st.selectbox("Condition", CONDITIONS, index=2, key="sc_cond")
            sc_loc = st.selectbox("Localisation", LOCATIONS, index=2, key="sc_loc")
            sc_tx = st.slider("Taux 10Y (%)", 0.0, 10.0, 4.25, 0.05, key="sc_tx")
            sc_txr = st.slider("Taux 10Y réf (%)", 0.0, 10.0, 4.00, 0.05, key="sc_txr")
            sc_elas = st.slider("Élasticité", 0.0, 1.0, 0.25, 0.05, key="sc_elas")
            sc_prime = st.slider("Prime locale (bps)", 0, 300, 50, 5, key="sc_prime")
            sc_noi = st.number_input("NOI stabilisé (€)", 0.0, value=1_000_000.0, step=50_000.0, key="sc_noi")

        with sc2:
            sc_inputs = build_asset_inputs(
                sc_name, sc_rooms, sc_seg, sc_age, sc_reno,
                sc_brand, sc_cond, sc_loc, sc_tx, sc_txr, sc_elas, sc_prime, sc_noi
            )
            sc_calc = compute_cap_rate(sc_inputs, base_rates, age_table, brand_table, condition_table, location_table)
            sc_row = sc_calc.iloc[0]

            scenarios = build_scenarios(sc_row["CapRate_Final_Bps"], sc_noi, sc_rooms)

            # Scenario cards
            for sc_label, sc_data in scenarios.items():
                bg = {"🐻 Bear (stress)": "#fff5f5", "📊 Base": "#f5f8ff", "🐂 Bull (upside)": "#f5fff7"}[sc_label]
                border = {"🐻 Bear (stress)": "#e05c5c", "📊 Base": "#4a7fc1", "🐂 Bull (upside)": "#3aaa6e"}[sc_label]
                st.markdown(f"""
                <div style='background:{bg}; border-left:5px solid {border}; border-radius:10px; padding:1rem 1.4rem; margin-bottom:0.6rem;'>
                <span style='font-size:1.05rem; font-weight:700; color:#1a1a2e;'>{sc_label}</span>
                <table style='width:100%; margin-top:0.5rem; font-size:0.85rem;'>
                <tr>
                    <td style='color:#555;'>Cap Rate</td>
                    <td style='color:#555;'>NOI</td>
                    <td style='color:#555;'>Valeur implicite</td>
                    <td style='color:#555;'>Valeur / clé</td>
                </tr>
                <tr>
                    <td style='font-weight:700; font-size:1.1rem; color:#1a1a2e;'>{sc_data["cap_rate"]:.2%}</td>
                    <td style='font-weight:700; font-size:1.1rem; color:#1a1a2e;'>{fmt_eur(sc_data["noi"])}</td>
                    <td style='font-weight:700; font-size:1.1rem; color:#1a1a2e;'>{fmt_eur(sc_data["value"])}</td>
                    <td style='font-weight:700; font-size:1.1rem; color:#1a1a2e;'>{fmt_eur(sc_data["value_per_key"])}</td>
                </tr>
                </table>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div class='section-title'>Fourchette de valeur</div>", unsafe_allow_html=True)
            sc_vals = pd.DataFrame({
                "Scénario": list(scenarios.keys()),
                "Valeur (M€)": [v["value"] / 1e6 if v["value"] else 0 for v in scenarios.values()],
                "Cap Rate (bps)": [v["cap_rate_bps"] for v in scenarios.values()],
                "NOI (k€)": [v["noi"] / 1000 for v in scenarios.values()],
                "€/Clé": [v["value_per_key"] if v["value_per_key"] else 0 for v in scenarios.values()],
            }).set_index("Scénario")
            st.bar_chart(sc_vals[["Valeur (M€)"]])

            st.dataframe(sc_vals.style.format({
                "Valeur (M€)": "{:.2f}",
                "Cap Rate (bps)": "{:.0f}",
                "NOI (k€)": "{:.0f}",
                "€/Clé": "{:,.0f}",
            }), use_container_width=True)

            # Custom scenario
            st.markdown("<div class='section-title'>Scénario personnalisé</div>", unsafe_allow_html=True)
            cu1, cu2 = st.columns(2)
            with cu1:
                custom_delta_bps = st.slider("Δ Cap Rate vs Base (bps)", -200, 300, 0, 25, key="sc_custom_bps")
            with cu2:
                custom_noi_mult = st.slider("Multiplicateur NOI", 0.5, 1.5, 1.0, 0.05, key="sc_custom_noi")
            custom_cr = max((sc_row["CapRate_Final_Bps"] + custom_delta_bps) / 10000, 0.01)
            custom_noi = sc_noi * custom_noi_mult
            custom_val = custom_noi / custom_cr
            cv1, cv2, cv3 = st.columns(3)
            cv1.metric("Cap Rate personnalisé", f"{custom_cr:.2%}")
            cv2.metric("Valeur", fmt_eur(custom_val))
            cv3.metric("€/Clé", fmt_eur(custom_val / sc_rooms if sc_rooms > 0 else None))

    # =====================
    # TAB 4 – Market benchmarks
    # =====================
    with tab4:
        st.markdown("<div class='section-title'>Benchmarks de marché – Cap rates par ville</div>", unsafe_allow_html=True)

        pays_filter = st.multiselect("Filtrer par pays", sorted(market_benchmarks["Pays"].unique()), default=sorted(market_benchmarks["Pays"].unique()))
        bm_filtered = market_benchmarks[market_benchmarks["Pays"].isin(pays_filter)]

        bm_filtered = bm_filtered.copy()
        bm_filtered["Cap Rate Mid (bps)"] = (bm_filtered["Cap_Rate_Min_Bps"] + bm_filtered["Cap_Rate_Max_Bps"]) / 2
        bm_filtered["Fourchette"] = bm_filtered.apply(lambda r: f"{r['Cap_Rate_Min_Bps']:.0f} – {r['Cap_Rate_Max_Bps']:.0f} bps", axis=1)
        bm_filtered["Cap Rate Min"] = bm_filtered["Cap_Rate_Min_Bps"] / 10000
        bm_filtered["Cap Rate Max"] = bm_filtered["Cap_Rate_Max_Bps"] / 10000
        bm_filtered["Cap Rate Mid"] = bm_filtered["Cap Rate Mid (bps)"] / 10000

        bm_display = bm_filtered[["Marché", "Pays", "Fourchette", "Cap Rate Mid", "RevPAR_Ref_EUR", "Tendance"]].copy()
        bm_display.columns = ["Marché", "Pays", "Fourchette (bps)", "Cap Rate Mid", "RevPAR Réf. (€)", "Tendance"]

        def color_tendance(val):
            if "↑" in val:
                return "color: #3aaa6e; font-weight:600"
            elif "↓" in val:
                return "color: #e05c5c; font-weight:600"
            return "color: #555"

        st.dataframe(
            bm_display.style
                .format({"Cap Rate Mid": "{:.2%}", "RevPAR Réf. (€)": "€ {:.0f}"})
                .map(color_tendance, subset=["Tendance"]),
            use_container_width=True, hide_index=True
        )

        st.markdown("<div class='section-title'>Cap Rate Mid par marché</div>", unsafe_allow_html=True)
        chart_bm = bm_filtered.set_index("Marché")[["Cap Rate Mid (bps)"]].sort_values("Cap Rate Mid (bps)")
        st.bar_chart(chart_bm)

        st.markdown("<div class='section-title'>RevPAR de référence par marché</div>", unsafe_allow_html=True)
        chart_revpar = bm_filtered.set_index("Marché")[["RevPAR_Ref_EUR"]].sort_values("RevPAR_Ref_EUR", ascending=False)
        st.bar_chart(chart_revpar)

        # Position your asset vs market
        st.markdown("<div class='section-title'>Positionner votre actif sur le benchmark</div>", unsafe_allow_html=True)
        pb1, pb2 = st.columns(2)
        with pb1:
            your_cap_rate_bps = st.number_input("Cap rate de votre actif (bps)", 300, 2000, 950, 10, key="bm_cr")
        with pb2:
            ref_market = st.selectbox("Marché de référence", bm_filtered["Marché"].tolist(), key="bm_mkt")
        ref_row = bm_filtered[bm_filtered["Marché"] == ref_market].iloc[0]
        delta_min = your_cap_rate_bps - ref_row["Cap_Rate_Min_Bps"]
        delta_max = your_cap_rate_bps - ref_row["Cap_Rate_Max_Bps"]
        if your_cap_rate_bps < ref_row["Cap_Rate_Min_Bps"]:
            position = f"⚠️ Sous la fourchette basse du marché ({ref_row['Cap_Rate_Min_Bps']:.0f} bps) – potentiel de compression ou actif premium"
        elif your_cap_rate_bps > ref_row["Cap_Rate_Max_Bps"]:
            position = f"⚠️ Au-dessus de la fourchette haute ({ref_row['Cap_Rate_Max_Bps']:.0f} bps) – actif décôté ou risque plus élevé"
        else:
            position = f"✅ Dans la fourchette de marché [{ref_row['Cap_Rate_Min_Bps']:.0f} – {ref_row['Cap_Rate_Max_Bps']:.0f} bps]"
        st.markdown(f"""
        <div class='highlight-box'>
        <strong>{ref_market}</strong> → Fourchette benchmark : {ref_row['Fourchette']} · Tendance : {ref_row['Tendance']}<br>
        Votre actif à <strong>{your_cap_rate_bps:.0f} bps</strong> : {position}<br>
        Écart vs min : {delta_min:+.0f} bps · Écart vs max : {delta_max:+.0f} bps
        </div>
        """, unsafe_allow_html=True)

    # =====================
    # TAB 5 – Comparables
    # =====================
    with tab5:
        st.markdown("<div class='section-title'>Base de comparables – Transactions fictives</div>", unsafe_allow_html=True)
        st.info("📌 Ces comparables sont entièrement fictifs et générés à titre illustratif. En pratique, ils seraient issus de bases de données de transactions (JLL, CBRE, Cushman, etc.).")

        filt1, filt2 = st.columns(2)
        with filt1:
            pays_comp = st.multiselect("Pays", sorted(comparables["Pays"].unique()), default=sorted(comparables["Pays"].unique()), key="comp_pays")
        with filt2:
            seg_comp = st.multiselect("Segment", comparables["Segment"].unique(), default=list(comparables["Segment"].unique()), key="comp_seg")

        comp_f = comparables[(comparables["Pays"].isin(pays_comp)) & (comparables["Segment"].isin(seg_comp))].copy()

        # Cards view
        st.markdown("<div class='section-title'>Fiches comparables</div>", unsafe_allow_html=True)
        card_cols = st.columns(3)
        for idx, (_, comp_row) in enumerate(comp_f.iterrows()):
            with card_cols[idx % 3]:
                st.markdown(f"""
                <div class='comparable-card'>
                <div class='comp-name'>{comp_row['Nom']} <span class='comp-tag'>{comp_row['Source']}</span></div>
                <div style='color:#888; font-size:0.78rem; margin-top:2px;'>{comp_row['Ville']} · {comp_row['Pays']} · {comp_row['Année']}</div>
                <div style='margin-top:0.5rem;'>
                    <span style='color:#1a1a2e; font-weight:600;'>{comp_row['CapRate_Bps']:.0f} bps</span>
                    <span style='color:#888; font-size:0.8rem; margin-left:6px;'>cap rate</span>
                </div>
                <div style='margin-top:2px;'>
                    <span style='font-weight:500;'>{comp_row['Prix_M_EUR']:.1f} M€</span>
                    <span style='color:#888; font-size:0.8rem; margin-left:4px;'>·</span>
                    <span style='color:#555; font-size:0.82rem; margin-left:4px;'>{comp_row['Prix_Par_Cle_K_EUR']:.0f} k€/clé</span>
                    <span style='color:#888; font-size:0.78rem; margin-left:4px;'>({comp_row['Rooms']} ch.)</span>
                </div>
                <div style='margin-top:3px; color:#888; font-size:0.78rem;'>{comp_row['Segment']}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Tableau récapitulatif</div>", unsafe_allow_html=True)
        comp_display = comp_f[["Nom", "Ville", "Pays", "Segment", "Rooms", "CapRate_Bps", "Prix_M_EUR", "Prix_Par_Cle_K_EUR", "Année", "Source"]].copy()
        comp_display.columns = ["Nom", "Ville", "Pays", "Segment", "Chambres", "Cap Rate (bps)", "Prix (M€)", "Prix/Clé (k€)", "Année", "Source"]
        st.dataframe(comp_display.style.format({
            "Cap Rate (bps)": "{:.0f}", "Prix (M€)": "{:.1f}", "Prix/Clé (k€)": "{:.0f}",
        }), use_container_width=True, hide_index=True)

        st.markdown("<div class='section-title'>Statistiques des comparables sélectionnés</div>", unsafe_allow_html=True)
        if not comp_f.empty:
            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Nb comparables", len(comp_f))
            s2.metric("Cap Rate médian", f"{comp_f['CapRate_Bps'].median():.0f} bps")
            s3.metric("Cap Rate moyen", f"{comp_f['CapRate_Bps'].mean():.0f} bps")
            s4.metric("Prix/Clé médian", f"{comp_f['Prix_Par_Cle_K_EUR'].median():.0f} k€")
            s5.metric("Prix médian", f"{comp_f['Prix_M_EUR'].median():.1f} M€")

        # Position actif vs comparables
        st.markdown("<div class='section-title'>Positionner votre actif vs comparables</div>", unsafe_allow_html=True)
        user_cr_bps = st.number_input("Cap rate actif analysé (bps)", 300, 2000, 950, 10, key="comp_user_cr")
        if not comp_f.empty:
            pct_rank = (comp_f["CapRate_Bps"] < user_cr_bps).mean() * 100
            q1 = comp_f["CapRate_Bps"].quantile(0.25)
            q3 = comp_f["CapRate_Bps"].quantile(0.75)
            st.markdown(f"""
            <div class='highlight-box'>
            Sur {len(comp_f)} comparable(s) · Q1 = {q1:.0f} bps · Médiane = {comp_f['CapRate_Bps'].median():.0f} bps · Q3 = {q3:.0f} bps<br>
            Votre actif à <strong>{user_cr_bps:.0f} bps</strong> se situe au-dessus de <strong>{pct_rank:.0f}%</strong> des comparables
            ({"actif moins cher que la médiane" if user_cr_bps > comp_f['CapRate_Bps'].median() else "actif plus cher que la médiane"}).
            </div>
            """, unsafe_allow_html=True)

        # Distribution
        st.markdown("<div class='section-title'>Distribution cap rates – comparables</div>", unsafe_allow_html=True)
        dist_chart = comp_f[["Nom", "CapRate_Bps"]].set_index("Nom").sort_values("CapRate_Bps")
        st.bar_chart(dist_chart)


if __name__ == "__main__":
    main()
