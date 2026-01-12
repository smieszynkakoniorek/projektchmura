import streamlit as st
from supabase import create_client, Client
import pandas as pd
import math

# Konfiguracja połączenia
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase: Client = create_client(URL, KEY)

st.title("Magazyn Projektu")

# Zakładamy wartość z Parametry!$C$6 (np. ile sztuk mieści się na TIRze)
sztuk_na_tir = st.sidebar.number_input("Sztuk na 1 TIR", value=100)

def fetch_data():
    res = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
    df = pd.DataFrame(res.data)
    
    # 1. Mapowanie kategorii
    df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
    
    # 2. Logika odrzucania punktów (status: wysyłka, wyprzedane, utylizuj)
    statusy_odrzucone = ["wysyłka", "wyprzedane", "utylizuj"]
    df['punkty_liczone'] = df['status'].apply(lambda x: "NIE" if x in statusy_odrzucone else "TAK")

    # 3. Logika utylizacji choinek < 30 sztuk
    mask_choinki = (df['nazwa_produktu'].str.contains('Choinka', case=False)) & (df['ilosc'] < 30)
    df.loc[mask_choinki, 'status'] = 'utylizuj'
    df.loc[mask_choinki, 'punkty_liczone'] = 'NIE'

    # 4. Obliczanie TIRów: =ZAOKR.GÓRA(D2 / Parametry!$C$6)
    df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / sztuk_na_tir))
    
    return df

try:
    data = fetch_data()
    st.dataframe(data[['nazwa_produktu', 'ilosc', 'cena', 'status', 'kategoria', 'punkty_liczone', 'TIRy']])
except Exception as e:
    st.error(f"Wystąpił błąd podczas pobierania danych: {e}")
