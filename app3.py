# cap_rate_builder_app_v2.py
# Lance avec : streamlit run cap_rate_builder_app_v2.py

import streamlit as st
import pandas as pd
import numpy as np

# =========================
# Initialisation de l'état de la session
# =========================
def initialize_session_state():
    if 'initialized' in st.session_state:
        return

    # Tables de base (seront modifiables par l'utilisateur)
    st.session_state.base_rates_df = pd.DataFrame({
        "Segment": ["Luxury / Upper-Upscale", "Upscale / Full-Service", "Limited-Service récent", "Limited-Service standard", "Limited-Service ancien"],
        "CapRate_Base_Bps": [750, 800, 850, 950, 1050],
    })
    st.session_state.age_adj_df = pd.DataFrame({
        "Age_Min": [0, 6, 16, 26], "Age_Max": [5, 15, 25, 200], "Adj_Age_Bps": [-75, 25, 100, 200],
    })
    st.session_state.brand_adj_df = pd.DataFrame({
        "Brand_Class": ["Premium", "Midscale", "Economy", "Indépendant"], "Adj_Brand_Bps": [-50, 0, 150, 250],
    })
    st.session_state.condition_adj_df = pd.DataFrame({
        "Condition": ["Rénové <3 ans", "Standard", "Non rénové", "Mauvais état"], "Adj_Condition_Bps": [-75, 0, 125, 250],
    })
    st.session_state.location_adj_df = pd.DataFrame({
        "Location_Class": ["Primaire", "Secondaire", "Tertiaire", "Autoroute / rural"], "Adj_Location_Bps": [-75, 0, 150, 250],
    })
    
    # Historique des calculs
    st.session_state.history_df = pd.DataFrame(columns=[
        "Actif", "Date", "CapRate_Final", "Valeur_Finale", "Valeur_Par_Cle", "Valeur_Par_M2"
    ])

    # Comparables de marché
    st.session_state.market_comps_df = pd.DataFrame({
        'Transaction': ['Ex: Hotel Alpha', 'Ex: Hotel Beta'],
        'Prix_Vente': [25_000_000, 18_000_000],
        'NOI': [1_875_000, 1_530_000],
        'Cles': [150, 120],
        'Surface_m2': [8000, 6500]
    })

    st.session_state.initialized = True

# =========================
# Formatting helpers
# =========================
def fmt_pct(x): return f"{x:.2%}" if pd.notna(x) else "N/A"
def fmt_bps(x): return f"{x:+.0f} bps" if pd.notna(x) else "N/A"
def fmt_eur(x): return f"€ {x:,.0f}".replace(",", " ") if pd.notna(x) else "N/A"

# =========================
# Mapping & Computation
# =========================
def map_age_adjustment(age, age_table):
    row = age_table[(age_table["Age_Min"] <= age) & (age_table["Age_Max"] >= age)]
    return float(row["Adj_Age_Bps"].iloc[0]) if not row.empty else 0.0

def map_exact_adjustment(value, table, key_col, value_col):
    row = table[table[key_col] == value]
    return float(row[value_col].iloc[0]) if not row.empty else 0.0

def compute_cap_rate(inputs_df):
    # Utilise les tables de l'état de la session, qui peuvent avoir été éditées
    df = inputs_df.merge(st.session_state.base_rates_df, on="Segment", how="left")

    df["Adj_Age_Bps"] = df["Age_For_Adjustment"].apply(lambda x: map_age_adjustment(x, st.session_state.age_adj_df))
    df["Adj_Brand_Bps"] = df["Brand_Class"].apply(lambda x: map_exact_adjustment(x, st.session_state.brand_adj_df, "Brand_Class", "Adj_Brand_Bps"))
    df["Adj_Condition_Bps"] = df["Condition"].apply(lambda x: map_exact_adjustment(x, st.session_state.condition_adj_df, "Condition", "Adj_Condition_Bps"))
    df["Adj_Location_Bps"] = df["Location_Class"].apply(lambda x: map_exact_adjustment(x, st.session_state.location_adj_df, "Location_Class", "Adj_Location_Bps"))
    df["Adj_Taux_Bps"] = (df["Taux10Y"] - df["Taux10Y_Ref"]) * df["Elasticite"] * 10000
    df["Adj_Prime_Locale_Bps"] = df["Prime_Risque_Locale_Bps"]

    df["Adj_Total_Bps"] = df[["Adj_Age_Bps", "Adj_Brand_Bps", "Adj_Condition_Bps", "Adj_Location_Bps", "Adj_Taux_Bps", "Adj_Prime_Locale_Bps"]].sum(axis=1)
    df["CapRate_Final_Bps"] = (df["CapRate_Base_Bps"] + df["Adj_Total_Bps"]).clip(lower=1) # Cap rate ne peut être nul ou négatif
    df["CapRate_Base"] = df["CapRate_Base_Bps"] / 10000
    df["CapRate_Final"] = df["CapRate_Final_Bps"] / 10000

    df["Value_Final"] = df["NOI"] / df["CapRate_Final"]
    df["Value_Per_Key"] = df["Value_Final"] / df["Rooms"]
    df["Value_Per_Sqm"] = df["Value_Final"] / df["Surface_m2"]
    
    return df

# =========================
# Streamlit App UI
# =========================
def main():
    st.set_page_config(page_title="Hotel Cap Rate Underwriting", layout="wide")
    initialize_session_state()
    
    st.title("Hotel Cap Rate Underwriting Tool")
    st.caption("Version 2.0 avec comparables de marché, historique et tables de paramètres éditables.")
    
    current_year = pd.Timestamp.today().year

    # --- Sidebar Inputs ---
    with st.sidebar:
        st.header("Paramètres de l'actif")
        asset_name = st.text_input("Nom de l’actif", "Hotel A")
        rooms = st.number_input("Nombre de clés", min_value=1, value=120)
        surface_m2 = st.number_input("Surface (m²)", min_value=1, value=6000)
        segment = st.selectbox("Segment", st.session_state.base_rates_df["Segment"].tolist(), index=3)
        age_physical = st.slider("Âge physique (années)", 0, 60, 22)
        year_last_reno = st.number_input("Année dernière rénovation", 1950, current_year, 2020)
        
        st.header("Marché & Rendement")
        noi = st.number_input("NOI annuel stabilisé (€)", 0.0, value=1_000_000.0, step=50_000.0, format="%.0f")
        taux10y_pct = st.slider("Taux 10Y actuel (%)", 0.0, 10.0, 4.25, step=0.05)
        taux10y_ref_pct = st.slider("Taux 10Y de référence (%)", 0.0, 10.0, 4.00, step=0.05)
        elasticite = st.slider("Élasticité cap rate / taux", 0.0, 1.0, 0.25, step=0.05)
        prime_locale_bps = st.slider("Prime de risque locale (bps)", 0, 300, 50, step=5)
        
        st.header("Catégorisation qualitative")
        brand_class = st.selectbox("Classe de marque", st.session_state.brand_adj_df["Brand_Class"].tolist(), index=1)
        condition = st.selectbox("Condition", st.session_state.condition_adj_df["Condition"].tolist(), index=2)
        location_class = st.selectbox("Localisation", st.session_state.location_adj_df["Location_Class"].tolist(), index=2)

    # --- Pre-computation ---
    years_since_reno = max(0, current_year - int(year_last_reno))
    age_for_adjustment = min(age_physical, years_since_reno) if years_since_reno > 0 else age_physical
    
    inputs_df = pd.DataFrame({
        "Asset_Name": [asset_name], "Rooms": [rooms], "Surface_m2": [surface_m2], "Segment": [segment],
        "Age_Physical": [age_physical], "Year_Last_Reno": [int(year_last_reno)], "Years_Since_Reno": [years_since_reno],
        "Age_For_Adjustment": [age_for_adjustment], "Brand_Class": [brand_class], "Condition": [condition],
        "Location_Class": [location_class], "Taux10Y": [taux10y_pct / 100], "Taux10Y_Ref": [taux10y_ref_pct / 100],
        "Elasticite": [elasticite], "Prime_Risque_Locale_Bps": [prime_locale_bps], "NOI": [noi],
    })

    calc_df = compute_cap_rate(inputs_df)
    row = calc_df.iloc[0]

    # --- Main Display ---
    st.subheader(f"Résultats pour : {asset_name}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Cap Rate de Base", fmt_pct(row["CapRate_Base"]))
    c2.metric("Cap Rate Final", fmt_pct(row["CapRate_Final"]), fmt_bps(row["Adj_Total_Bps"]))
    c3.metric("Valeur Implicite", fmt_eur(row["Value_Final"]))
    c4.metric("Valeur / Clé", fmt_eur(row["Value_Per_Key"]))
    c5.metric("Valeur / m²", fmt_eur(row["Value_Per_Sqm"]))
    
    if st.button("💾 Ajouter ce calcul au comparatif"):
        new_entry = pd.DataFrame({
            "Actif": [row["Asset_Name"]],
            "Date": [pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')],
            "CapRate_Final": [row["CapRate_Final"]],
            "Valeur_Finale": [row["Value_Final"]],
            "Valeur_Par_Cle": [row["Value_Per_Key"]],
            "Valeur_Par_M2": [row["Value_Per_Sqm"]]
        })
        st.session_state.history_df = pd.concat([st.session_state.history_df, new_entry], ignore_index=True)
        st.success(f"'{asset_name}' ajouté au comparatif historique.")

    tab1, tab2, tab3, tab4 = st.tabs(["Waterfall", "Sensibilité", "Comparables de marché", "Historique & Stats"])

    with tab1:
        st.subheader("Waterfall du Cap Rate")
        detail = pd.DataFrame({
            "Composant": ["Base", "Âge", "Marque", "Condition", "Localisation", "Taux longs", "Prime locale", "Final"],
            "bps": [row["CapRate_Base_Bps"], row["Adj_Age_Bps"], row["Adj_Brand_Bps"], row["Adj_Condition_Bps"], row["Adj_Location_Bps"], row["Adj_Taux_Bps"], row["Adj_Prime_Locale_Bps"], row["CapRate_Final_Bps"]]
        })
        detail["%"] = detail["bps"] / 10000
        st.dataframe(detail.style.format({"bps": "{:+.0f}", "%": fmt_pct}), use_container_width=True)
        
        # Waterfall Chart
        steps = detail[detail['Composant'] != 'Final'].set_index('Composant')
        steps['Cumulé'] = steps['bps'].cumsum()
        st.bar_chart(steps, y='Cumulé')

    with tab2:
        st.subheader("Analyse de Sensibilité")
        sens_data = []
        for bps_shift in [-100, -50, 0, 50, 100]:
            cr_bps = row["CapRate_Final_Bps"] + bps_shift
            cr = cr_bps / 10000
            val = noi / cr if cr > 0 else np.nan
            sens_data.append([f"{bps_shift:+.0f} bps", cr, val, val / rooms, val/surface_m2])
        
        sens_df = pd.DataFrame(sens_data, columns=["Scénario", "Cap Rate", "Valeur", "Valeur / Clé", "Valeur / m²"])
        st.dataframe(sens_df.style.format({
            "Cap Rate": fmt_pct, "Valeur": fmt_eur, "Valeur / Clé": fmt_eur, "Valeur / m²": fmt_eur
        }), use_container_width=True)

    with tab3:
        st.subheader("Comparables de Marché (éditable)")
        st.caption("Saisissez les données des transactions. Les ratios sont calculés automatiquement.")
        
        edited_comps = st.data_editor(st.session_state.market_comps_df, num_rows="dynamic", use_container_width=True)
        
        # Recalculate ratios for comps
        edited_comps['Cap_Rate'] = (edited_comps['NOI'] / edited_comps['Prix_Vente']).replace([np.inf, -np.inf], 0)
        edited_comps['Prix_Par_Cle'] = (edited_comps['Prix_Vente'] / edited_comps['Cles']).replace([np.inf, -np.inf], 0)
        edited_comps['Prix_Par_M2'] = (edited_comps['Prix_Vente'] / edited_comps['Surface_m2']).replace([np.inf, -np.inf], 0)
        
        st.session_state.market_comps_df = edited_comps # Save edits
        
        st.dataframe(edited_comps.style.format({
            'Prix_Vente': fmt_eur, 'NOI': fmt_eur, 'Cap_Rate': fmt_pct, 'Prix_Par_Cle': fmt_eur, 'Prix_Par_M2': fmt_eur
        }), use_container_width=True)
        
    with tab4:
        st.subheader("Historique des calculs & Statistiques")
        if st.session_state.history_df.empty:
            st.info("Aucun calcul sauvegardé. Cliquez sur 'Ajouter ce calcul au comparatif' pour commencer.")
        else:
            # Stats
            hist_mean = st.session_state.history_df['CapRate_Final'].mean()
            hist_std = st.session_state.history_df['CapRate_Final'].std()
            
            sc1, sc2 = st.columns(2)
            sc1.metric("Moyenne Cap Rates sauvegardés", fmt_pct(hist_mean))
            sc2.metric("Écart-type Cap Rates sauvegardés", fmt_pct(hist_std))
            
            # Display history
            st.dataframe(st.session_state.history_df.style.format({
                'CapRate_Final': fmt_pct, 'Valeur_Finale': fmt_eur, 'Valeur_Par_Cle': fmt_eur, 'Valeur_Par_M2': fmt_eur
            }), use_container_width=True)
            
            # Download button
            csv = st.session_state.history_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Télécharger l'historique en CSV",
                data=csv,
                file_name='cap_rate_history.csv',
                mime='text/csv',
            )
    
    # --- Editable Tables Expander ---
    with st.expander("⚙️ Paramètres du modèle (éditable)"):
        st.warning("Les modifications ici sont temporaires et ne s'appliquent qu'à cette session.")
        
        t1, t2, t3, t4, t5 = st.tabs(["Segments", "Âge", "Marque", "Condition", "Localisation"])
        with t1:
            st.session_state.base_rates_df = st.data_editor(st.session_state.base_rates_df, key="edit_base", use_container_width=True)
        with t2:
            st.session_state.age_adj_df = st.data_editor(st.session_state.age_adj_df, key="edit_age", use_container_width=True)
        with t3:
            st.session_state.brand_adj_df = st.data_editor(st.session_state.brand_adj_df, key="edit_brand", use_container_width=True)
        with t4:
            st.session_state.condition_adj_df = st.data_editor(st.session_state.condition_adj_df, key="edit_cond", use_container_width=True)
        with t5:
            st.session_state.location_adj_df = st.data_editor(st.session_state.location_adj_df, key="edit_loc", use_container_width=True)

if __name__ == "__main__":
    main()
