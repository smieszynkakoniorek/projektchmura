import streamlit as st
from supabase import create_client
import pandas as pd
import math

# Połączenie
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = create_client(URL, KEY)

st.set_page_config(page_title="WMS System", layout="wide")
st.title("📦 Panel Zarządzania Magazynem (WMS)")

try:
    # 1. Pobranie parametrów (pojemność TIRa z bazy)
    res_p = supabase.table("parametry").select("*").eq("klucz", "pojemnosc_tir").single().execute()
    tir_limit = res_p.data['wartosc_int']

    # 2. Pobranie danych magazynowych
    res_m = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(res_m.data)
    df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')

    # --- LOGIKA BIZNESOWA ---
    # Automatyczna utylizacja choinek poniżej 30 sztuk
    def apply_rules(row):
        status = row['status']
        if "Choinka" in row['nazwa_produktu'] and row['ilosc'] < 30:
            status = "utylizuj"
        
        # Odrzucanie punktów dla statusów: wysyłka, wyprzedane, utylizuj
        punkty = "TAK" if status not in ["wysyłka", "wyprzedane", "utylizuj"] else "NIE"
        return pd.Series([status, punkty])

    df[['status', 'naliczaj_punkty']] = df.apply(apply_rules, axis=1)

    # Obliczanie TIRów (=ZAOKR.GÓRA)
    df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit))

    # Wyświetlanie statystyk
    c1, c2, c3 = st.columns(3)
    c1.metric("Łączna ilość", df['ilosc'].sum())
    c2.metric("Produkty do utylizacji", len(df[df['status'] == 'utylizuj']))
    c3.metric("Potrzebne TIRy", df['TIRy'].sum())

    # Tabela danych
    st.write(f"### Aktualny stan (1 TIR = {tir_limit} szt.)")
    st.dataframe(df[['nazwa_produktu', 'kategoria', 'ilosc', 'cena', 'status', 'naliczaj_punkty', 'TIRy']], use_container_width=True)

except Exception as e:
    st.error(f"Czekam na bazę danych lub instalację bibliotek... Błąd: {e}")
