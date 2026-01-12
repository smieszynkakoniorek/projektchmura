import streamlit as st
from supabase import create_client
import pandas as pd
import math

# --- KONFIGURACJA POŁĄCZENIA ---
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = create_client(URL, KEY)

st.set_page_config(page_title="WMS Enterprise 2026", layout="wide")

# --- FUNKCJE POMOCNICZE ---
def fetch_data():
    res = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
    return df

def fetch_categories():
    res = supabase.table("kategorie").select("*").execute()
    return {item['nazwa']: item['id'] for item in res.data}

def fetch_config():
    res = supabase.table("parametry").select("*").eq("klucz", "pojemnosc_tir").single().execute()
    return res.data

# --- INTERFEJS ---
st.title("🚀 Zaawansowany System WMS")

# Definicja zakładek
tab_magazyn, tab_dodaj, tab_zarzadzanie, tab_ustawienia = st.tabs([
    "📋 Stan Magazynowy", 
    "➕ Dodaj Towar", 
    "🛠️ Edycja i Usuwanie", 
    "⚙️ Ustawienia"
])

# Pobieranie parametrów logistycznych (Parametr $C$6)
config = fetch_config()
tir_limit = config['wartosc_int']

# --- TAB: DODAJ TOWAR ---
with tab_dodaj:
    st.header("Wprowadzanie nowego towaru do bazy")
    kat_dict = fetch_categories()
    
    with st.form("form_nowy_towar", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            n_nazwa = st.text_input("Nazwa produktu", placeholder="np. Choinka Jodła")
            n_ilosc = st.number_input("Ilość (sztuki)", min_value=0, step=1)
            n_cena = st.number_input("Cena jednostkowa (PLN)", min_value=0.0, step=0.01)
        
        with col2:
            n_kat = st.selectbox("Kategoria", options=list(kat_dict.keys()))
            n_status = st.selectbox("Status początkowy", ["dostępny", "wysyłka", "wyprzedane", "utylizuj"])
        
        submit = st.form_submit_button("✅ Dodaj produkt do magazynu")
        
        if submit:
            if n_nazwa:
                nowy_rekord = {
                    "nazwa_produktu": n_nazwa,
                    "ilosc": n_ilosc,
                    "cena": n_cena,
                    "kategoria_id": kat_dict[n_kat],
                    "status": n_status
                }
                try:
                    supabase.table("magazyn").insert(nowy_rekord).execute()
                    st.success(f"Pomyślnie dodano: {n_nazwa}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd zapisu: {e}")
            else:
                st.warning("Nazwa produktu nie może być pusta!")

# --- TAB: STAN MAGAZYNOWY ---
with tab_magazyn:
    df = fetch_data()
    if not df.empty:
        def apply_logic(row):
            status = row['status']
            # Zasada: Choinki < 30 sztuk są utylizowane
            if "Choinka" in str(row['nazwa_produktu']) and row['ilosc'] < 30:
                status = "utylizuj"
            
            # Zasada: Punkty odrzucane gdy status to "wysyłka", "wyprzedane" lub "utylizuj"
            punkty = "NIE" if status in ["wysyłka", "wyprzedane", "utylizuj"] else "TAK"
            return pd.Series([status, punkty])

        df[['status', 'naliczaj_punkty']] = df.apply(apply_logic, axis=1)
        # Formuła TIRów: =ZAOKR.GÓRA(Ilość / Parametry!$C$6)
        df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit))

        st.subheader(f"Aktualne stany (Pojemność TIRa: {tir_limit} szt.)")
        st.dataframe(df[['nazwa_produktu', 'kategoria', 'ilosc', 'cena', 'status', 'naliczaj_punkty', 'TIRy']], use_container_width=True)
    else:
        st.info("Magazyn jest pusty.")

# --- TAB: EDYCJA I USUWANIE ---
with tab_zarzadzanie:
    if not df.empty:
        col_e, col_d = st.columns(2)
        with col_e:
            st.subheader("Edytuj produkt")
            wybrany = st.selectbox("Wybierz towar", df['nazwa_produktu'].tolist())
            dane = df[df['nazwa_produktu'] == wybrany].iloc[0]
            with st.form("edycja"):
                e_ilosc = st.number_input("Zmień ilość", value=int(dane['ilosc']))
                e_status = st.selectbox("Zmień status", ["dostępny", "wysyłka", "wyprzedane", "utylizuj"], 
                                        index=["dostępny", "wysyłka", "wyprzedane", "utylizuj"].index(dane['status']))
                if st.form_submit_button("Zapisz zmiany"):
                    supabase.table("magazyn").update({"ilosc": e_ilosc, "status": e_status}).eq("id", dane['id']).execute()
                    st.rerun()
        
        with col_d:
            st.subheader("Usuń produkt")
            do_usuniecia = st.selectbox("Towar do usunięcia", df['nazwa_produktu'].tolist())
            if st.button("🔴 USUŃ TRWALE"):
                id_usunj = df[df['nazwa_produktu'] == do_usuniecia].iloc[0]['id']
                supabase.table("magazyn").delete().eq("id", id_usunj).execute()
                st.rerun()

# --- TAB: USTAWIENIA ---
with tab_ustawienia:
    st.header("Konfiguracja parametrów")
    nowa_poj = st.number_input("Zmień pojemność transportową TIRa", value=tir_limit)
    if st.button("Aktualizuj parametr $C$6"):
        supabase.table("parametry").update({"wartosc_int": nowa_poj}).eq("klucz", "pojemnosc_tir").execute()
        st.success("Zmieniono globalne ustawienia logistyki.")
        st.rerun()
