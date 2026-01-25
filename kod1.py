import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import requests
import json

# --- PATCH DLA PRZEGLĄDARKI (Pyodide/Stlite) ---
# Pozwala używać biblioteki requests w środowisku WebAssembly.
# Lokalnie (na komputerze) ten blok zostanie pominięty.
try:
    import pyodide_http
    pyodide_http.patch_all()
except ImportError:
    pass

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="System Magazynowy Cloud",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- MINIMALISTYCZNY KLIENT SUPABASE ---
# Wrapper, który działa tak samo w przeglądarce i lokalnie
class SupabaseClient:
    def __init__(self, url, key):
        self.base_url = url
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def table(self, name):
        return QueryBuilder(self.base_url, name, self.headers)

class QueryBuilder:
    def __init__(self, base_url, table, headers):
        self.url = f"{base_url}/rest/v1/{table}"
        self.headers = headers
        self.params = {}

    def select(self, columns="*"):
        self.params["select"] = columns
        return self

    def order(self, column, desc=False):
        self.params["order"] = f"{column}.{'desc' if desc else 'asc'}"
        return self
    
    def eq(self, column, value):
        self.params[column] = f"eq.{value}"
        return self

    def execute(self):
        try:
            r = requests.get(self.url, headers=self.headers, params=self.params)
            r.raise_for_status()
            return Response(r.json())
        except Exception as e:
            return Response([], error=str(e))

    def insert(self, data):
        try:
            r = requests.post(self.url, headers=self.headers, json=data)
            r.raise_for_status()
            return Response(r.json())
        except Exception as e:
            return Response([], error=str(e))

    def update(self, data):
        try:
            r = requests.patch(self.url, headers=self.headers, json=data, params=self.params)
            r.raise_for_status()
            return Response(r.json())
        except Exception as e:
            return Response([], error=str(e))

class Response:
    def __init__(self, data, error=None):
        self.data = data if data is not None else []
        self.error = error

# --- POŁĄCZENIE Z SUPABASE ---
# Upewnij się, że klucze są poprawne
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co" 
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = SupabaseClient(URL, KEY)

# --- FUNKCJE POBIERANIA DANYCH ---
def get_categories():
    res = supabase.table("kategorie").select("*").execute()
    return pd.DataFrame(res.data) if not res.error else pd.DataFrame()

def get_inventory():
    res = supabase.table("magazyn").select("*").order("id").execute()
    return pd.DataFrame(res.data) if not res.error else pd.DataFrame()

def get_history():
    res = supabase.table("historia_transakcji").select("*").order("data_operacji", desc=True).execute()
    return pd.DataFrame(res.data) if not res.error else pd.DataFrame()

def get_parameters():
    res = supabase.table("parametry").select("*").execute()
    return pd.DataFrame(res.data) if not res.error else pd.DataFrame()

# --- LOGIKA BIZNESOWA ---
def update_stock(product_id, product_name, change_amount, operation_type, current_stock):
    new_stock = current_stock + change_amount
    if new_stock < 0:
        return False, "Stan magazynowy nie może być ujemny!"

    status = "dostępny"
    if new_stock == 0: status = "wyprzedane"
    elif new_stock < 10: status = "ostatnie sztuki"

    try:
        supabase.table("magazyn").eq("id", product_id).update({
            "ilosc": new_stock,
            "status": status,
            "data_aktualizacji": datetime.now().isoformat()
        })
        supabase.table("historia_transakcji").insert({
            "produkt_nazwa": product_name,
            "typ_operacji": operation_type,
            "zmiana_ilosci": abs(change_amount),
            "data_operacji": datetime.now().isoformat()
        })
        return True, "Sukces"
    except Exception as e:
        return False, str(e)

# --- UI APLIKACJI ---

# Naprawiony CSS: Wymusza czarny tekst wewnątrz kafelków (Metrics),
# nawet jeśli cała aplikacja jest w trybie Dark Mode.
st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
        color: #000000;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    /* Etykieta (np. "Produkty") - ciemnoszary */
    div[data-testid="stMetric"] label {
        color: #666666 !important;
    }
    /* Wartość (np. "11") - czarny */
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #000000 !important;
    }
    /* Ikona delty (zmiany) - zachowuje oryginalne kolory (zielony/czerwony) */
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("📦 Magazyn Cloud")
    page = st.radio("Menu", ["Dashboard", "Magazyn", "Operacje", "Historia", "Logistyka"])
    
    st.caption("Status: Online (Supabase)")
    # Sprawdzenie środowiska dla informacji użytkownika
    try:
        import pyodide_http
        st.info("Tryb przeglądarkowy (Stlite)")
    except ImportError:
        pass

# Pobranie danych
df_magazyn = get_inventory()
df_kategorie = get_categories()
df_historia = get_history()

# Merge kategorii (dołączenie nazwy kategorii do produktu)
if not df_magazyn.empty and not df_kategorie.empty:
    df_magazyn = df_magazyn.merge(df_kategorie, left_on="kategoria_id", right_on="id", suffixes=("", "_kat"))
    if 'nazwa' not in df_magazyn.columns and 'nazwa_kat' in df_magazyn.columns:
        df_magazyn['nazwa'] = df_magazyn['nazwa_kat']

# 1. DASHBOARD
if page == "Dashboard":
    st.header("📊 Dashboard")
    if df_magazyn.empty:
        st.warning("Brak danych lub błąd połączenia z bazą.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Produkty", len(df_magazyn))
        col2.metric("Sztuki łącznie", df_magazyn['ilosc'].sum())
        val = (df_magazyn['ilosc'] * df_magazyn['cena']).sum()
        col3.metric("Wartość (PLN)", f"{val:,.2f}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Ilość wg Kategorii")
            if 'nazwa' in df_magazyn.columns:
                fig = px.bar(df_magazyn, x='nazwa', y='ilosc', color='status')
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("Statusy")
            fig2 = px.pie(df_magazyn, names='status', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

# 2. MAGAZYN
elif page == "Magazyn":
    st.header("📦 Stan Magazynowy")
    
    search = st.text_input("Szukaj produktu...")
    if not df_magazyn.empty:
        df_show = df_magazyn.copy()
        if search:
            df_show = df_show[df_show['nazwa_produktu'].str.contains(search, case=False, na=False)]
        
        # Wybór kolumn do wyświetlenia
        cols = ['id', 'nazwa_produktu', 'ilosc', 'cena', 'status']
        if 'nazwa' in df_show.columns: cols.insert(2, 'nazwa') # Dodaj kategorię jeśli jest
        
        st.dataframe(df_show[cols], use_container_width=True)
    
    with st.expander("Dodaj nowy produkt"):
        with st.form("add_prod"):
            n = st.text_input("Nazwa")
            k = st.selectbox("Kategoria", df_kategorie['nazwa'].tolist() if not df_kategorie.empty else [])
            i = st.number_input("Ilość", min_value=0, step=1)
            c = st.number_input("Cena", min_value=0.0, step=0.01)
            
            if st.form_submit_button("Dodaj"):
                if n and k:
                    kid = df_kategorie[df_kategorie['nazwa'] == k]['id'].values[0]
                    res = supabase.table("magazyn").insert({
                        "nazwa_produktu": n, "kategoria_id": int(kid), "ilosc": int(i),
                        "cena": float(c), "status": "dostępny" if i>0 else "wyprzedane",
                        "data_aktualizacji": datetime.now().isoformat()
                    })
                    if not res.error:
                        st.success("Dodano!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Błąd: {res.error}")

# 3. OPERACJE
elif page == "Operacje":
    st.header("🛠 Operacje Magazynowe")
    tab1, tab2 = st.tabs(["Dostawa (+)", "Wydanie (-)"])
    
    with tab1:
        p_in = st.selectbox("Produkt", df_magazyn['nazwa_produktu'].unique().tolist() if not df_magazyn.empty else [], key="in")
        q_in = st.number_input("Ilość do dodania", 1, step=1, key="qin")
        if st.button("Zaksięguj Dostawę"):
            row = df_magazyn[df_magazyn['nazwa_produktu'] == p_in].iloc[0]
            ok, msg = update_stock(int(row['id']), row['nazwa_produktu'], q_in, "DOSTAWA", int(row['ilosc']))
            if ok:
                st.success(f"Dodano {q_in} szt.")
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)
                
    with tab2:
        p_out = st.selectbox("Produkt", df_magazyn['nazwa_produktu'].unique().tolist() if not df_magazyn.empty else [], key="out")
        q_out = st.number_input("Ilość do wydania", 1, step=1, key="qout")
        type_out = st.selectbox("Typ", ["WYDANIE", "SPRZEDAŻ", "UTYLIZACJA"])
        if st.button("Zaksięguj Wydanie"):
            row = df_magazyn[df_magazyn['nazwa_produktu'] == p_out].iloc[0]
            ok, msg = update_stock(int(row['id']), row['nazwa_produktu'], -q_out, type_out, int(row['ilosc']))
            if ok:
                st.success(f"Wydano {q_out} szt.")
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)

# 4. HISTORIA
elif page == "Historia":
    st.header("📜 Historia Transakcji")
    st.dataframe(df_historia, use_container_width=True)

# 5. LOGISTYKA
elif page == "Logistyka":
    st.header("🚚 Kalkulator Logistyczny")
    df_params = get_parameters()
    
    cap = 80
    if not df_params.empty:
        r = df_params[df_params['klucz']=='pojemnosc_tir']
        if not r.empty: cap = r.iloc[0]['wartosc_int']
    
    total = df_magazyn['ilosc'].sum() if not df_magazyn.empty else 0
    needed = total / cap if cap > 0 else 0
    
    c1, c2 = st.columns(2)
    c1.metric("Towar łącznie", total)
    c1.metric("Pojemność TIR", cap)
    c2.metric("Potrzebne TIRy", f"{needed:.2f}")
    
    st.progress(needed - int(needed))
    st.caption(f"Pełnych ciężarówek: {int(needed)}")
