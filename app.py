# cap_rate_builder_app.py
# Lance avec : streamlit run cap_rate_builder_app.py


import streamlit as st
import pandas as pd
import numpy as np


# =========================
# Formatting helpers
# =========================
def fmt_pct(x):
    return f"{x:.2%}" if pd.notna(x) else "N/A"

def fmt_bps(x):
    return f"{x:+.0f} bps" if pd.notna(x) else "N/A"

def fmt_eur(x):
    if pd.isna(x):
        return "N/A"
    return f"€ {x:,.0f}".replace(",", " ").replace(".", ",")


# =========================
# Base rates & adjustments
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
    df["Adj_Brand_Bps"] = df["Brand_Class"].apply(
        lambda x: map_exact_adjustment(x, brand_table, "Brand_Class", "Adj_Brand_Bps")
    )
    df["Adj_Condition_Bps"] = df["Condition"].apply(
        lambda x: map_exact_adjustment(x, condition_table, "Condition", "Adj_Condition_Bps")
    )
    df["Adj_Location_Bps"] = df["Location_Class"].apply(
        lambda x: map_exact_adjustment(x, location_table, "Location_Class", "Adj_Location_Bps")
    )

    # Taux longs : l’écart de taux est converti en bps via l’élasticité
    df["Adj_Taux_Bps"] = (df["Taux10Y"] - df["Taux10Y_Ref"]) * df["Elasticite"] * 10000

    # Prime locale déjà saisie en bps
    df["Adj_Prime_Locale_Bps"] = df["Prime_Risque_Locale_Bps"]

    df["Adj_Total_Bps"] = (
        df["Adj_Age_Bps"]
        + df["Adj_Brand_Bps"]
        + df["Adj_Condition_Bps"]
        + df["Adj_Location_Bps"]
        + df["Adj_Taux_Bps"]
        + df["Adj_Prime_Locale_Bps"]
    )

    df["CapRate_Final_Bps"] = (df["CapRate_Base_Bps"] + df["Adj_Total_Bps"]).clip(lower=0)

    df["CapRate_Base"] = df["CapRate_Base_Bps"] / 10000
    df["CapRate_Final"] = df["CapRate_Final_Bps"] / 10000

    # Valeur implicite = NOI / cap rate
    df["Value_Base"] = np.where(df["CapRate_Base"] > 0, df["NOI"] / df["CapRate_Base"], np.nan)
    df["Value_Final"] = np.where(df["CapRate_Final"] > 0, df["NOI"] / df["CapRate_Final"], np.nan)
    df["Value_Delta"] = df["Value_Final"] - df["Value_Base"]
    df["Value_Per_Key"] = np.where(df["Rooms"] > 0, df["Value_Final"] / df["Rooms"], np.nan)

    return df


# =========================
# Streamlit app
# =========================
def main():
    st.set_page_config(page_title="Cap Rate Builder", layout="wide")
    st.title("Cap Rate Builder – Hotel Investment")
    st.caption(
        "Outil simplifié d’estimation de cap rate pour un hôtel. "
        "À calibrer avec des comparables de marché, la structure de management, le PIP, et les réserves FF&E."
    )

    base_rates = build_base_rates()
    age_table, brand_table, condition_table, location_table = build_adjustment_tables()
    current_year = pd.Timestamp.today().year

    # -------------------------
    # Sidebar inputs
    # -------------------------
    st.sidebar.header("Paramètres de l’actif")

    asset_name = st.sidebar.text_input("Nom de l’actif", "Hotel A")
    rooms = st.sidebar.number_input(
        "Nombre de chambres / clés",
        min_value=1,
        max_value=3000,
        value=120,
        step=1,
    )

    segment = st.sidebar.selectbox(
        "Segment",
        base_rates["Segment"].tolist(),
        index=3,
    )

    age_physical = st.sidebar.slider("Âge physique de l’hôtel (années)", 0, 60, 22)
    year_last_reno = st.sidebar.number_input(
        "Année de dernière rénovation",
        min_value=1950,
        max_value=current_year,
        value=2020,
        step=1,
    )

    years_since_reno = max(0, current_year - int(year_last_reno))
    age_for_adjustment = min(age_physical, years_since_reno) if years_since_reno > 0 else age_physical

    brand_class = st.sidebar.selectbox(
        "Classe de marque",
        ["Premium", "Midscale", "Economy", "Indépendant"],
        index=1,
    )

    condition = st.sidebar.selectbox(
        "Condition",
        ["Rénové <3 ans", "Standard", "Non rénové", "Mauvais état"],
        index=2,
    )

    location_class = st.sidebar.selectbox(
        "Localisation",
        ["Primaire", "Secondaire", "Tertiaire", "Autoroute / rural"],
        index=2,
    )

    st.sidebar.header("Marché & rendement")

    taux10y_pct = st.sidebar.slider("Taux 10Y actuel (%)", 0.0, 10.0, 4.25, step=0.05)
    taux10y_ref_pct = st.sidebar.slider("Taux 10Y de référence (%)", 0.0, 10.0, 4.00, step=0.05)
    elasticite = st.sidebar.slider("Élasticité cap rate / taux longs", 0.0, 1.0, 0.25, step=0.05)
    prime_locale_bps = st.sidebar.slider("Prime de risque locale (bps)", 0, 300, 50, step=5)

    noi = st.sidebar.number_input(
        "NOI annuel stabilisé (€)",
        min_value=0.0,
        value=1_000_000.0,
        step=50_000.0,
        format="%.0f",
    )

    # -------------------------
    # Inputs dataframe
    # -------------------------
    inputs_df = pd.DataFrame({
        "Asset_Name": [asset_name],
        "Rooms": [rooms],
        "Segment": [segment],
        "Age_Physical": [age_physical],
        "Year_Last_Reno": [int(year_last_reno)],
        "Years_Since_Reno": [years_since_reno],
        "Age_For_Adjustment": [age_for_adjustment],
        "Brand_Class": [brand_class],
        "Condition": [condition],
        "Location_Class": [location_class],
        "Taux10Y": [taux10y_pct / 100],
        "Taux10Y_Ref": [taux10y_ref_pct / 100],
        "Elasticite": [elasticite],
        "Prime_Risque_Locale_Bps": [prime_locale_bps],
        "NOI": [noi],
    })

    calc_df = compute_cap_rate(
        inputs_df,
        base_rates,
        age_table,
        brand_table,
        condition_table,
        location_table,
    )

    row = calc_df.iloc[0]

    # -------------------------
    # Top metrics
    # -------------------------
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("Cap rate de base", fmt_pct(row["CapRate_Base"]))
    with c2:
        st.metric("Cap rate final", fmt_pct(row["CapRate_Final"]), fmt_bps(row["Adj_Total_Bps"]))
    with c3:
        st.metric("Valeur implicite", fmt_eur(row["Value_Final"]))
    with c4:
        st.metric("Valeur / clé", fmt_eur(row["Value_Per_Key"]))
    with c5:
        st.metric("Delta valeur vs base", fmt_eur(row["Value_Delta"]))

    st.info(
        f"Âge retenu pour l’ajustement : {age_for_adjustment} ans "
        f"(âge physique {age_physical} ans, {years_since_reno} ans depuis la dernière rénovation)."
    )

    # -------------------------
    # Charts and tables
    # -------------------------
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Détail des ajustements")

        detail = pd.DataFrame({
            "Composant": [
                "Base",
                "Âge",
                "Marque",
                "Condition",
                "Localisation",
                "Taux longs",
                "Prime locale",
                "Final",
            ],
            "bps": [
                row["CapRate_Base_Bps"],
                row["Adj_Age_Bps"],
                row["Adj_Brand_Bps"],
                row["Adj_Condition_Bps"],
                row["Adj_Location_Bps"],
                row["Adj_Taux_Bps"],
                row["Adj_Prime_Locale_Bps"],
                row["CapRate_Final_Bps"],
            ],
        })
        detail["%"] = detail["bps"] / 10000

        st.dataframe(
            detail.style.format({
                "bps": "{:.0f}",
                "%": "{:.2%}",
            }),
            use_container_width=True,
        )

        st.subheader("Contribution des ajustements")
        contrib = pd.DataFrame({
            "Ajustement": ["Âge", "Marque", "Condition", "Localisation", "Taux", "Prime locale"],
            "Impact_bps": [
                row["Adj_Age_Bps"],
                row["Adj_Brand_Bps"],
                row["Adj_Condition_Bps"],
                row["Adj_Location_Bps"],
                row["Adj_Taux_Bps"],
                row["Adj_Prime_Locale_Bps"],
            ],
        }).set_index("Ajustement")

        st.bar_chart(contrib)

    with colB:
        st.subheader("Sensibilité à la valeur")

        sensitivity_bps = [
            row["CapRate_Final_Bps"] - 100,
            row["CapRate_Final_Bps"] - 50,
            row["CapRate_Final_Bps"],
            row["CapRate_Final_Bps"] + 50,
            row["CapRate_Final_Bps"] + 100,
        ]

        sens = pd.DataFrame({"Cap Rate (bps)": sensitivity_bps})
        sens["Cap Rate"] = sens["Cap Rate (bps)"] / 10000
        sens["Valeur implicite"] = np.where(sens["Cap Rate"] > 0, noi / sens["Cap Rate"], np.nan)
        sens["Valeur / clé"] = np.where(rooms > 0, sens["Valeur implicite"] / rooms, np.nan)

        st.dataframe(
            sens.style.format({
                "Cap Rate (bps)": "{:.0f}",
                "Cap Rate": "{:.2%}",
                "Valeur implicite": lambda x: fmt_eur(x),
                "Valeur / clé": lambda x: fmt_eur(x),
            }),
            use_container_width=True,
        )

        st.subheader("Hypothèses clés")
        assumptions = pd.DataFrame({
            "Variable": [
                "Segment",
                "Âge physique",
                "Année dernière rénovation",
                "Classe de marque",
                "Condition",
                "Localisation",
                "Taux 10Y actuel",
                "Taux 10Y de référence",
                "Élasticité",
                "Prime locale",
            ],
            "Valeur": [
                segment,
                age_physical,
                year_last_reno,
                brand_class,
                condition,
                location_class,
                f"{taux10y_pct:.2f}%",
                f"{taux10y_ref_pct:.2f}%",
                elasticite,
                f"{prime_locale_bps} bps",
            ],
        })
        st.dataframe(assumptions, use_container_width=True)

    st.subheader("Données complètes")
    st.dataframe(calc_df, use_container_width=True)

    csv = calc_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Télécharger les résultats en CSV",
        data=csv,
        file_name="cap_rate_builder_results.csv",
        mime="text/csv",
    )

    with st.expander("Notes d’interprétation"):
        st.write(
            "- Le modèle est volontairement simple : il sert à structurer une opinion de cap rate.\n"
            "- Pour un hôtel, les variables de underwriting les plus importantes sont souvent : ADR, Occupancy, RevPAR, GOP, frais de management, franchise fees, réserve FF&E, et CAPEX/PIP.\n"
            "- Les tables de base sont indicatives : idéalement, elles doivent être recalibrées avec des transactions comparables et des données de marché locales."
        )


if __name__ == "__main__":
    main()
