import streamlit as st
from supabase import create_client
import pandas as pd
import math

# --- KONFIGURACJA POŁĄCZENIA ---
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = create_client(URL, KEY)

st.set_page_config(page_title="WMS Pro 2026", layout="wide")

# --- FUNKCJE POMOCNICZE ---
def fetch_data():
    """Pobiera świeże dane z bazy."""
    res_m = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(res_m.data)
    if not df.empty:
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
    return df

def fetch_categories():
    """Pobiera listę kategorii do formularza."""
    res_c = supabase.table("kategorie").select("*").execute()
    return {item['nazwa']: item['id'] for item in res_c.data}

# --- INTERFEJS UŻYTKOWNIKA ---
st.title("📦 System WMS: Zarządzanie Magazynem")

# Sidebar - Dodawanie i Edycja
with st.sidebar:
    st.header("Zarządzanie Towarem")
    
    # 1. FORMULARZ: DODAWANIE NOWEGO PRODUKTU
    with st.expander("➕ Dodaj nowy produkt"):
        with st.form("add_form", clear_on_submit=True):
            nowa_nazwa = st.text_input("Nazwa produktu")
            nowa_ilosc = st.number_input("Ilość początkowa", min_value=0, step=1)
            nowa_cena = st.number_input("Cena", min_value=0.0, step=0.01)
            kategorie_dict = fetch_categories()
            wybrana_kat = st.selectbox("Kategoria", options=list(kategorie_dict.keys()))
            nowy_status = st.selectbox("Status", ["dostępny", "wysyłka", "wyprzedane", "utylizuj"])
            
            submit_add = st.form_submit_button("Zatwierdź produkt")
            
            if submit_add and nowa_nazwa:
                new_data = {
                    "nazwa_produktu": nowa_nazwa,
                    "ilosc": nowa_ilosc,
                    "cena": nowa_cena,
                    "kategoria_id": kategorie_dict[wybrana_kat],
                    "status": nowy_status
                }
                supabase.table("magazyn").insert(new_data).execute()
                st.success("Dodano produkt!")
                st.rerun()

    # 2. FORMULARZ: DODAJ/ODEJMIJ ILOŚĆ (AKTUALIZACJA)
    with st.expander("🔄 Zmień ilość (Dostawa/Wydanie)"):
        df_current = fetch_data()
        if not df_current.empty:
            produkt_do_zmiany = st.selectbox("Wybierz produkt", df_current['nazwa_produktu'].tolist())
            operacja = st.radio("Operacja", ["Dodaj", "Odejmij"])
            ile_zmienic = st.number_input("Ilość", min_value=1, step=1)
            
            if st.button("Zapisz zmianę ilości"):
                row = df_current[df_current['nazwa_produktu'] == produkt_do_zmiany].iloc[0]
                nowa_suma = row['ilosc'] + ile_zmienic if operacja == "Dodaj" else row['ilosc'] - ile_zmienic
                
                if nowa_suma < 0:
                    st.error("Błąd: Ilość nie może być ujemna!")
                else:
                    supabase.table("magazyn").update({"ilosc": nowa_suma}).eq("id", row['id']).execute()
                    st.success(f"Zaktualizowano {produkt_do_zmiany} na {nowa_suma} szt.")
                    st.rerun()

# --- GŁÓWNY PANEL WYŚWIETLANIA ---
try:
    # Pobranie limitu TIRa
    res_p = supabase.table("parametry").select("*").eq("klucz", "pojemnosc_tir").single().execute()
    tir_limit = res_p.data['wartosc_int']

    df = fetch_data()

    if not df.empty:
        # LOGIKA BIZNESOWA (zgodnie z Twoimi instrukcjami)
        def apply_rules(row):
            status = row['status']
            # Choinki poniżej 30 sztuk są utylizowane
            if "Choinka" in str(row['nazwa_produktu']) and row['ilosc'] < 30:
                status = "utylizuj"
            
            # Punkty odrzucane dla konkretnych statusów
            punkty = "TAK" if status not in ["wysyłka", "wyprzedane", "utylizuj"] else "NIE"
            return pd.Series([status, punkty])

        df[['status', 'naliczaj_punkty']] = df.apply(apply_rules, axis=1)
        df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit))

        # Statystyki
        c1, c2, c3 = st.columns(3)
        c1.metric("Suma towaru", df['ilosc'].sum())
        c2.metric("Do utylizacji", len(df[df['status'] == 'utylizuj']))
        c3.metric("Potrzebne TIRy", df['TIRy'].sum())

        # Tabela
        st.dataframe(
            df[['nazwa_produktu', 'kategoria', 'ilosc', 'status', 'naliczaj_punkty', 'TIRy']],
            use_container_width=True
        )
    else:
        st.info("Magazyn jest pusty. Dodaj pierwszy produkt w panelu bocznym.")

except Exception as e:
    st.error(f"Problem z połączeniem: {e}")
