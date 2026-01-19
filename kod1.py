import math
import plotly.express as px

# --- KONFIGURACJA ---
# --- KONFIGURACJA POŁĄCZENIA ---
URL = "https://pmgklpkyljdvhhxklnmq.supabase.co"
KEY = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"
supabase = create_client(URL, KEY)

st.set_page_config(page_title="WMS Enterprise 2026", layout="wide")

# --- REPOZYTORIUM DANYCH ---
def get_data():
# --- FUNKCJE DANYCH ---
def fetch_data():
res = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
df = pd.DataFrame(res.data)
if not df.empty:
df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
return df

def get_config():
def fetch_config():
res = supabase.table("parametry").select("*").eq("klucz", "pojemnosc_tir").single().execute()
return res.data['wartosc_int']

# --- INTERFEJS ---
st.title("🚀 Zaawansowany System Magazynowy WMS")

# Pobieranie aktualnych stanów
df = get_data()
tir_limit = get_config()
df = fetch_data()
tir_limit = fetch_config()

# Zastosowanie reguł biznesowych
# APLIKACJA LOGIKI BIZNESOWEJ
if not df.empty:
    def process_rules(row):
    def apply_rules(row):
status = row['status']
        # Reguła: Choinki < 30 sztuk -> utylizuj
        # Zasada: Choinki poniżej 30 sztuk są utylizowane
if "Choinka" in str(row['nazwa_produktu']) and row['ilosc'] < 30:
status = "utylizuj"
        # Reguła: Odrzucanie punktów dla konkretnych statusów
        
        # Zasada: Punkty odrzucane dla statusów: wysyłka, wyprzedane, utylizuj
punkty = "NIE" if status in ["wysyłka", "wyprzedane", "utylizuj"] else "TAK"
return pd.Series([status, punkty])

    df[['status', 'punkty_liczone']] = df.apply(process_rules, axis=1)
    df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit)) # Formuła ZAOKR.GÓRA
    df[['status', 'punkty_liczone']] = df.apply(apply_rules, axis=1)
    df['TIRy'] = df['ilosc'].apply(lambda x: math.ceil(x / tir_limit))

# Zakładki systemowe
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📋 Magazyn", "🔄 Ruch Towaru", "📜 Historia"])
tab_dash, tab_mag, tab_operacje, tab_hist = st.tabs(["📈 Dashboard", "📋 Magazyn", "🔄 Ruch Towaru", "📜 Historia"])

# --- TAB 1: DASHBOARD ---
with tab1:
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(px.bar(df, x='nazwa_produktu', y='ilosc', color='status', title="Stan ilościowy"), use_container_width=True)
    with col_b:
        st.plotly_chart(px.pie(df, names='kategoria', title="Podział towaru wg kategorii"), use_container_width=True)

# --- TAB 2: MAGAZYN ---
with tab2:
    search = st.text_input("Szukaj produktu...")
    display_df = df[df['nazwa_produktu'].str.contains(search, case=False)] if search else df
    st.dataframe(display_df[['nazwa_produktu', 'kategoria', 'ilosc', 'status', 'punkty_liczone', 'TIRy']], use_container_width=True)

# --- TAB 3: RUCH TOWARU ---
with tab3:
# --- TAB: RUCH TOWARU (TUTAJ BYŁ BŁĄD) ---
with tab_operacje:
st.subheader("Zarządzanie ilością")
    with st.form("move_form"):
        p_name = st.selectbox("Produkt", df['nazwa_produktu'].tolist())
        akcja = st.radio("Operacja", ["Dodaj (Dostawa)", "Odejmij (Wydanie)"], horizontal=True)
        ile = st.number_input("Ilość", min_value=1)
    with st.form("form_ruch"):
        prod_name = st.selectbox("Produkt", df['nazwa_produktu'].tolist())
        operacja = st.radio("Operacja", ["Dodaj (Dostawa)", "Odejmij (Wydanie)"], horizontal=True)
        ile = st.number_input("Ilość", min_value=1, step=1)
        
if st.form_submit_button("Zapisz zmianę"):
            row = df[df['nazwa_produktu'] == p_name].iloc[0]
            nowa = row['ilosc'] + ile if "Dodaj" in akcja else row['ilosc'] - ile
            if nowa >= 0:
                supabase.table("magazyn").update({"ilosc": nowa}).eq("id", row['id']).execute()
                supabase.table("historia_transakcji").insert({
                    "produkt_nazwa": p_name, "typ_operacji": "DOSTAWA" if "Dodaj" in akcja else "WYDANIE", "zmiana_ilosci": ile
                }).execute()
                st.success("Zaktualizowano stan magazynowy!")
                st.rerun()
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
                st.error("Błąd: Ilość nie może być mniejsza od zera!")
                st.error("Błąd: Stan magazynowy nie może być ujemny!")

# --- TAB 4: HISTORIA ---
with tab4:
    res_h = supabase.table("historia_transakcji").select("*").order("data_operacji", desc=True).execute()
    st.table(pd.DataFrame(res_h.data)[['data_operacji', 'produkt_nazwa', 'typ_operacji', 'zmiana_ilosci']])
# --- TAB: MAGAZYN ---
with tab_mag:
    st.dataframe(df[['nazwa_produktu', 'kategoria', 'ilosc', 'status', 'punkty_liczone', 'TIRy']], use_container_width=True)
