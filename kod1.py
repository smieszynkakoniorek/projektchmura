import streamlit as st
import pandas as pd
import plotly.express as px
import math
from supabase import create_client

# --- POŁĄCZENIE ---
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = create_client(URL, KEY)

# --- FUNKCJA POBIERANIA ---
def get_data():
    res = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
    return pd.DataFrame(res.data)

def get_config():
    res = supabase.table("parametry").select("*").eq("klucz", "pojemnosc_tir").single().execute()
    return res.data['wartosc_int']

# --- GŁÓWNA APLIKACJA ---
df = get_data()

if df.empty:
    st.warning("⚠️ Baza danych jest pusta. Dashboard nie ma danych do wyświetlenia.")
else:
    # Pobieranie parametru C6 dla TIRów
    tir_limit = get_config()

    # Zastosowanie Twoich reguł biznesowych
    def apply_rules(row):
        status = row['status']
        # Choinki poniżej 30 sztuk są utylizowane
        if "Choinka" in str(row['nazwa_produktu']) and row['ilosc'] < 30:
            status = "utylizuj"
        
        # Punkty są odrzucane, gdy status to "wysyłka", "wyprzedane" lub "utylizuj"
        punkty = "NIE" if status in ["wysyłka", "wyprzedane", "utylizuj"] else "TAK"
        return pd.Series([status, punkty])

    df[['status', 'punkty_liczone']] = df.apply(apply_rules, axis=1)
    
    # Formuła do obliczania TIRów: =ZAOKR.GÓRA(ilość / pojemność)
    df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit))

    # --- SEKCOJA DASHBOARD ---
    st.header("📈 Dashboard Analityczny")
    
    col1, col2 = st.columns(2)

    with col1:
        try:
            # Wykres słupkowy ilości produktów
            fig1 = px.bar(df, x='nazwa_produktu', y='ilosc', color='status', 
                          title="Ilość towaru wg Statusu",
                          labels={'ilosc': 'Liczba sztuk', 'nazwa_produktu': 'Produkt'})
            st.plotly_chart(fig1, use_container_width=True)
        except Exception as e:
            st.error(f"Błąd wykresu słupkowego: {e}")

    with col2:
        try:
            # Wykres kołowy kategorii
            # Wyciągamy nazwy kategorii
            df['kat_nazwa'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
            fig2 = px.pie(df, names='kat_nazwa', title="Udział Kategorii w Magazynie")
            st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.error(f"Błąd wykresu kołowego: {e}")

    # Statystyki ogólne
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Suma towaru", int(df['ilosc'].sum()))
    m2.metric("Łącznie TIRów", int(df['TIRy'].sum()))
    m3.metric("Produkty utylizowane", len(df[df['status'] == 'utylizuj']))
