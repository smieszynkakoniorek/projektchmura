import streamlit as st
from supabase import create_client
import pandas as pd
import math

# --- POŁĄCZENIE ---
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = create_client(URL, KEY)

st.set_page_config(page_title="WMS Enterprise 2026", layout="wide")

# --- FUNKCJE BAZODANOWE ---
def fetch_data():
    res = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
    return df

def fetch_config():
    res = supabase.table("parametry").select("*").eq("klucz", "pojemnosc_tir").single().execute()
    return res.data

# --- INTERFEJS ---
st.title("🚀 Zaawansowany System WMS")

# Taby dla lepszej organizacji
tab_magazyn, tab_zarzadzanie, tab_ustawienia = st.tabs(["📋 Stan Magazynowy", "🛠️ Edycja i Usuwanie", "⚙️ Ustawienia Systemu"])

# --- TAB 3: USTAWIENIA (Zarządzanie parametrem C6) ---
with tab_ustawienia:
    st.header("Parametry Logistyczne")
    config = fetch_config()
    nowa_pojemnosc = st.number_input("Pojemność 1 TIRa (Parametr $C$6)", value=config['wartosc_int'], step=1)
    if st.button("Zapisz nową pojemność"):
        supabase.table("parametry").update({"wartosc_int": nowa_pojemnosc}).eq("klucz", "pojemnosc_tir").execute()
        st.success("Zaktualizowano parametry transportu!")
        st.rerun()

tir_limit = nowa_pojemnosc

# --- TAB 1: STAN MAGAZYNOWY (Z filtrowaniem) ---
with tab_magazyn:
    df = fetch_data()
    if not df.empty:
        # Aplikacja logiki biznesowej
        def apply_logic(row):
            status = row['status']
            # Choinki < 30 sztuk -> utylizacja
            if "Choinka" in str(row['nazwa_produktu']) and row['ilosc'] < 30:
                status = "utylizuj"
            
            # Punkty odrzucane: wysyłka, wyprzedane, utylizuj
            punkty = "NIE" if status in ["wysyłka", "wyprzedane", "utylizuj"] else "TAK"
            return pd.Series([status, punkty])

        df[['status', 'naliczaj_punkty']] = df.apply(apply_logic, axis=1)
        # Formuła TIR: ZAOKR.GÓRA(Ilość / Pojemność)
        df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit))

        # Filtry
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            kat_filter = st.multiselect("Filtruj wg kategorii", options=df['kategoria'].unique())
        with f_col2:
            stat_filter = st.multiselect("Filtruj wg statusu", options=df['status'].unique())

        dff = df.copy()
        if kat_filter: dff = dff[dff['kategoria'].isin(kat_filter)]
        if stat_filter: dff = dff[dff['status'].isin(stat_filter)]

        st.dataframe(dff[['nazwa_produktu', 'kategoria', 'ilosc', 'status', 'naliczaj_punkty', 'TIRy']], use_container_width=True)
        
        # Szybki raport
        st.write(f"**Łączna liczba potrzebnych TIRów:** {dff['TIRy'].sum()}")

# --- TAB 2: EDYCJA I USUWANIE ---
with tab_zarzadzanie:
    col_edit, col_del = st.columns(2)
    
    with col_edit:
        st.subheader("Edytuj produkt")
        edit_prod = st.selectbox("Wybierz produkt do edycji", df['nazwa_produktu'].tolist())
        row_to_edit = df[df['nazwa_produktu'] == edit_prod].iloc[0]
        
        with st.form("edit_form"):
            new_n = st.text_input("Nazwa", value=row_to_edit['nazwa_produktu'])
            new_p = st.number_input("Cena", value=float(row_to_edit['cena']))
            new_s = st.selectbox("Status", ["dostępny", "wysyłka", "wyprzedane", "utylizuj"], 
                                 index=["dostępny", "wysyłka", "wyprzedane", "utylizuj"].index(row_to_edit['status']))
            if st.form_submit_button("Zapisz zmiany"):
                supabase.table("magazyn").update({"nazwa_produktu": new_n, "cena": new_p, "status": new_s}).eq("id", row_to_edit['id']).execute()
                st.success("Zaktualizowano dane!")
                st.rerun()

    with col_del:
        st.subheader("Usuń produkt")
        del_prod = st.selectbox("Wybierz produkt do usunięcia", df['nazwa_produktu'].tolist(), key="del")
        if st.button("🔴 USUŃ TRWALE", help="Tej operacji nie da się cofnąć"):
            id_to_del = df[df['nazwa_produktu'] == del_prod].iloc[0]['id']
            supabase.table("magazyn").delete().eq("id", id_to_del).execute()
            st.warning(f"Usunięto {del_prod}")
            st.rerun()
