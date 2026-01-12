import streamlit as st
from supabase import create_client
import pandas as pd
import math
import plotly.express as px

# --- KONFIGURACJA POŁĄCZENIA ---
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = create_client(URL, KEY)

st.set_page_config(page_title="WMS Enterprise 2026", layout="wide")

# --- FUNKCJE DANYCH ---
def fetch_data():
    res = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
    return df

def fetch_config():
    res = supabase.table("parametry").select("*").eq("klucz", "pojemnosc_tir").single().execute()
    return res.data['wartosc_int']

# --- INTERFEJS ---
st.title("🚀 Zaawansowany System Magazynowy WMS")

df = fetch_data()
tir_limit = fetch_config()

# APLIKACJA LOGIKI BIZNESOWEJ
if not df.empty:
    def apply_rules(row):
        status = row['status']
        # Zasada: Choinki poniżej 30 sztuk są utylizowane
        if "Choinka" in str(row['nazwa_produktu']) and row['ilosc'] < 30:
            status = "utylizuj"
        
        # Zasada: Punkty odrzucane dla statusów: wysyłka, wyprzedane, utylizuj
        punkty = "NIE" if status in ["wysyłka", "wyprzedane", "utylizuj"] else "TAK"
        return pd.Series([status, punkty])

    df[['status', 'punkty_liczone']] = df.apply(apply_rules, axis=1)
    df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit))

tab_dash, tab_mag, tab_operacje, tab_hist = st.tabs(["📈 Dashboard", "📋 Magazyn", "🔄 Ruch Towaru", "📜 Historia"])

# --- TAB: RUCH TOWARU (TUTAJ BYŁ BŁĄD) ---
with tab_operacje:
    st.subheader("Zarządzanie ilością")
    with st.form("form_ruch"):
        prod_name = st.selectbox("Produkt", df['nazwa_produktu'].tolist())
        operacja = st.radio("Operacja", ["Dodaj (Dostawa)", "Odejmij (Wydanie)"], horizontal=True)
        ile = st.number_input("Ilość", min_value=1, step=1)
        
        if st.form_submit_button("Zapisz zmianę"):
            row = df[df['nazwa_produktu'] == prod_name].iloc[0]
            
            # Obliczenie nowej ilości
            nowa_ilosc = row['ilosc'] + ile if "Dodaj" in operacja else row['ilosc'] - ile
            
            if nowa_ilosc >= 0:
                try:
                    # KLUCZOWA POPRAWKA: int() dla nowa_ilosc oraz dla ID
                    supabase.table("magazyn").update({"ilosc": int(nowa_ilosc)}).eq("id", int(row['id'])).execute()
                    
                    # Logowanie do historii
                    supabase.table("historia_transakcji").insert({
                        "produkt_nazwa": prod_name,
                        "typ_operacji": "DOSTAWA" if "Dodaj" in operacja else "WYDANIE",
                        "zmiana_ilosci": int(ile)
                    }).execute()
                    
                    st.success(f"Zaktualizowano {prod_name}. Nowy stan: {nowa_ilosc}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd bazy danych: {e}")
            else:
                st.error("Błąd: Stan magazynowy nie może być ujemny!")

# --- TAB: MAGAZYN ---
with tab_mag:
    st.dataframe(df[['nazwa_produktu', 'kategoria', 'ilosc', 'status', 'punkty_liczone', 'TIRy']], use_container_width=True)
