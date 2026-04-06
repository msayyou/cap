# cap_rate_builder_app.py
# Run with: streamlit run cap_rate_builder_app.py

import streamlit as st
import pandas as pd
import numpy as np


# =========================
# Constants / Configuration
# =========================

# Base cap rates by hotel segment (market-level defaults; easy to override)
BASE_RATES = pd.DataFrame({
    "Segment": [
        "Luxury / Upper-Upscale",
        "Upscale / Full-Service",
        "Limited-Service récent",
        "Limited-Service standard",
        "Limited-Service ancien",
    ],
    "CapRate_Base": [0.075, 0.080, 0.085, 0.095, 0.105],
})

# Age adjustment table (years elapsed or since major reno; interval-based)
AGE_ADJUSTMENT_TABLE = pd.DataFrame({
    "Age_Min": [0, 6, 16, 26],
    "Age_Max": [5, 15, 25, 200],
    "Adj_Age": [-0.0075, 0.0025, 0.0100, 0.0200],
})

# Brand / operator strength adjustment
BRAND_ADJUSTMENT_TABLE = pd.DataFrame({
    "Brand_Class": ["Premium", "Midscale", "Economy", "Indépendant"],
    "Adj_Brand": [-0.0050, 0.0000, 0.0150, 0.0250],
})

# Condition / renovation status adjustment
CONDITION_ADJUSTMENT_TABLE = pd.DataFrame({
    "Condition": ["Rénové <3 ans", "Standard", "Non rénové", "Mauvais état"],
    "Adj_Condition": [-0.0075, 0.0000, 0.0125, 0.0250],
})

# Location quality adjustment
LOCATION_ADJUSTMENT_TABLE = pd.DataFrame({
    "Location_Class": ["Primaire", "Secondaire", "Tertiaire", "Autoroute / rural"],
    "Adj_Location": [-0.0075, 0.0000, 0.0150, 0.0250],
})

# Sensitivity: how much cap rates move relative to long-term rates (empirical relationship)
DEFAULT_ELASTICITY = 0.25
DEFAULT_TEN_YEAR_TREASURY = 0.0425
DEFAULT_TEN_YEAR_REFERENCE = 0.0400

# Local risk premium interpretation (bps => decimal, e.g., 50 bps = 0.005)
DEFAULT_LOCAL_RISK_PREMIUM = 0.005  # 50 bps


# =========================
# Mapping / Lookup Helpers
# =========================

def lookup_interval_adjustment(value: int, table: pd.DataFrame) -> float:
    """
    Find adjustment from an interval table (Age_Min <= value <= Age_Max).
    Returns the corresponding adjustment column value, or 0.0 if no match found.
    """
    if table.empty or len(table.columns) < 3:
        raise ValueError("Interval table must have 'Age_Min', 'Age_Max', and an adjustment column.")
    
    # Determine adjustment column (assumes a single adjustment column present)
    adj_col = [col for col in table.columns if col.startswith("Adj_")][0]
    
    match = table.loc[(table["Age_Min"] <= value) & (table["Age_Max"] >= value)]
    if match.empty:
        # Fallback: logarithmic-like approximation or conservative 0.0
        return 0.0
    return float(match.iloc[0][adj_col])


def lookup_category_adjustment(value: str, table: pd.DataFrame, category_col: str) -> float:
    """
    Find adjustment from a category table (exact match on category_col).
    Returns the corresponding adjustment, or 0.0 if no match found.
    """
    if table.empty or category_col not in table.columns:
        raise ValueError(f"Category table must include column '{category_col}' and an adjustment column.")
    
    adj_col = [col for col in table.columns if col.startswith("Adj_")][0]
    match = table.loc[table[category_col] == value]
    if match.empty:
        # Fallback: 0.0 (neutral) if unknown category
        return 0.0
    return float(match.iloc[0][adj_col])


# =========================
# Core Cap Rate Computation
# =========================

def compute_cap_rate(
    inputs: pd.DataFrame,
    base_rates_table: pd.DataFrame = BASE_RATES,
    age_table: pd.DataFrame = AGE_ADJUSTMENT_TABLE,
    brand_table: pd.DataFrame = BRAND_ADJUSTMENT_TABLE,
    condition_table: pd.DataFrame = CONDITION_ADJUSTMENT_TABLE,
    location_table: pd.DataFrame = LOCATION_ADJUSTMENT_TABLE,
) -> pd.DataFrame:
    """
    Computes the final cap rate for one or more hotel assets given:
    - Segment (base)
    - Age of hotel and/or since renovation
    - Brand class (Premium / Midscale / Economy / Independent)
    - Condition (renovation status)
    - Location quality (primary/secondary/tertiary/rural)
    - Long-term Treasury rates (current + reference) and sensitivity
    - Local risk premium

    Returns a DataFrame with:
    - base cap rate
    - all adjustment components (+ rate sensitivity)
    - total adjustment
    - final cap rate
    - full breakdown for auditability
    """
    
    # Basic validation: required columns
    required_cols = [
        "Asset_Name", "Segment", "Age", "Brand_Class", "Condition", "Location_Class",
        "Taux10Y", "Taux10Y_Ref", "Elasticite", "Prime_Risque_Locale",
    ]
    missing = [c for c in required_cols if c not in inputs.columns]
    if missing:
        raise ValueError(f"Missing required input columns: {missing}")
    
    # Join the base cap rate by Segment
    df = inputs.merge(base_rates_table, on="Segment", how="left")
    if df["CapRate_Base"].isna().any():
        unknown_segments = df.loc[df["CapRate_Base"].isna(), "Segment"].unique().tolist()
        raise ValueError(
            f"Unknown Segment(s) found: {unknown_segments}. Update BASE_RATES with those segments."
        )
    
    # Compute qualitative adjustments (safe, interval/category mapping)
    df["Adj_Age"] = df["Age"].apply(
        lambda x: lookup_interval_adjustment(x, age_table)
    )
    df["Adj_Brand"] = df["Brand_Class"].apply(
        lambda x: lookup_category_adjustment(x, brand_table, "Brand_Class")
    )
    df["Adj_Condition"] = df["Condition"].apply(
        lambda x: lookup_category_adjustment(x, condition_table, "Condition")
    )
    df["Adj_Location"] = df["Location_Class"].apply(
        lambda x: lookup_category_adjustment(x, location_table, "Location_Class")
    )
    
    # Rate sensitivity adjustment (proxy: cap rate reaction to long-term rates)
    # Captures the simple heuristic: if current 10Y is n bp above reference, cap rate up by n*elasticity
    df["Adj_Taux"] = (df["Taux10Y"] - df["Taux10Y_Ref"]) * df["Elasticite"]
    # Ensure Adj_Taux is not NaN (in case elasticities or rates are missing)
    df["Adj_Taux"] = df["Adj_Taux"].fillna(0.0)
    
    # Local risk premium (bps -> decimal)
    df["Prime_Risque_Locale"] = df["Prime_Risque_Locale"].clip(lower=0.0)  # ensure non-negative
    
    # Compute final cap rate and total adjustments
    df["CapRate_Final"] = (
        df["CapRate_Base"]
        + df["Adj_Age"]
        + df["Adj_Brand"]
        + df["Adj_Condition"]
        + df["Adj_Location"]
        + df["Adj_Taux"]
        + df["Prime_Risque_Locale"]
    )
    
    df["Adj_Total"] = (
        df["Adj_Age"]
        + df["Adj_Brand"]
        + df["Adj_Condition"]
        + df["Adj_Location"]
        + df["Adj_Taux"]
        + df["Prime_Risque_Locale"]
    )
    
    # Optional: sanity checks (helps catch inputs that may break underwriting logic)
    valid_capcheck = (df["CapRate_Final"] >= 0.04) & (df["CapRate_Final"] <= 0.15)  # 4–15% range guide
    if (~valid_capcheck).any():
        st.warning(
            "Some cap rates are outside the typical 4–15% range (check segment, condition, rates, and risk premium)."
        )
    
    return df


# =========================
# Streamlit App
# =========================

def main():
    st.set_page_config(page_title="Cap Rate Builder – Hotel Investment", layout="wide")
    st.title("Cap Rate Builder – Hotel Investment Tool")
    st.markdown(
        "An interactive underwriting assistant to estimate hotel cap rates by combining (a) segment-level baseline rates, "
        "(b) qualitative adjustments (age, brand, condition, location), (c) long‑term rate sensitivity, and (d) local risk premiums."
    )
    
    # Sidebar (inputs)
    with st.sidebar:
        st.header("Asset & Market Parameters")
        
        asset_name = st.text_input("Asset name", placeholder="Hotel A", help="For reporting and export")
        
        segment = st.selectbox(
            "Segment",
            options=BASE_RATES["Segment"].tolist(),
            index=3,
            help="Defines the base cap rate for the hotel type (base reference point)",
        )
        
        age = st.slider(
            "Age of the hotel (years since construction or since major renovation)",
            min_value=0,
            max_value=60,
            value=22,
            help="Older hotels typically require higher cap rates unless recently renovated",
        )
        
        brand_class = st.selectbox(
            "Brand class / operator strength",
            options=["Premium", "Midscale", "Economy", "Indépendant"],
            index=1,
            help="Strong brands generally reduce risk and compress the cap rate",
        )
        
        condition = st.selectbox(
            "Condition / renovation status",
            options=["Rénové <3 ans", "Standard", "Non rénové", "Mauvais état"],
            index=2,
            help="Renovated hotels (and particularly recent ones) receive a tighter rate",
        )
        
        location_class = st.selectbox(
            "Location quality",
            options=["Primaire", "Secondaire", "Tertiaire", "Autoroute / rural"],
            index=2,
            help="Higher footfall and trade-area strength reduce cap rates",
        )
        
        taux10y = st.slider(
            "10Y Treasury (current)",
            min_value=0.0,
            max_value=0.08,
            value=DEFAULT_TEN_YEAR_TREASURY,
            step=0.0025,
            format="%.3f",
            help="Market long-term risk-free reference to proxy financing and investment hurdle rates",
        )
        
        taux10y_ref = st.slider(
            "10Y Treasury (reference / baseline)",
            min_value=0.0,
            max_value=0.08,
            value=DEFAULT_TEN_YEAR_REFERENCE,
            step=0.0025,
            format="%.3f",
            help="A reference period (e.g., long-term average) to create a spread-based adjustment",
        )
        
        elasticite = st.slider(
            "Cap rate elasticity vs long-term rates",
            min_value=0.0,
            max_value=1.0,
            value=DEFAULT_ELASTICITY,
            step=0.05,
            help="How much the cap rate moves per unit change in long-term rates: 0.25 ≈ 25 bps per 100 bps shift",
        )
        
        prime_locale = st.slider(
            "Local risk premium (bps)",
            min_value=0.0,
            max_value=0.03,
            value=DEFAULT_LOCAL_RISK_PREMIUM,
            step=0.001,
            format="%.3f",
            help="Additional spread due to local market risk (regulatory, supply risk, demand volatility, etc.)",
        )
        
        st.caption("Note: All numerical inputs map to decimals (e.g., 7.5% = 0.075)")
    
    # Build input DataFrame (can easily be expanded to multiple assets if needed)
    inputs_df = pd.DataFrame({
        "Asset_Name": [asset_name or "Hotel A"],
        "Segment": [segment],
        "Age": [age],
        "Brand_Class": [brand_class],
        "Condition": [condition],
        "Location_Class": [location_class],
        "Taux10Y": [taux10y],
        "Taux10Y_Ref": [taux10y_ref],
        "Elasticite": [elasticite],
        "Prime_Risque_Locale": [prime_locale],
    })
    
    # Compute cap rate
    try:
        calc_df = compute_cap_rate(inputs_df)
    except ValueError as e:
        st.error(f"Input error: {e}")
        st.stop()
    
    # Main content area
    row = calc_df.iloc[0]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Summary – Underwriting View")
        
        st.metric("Base cap rate (segment)", f"{row['CapRate_Base']:.2%}")
        st.metric("Final cap rate (estimated)", f"{row['CapRate_Final']:.2%}")
        st.metric("Total adjustments vs base", f"{row['Adj_Total']:.2%}")
        
        st.write("**Adjustment breakdown** (audit trail):")
        detail = pd.DataFrame({
            "Component": [
                "Base (Segment)",
                "Age",
                "Brand / Operator",
                "Condition / Renovation",
                "Location",
                "Long-term rates (spread × elasticity)",
                "Local risk premium",
                "Final cap rate",
            ],
            "Value": [
                row["CapRate_Base"],
                row["Adj_Age"],
                row["Adj_Brand"],
                row["Adj_Condition"],
                row["Adj_Location"],
                row["Adj_Taux"],
                row["Prime_Risque_Locale"],
                row["CapRate_Final"],
            ],
        })
        st.dataframe(
            detail.style.format({"Value": "{:.2%}"}),
            use_container_width=True,
            hide_index=True,
        )
    
    with col2:
        st.subheader("Base vs Final")
        comp = pd.DataFrame({
            "Type": ["Base", "Final"],
            "CapRate": [row["CapRate_Base"], row["CapRate_Final"]],
        }).set_index("Type")
        st.bar_chart(comp)
        
        st.subheader("Adjustment waterflow (simplified)")
        steps = pd.DataFrame({
            "Step": ["Base", "Age", "Brand", "Condition", "Location", "Rates", "Local Risk"],
            "Delta": [
                0.0,
                row["Adj_Age"],
                row["Adj_Brand"],
                row["Adj_Condition"],
                row["Adj_Location"],
                row["Adj_Taux"],
                row["Prime_Risque_Locale"],
            ],
        })
        steps["Cumulative"] = row["CapRate_Base"] + steps["Delta"].cumsum()
        st.line_chart(steps.set_index("Step")[["Cumulative"]])
    
    # Full result data
    st.subheader("Complete input & result data")
    st.dataframe(
        calc_df.style.format({
            "CapRate_Base": "{:.2%}",
            "CapRate_Final": "{:.2%}",
            "Adj_Age": "{:.2%}",
            "Adj_Brand": "{:.2%}",
            "Adj_Condition": "{:.2%}",
            "Adj_Location": "{:.2%}",
            "Adj_Taux": "{:.2%}",
            "Prime_Risque_Locale": "{:.2%}",
            "Adj_Total": "{:.2%}",
            "Taux10Y": "{:.3f}",
            "Taux10Y_Ref": "{:.3f}",
        }),
        use_container_width=True
    )
    
    # Export
    csv = calc_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download results (CSV)",
        data=csv,
        file_name="cap_rate_builder_results.csv",
        mime="text/csv",
    )
    
    # Notes to the user (helpful documentation without taking full screen space)
    st.info(
        "**Methodology reminder:** Adjustments are intended to be conservative, underwriting-grade proxies (not a market-clearing mechanism). "
        "They should be calibrated on your market’s transactions and may differ significantly by geography, operator, and financing criteria. "
        "Sensitivity review (scenarios + elasticity tuning) is recommended before using this for acquisition or appraisal decisions."
    )


if __name__ == "__main__":
    main()
