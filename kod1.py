import streamlit as st
import pandas as pd
import plotly.express as px
import math
from supabase import create_client

# --- POŁĄCZENIE ---
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = create_client(URL, KEY)

def fetch_safe_data():
    try:
        res = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
            
            # --- ZASTOSOWANIE TWOICH ZASAD BIZNESOWYCH ---
            # 1. Pobranie parametru TIR ($C$6)
            config = supabase.table("parametry").select("wartosc_int").eq("klucz", "pojemnosc_tir").single().execute()
            tir_limit = config.data['wartosc_int']
            
            # 2. Logika utylizacji choinek < 30 sztuk
            def calculate_status(row):
                if "Choinka" in str(row['nazwa_produktu']) and row['ilosc'] < 30:
                    return "utylizuj"
                return row['status']
            
            df['status'] = df.apply(calculate_status, axis=1)

            # 3. Odrzucanie punktów dla statusów: wysyłka, wyprzedane, utylizuj
            statusy_odrzucone = ["wysyłka", "wyprzedane", "utylizuj"]
            df['punkty_liczone'] = df['status'].apply(lambda x: "NIE" if x in statusy_odrzucone else "TAK")

            # 4. Formuła TIRów: ZAOKR.GÓRA(ilosc / parametr)
            df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit))
            
            return df, tir_limit
    except Exception as e:
        st.error(f"Błąd pobierania danych: {e}")
    return pd.DataFrame(), 80

st.title("📊 System WMS - Dashboard")

df, limit = fetch_safe_data()

if not df.empty:
    tab_dash, tab_tabela = st.tabs(["📈 Analiza Wykresów", "📋 Pełna Tabela"])

    with tab_dash:
        col1, col2 = st.columns(2)
        
        with col1:
            # Wykres ilości produktów z podziałem na statusy
            fig_stock = px.bar(
                df, 
                x='nazwa_produktu', 
                y='ilosc', 
                color='status',
                title="Stan Magazynowy wg Produktu",
                color_discrete_map={"utylizuj": "red", "dostępny": "green", "wysyłka": "blue", "wyprzedane": "gray"}
            )
            st.plotly_chart(fig_stock, use_container_width=True)

        with col2:
            # Wykres kołowy pokazujący udział kategorii
            fig_pie = px.pie(
                df, 
                names='kategoria', 
                values='ilosc', 
                title="Udział Kategorii w Magazynie"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
        # Dodatkowe wskaźniki
        m1, m2, m3 = st.columns(3)
        m1.metric("Suma potrzebnych TIRów", df['TIRy'].sum())
        m2.metric("Produkty bez punktów", len(df[df['punkty_liczone'] == "NIE"]))
        m3.metric("Łączna ilość sztuk", df['ilosc'].sum())

    with tab_tabela:
        st.write(f"### Dane magazynowe (Parametr TIR: {limit})")
        st.dataframe(df[['nazwa_produktu', 'ilosc', 'status', 'punkty_liczone', 'TIRy', 'kategoria']])
else:
    st.warning("Baza danych jest pusta lub nie udało się połączyć. Dodaj towary, aby zobaczyć dashboard.")
