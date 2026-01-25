import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="System Magazynowy Cloud",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS DLA LEPSZEGO UI ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"] {
        background-color: white;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    h1, h2, h3 {
        font-family: 'Helvetica Neue', sans-serif;
        color: #2c3e50;
    }
    </style>
    """, unsafe_allow_html=True)

# --- POŁĄCZENIE Z SUPABASE ---
@st.cache_resource
def init_connection():
    # WPISZ TUTAJ DANE ZE SWOJEGO ZRZUTU EKRANU (Settings -> API)
    url = "https://pmgklpkyljdvhhxklnmq.supabase.co" 
    key = "TUTAJ_WKLEJ_SWOJ_SUPABASE_KEY_ANON_PUBLIC"  # Wklej klucz zaczynający się od eyJ...
    
    if key == "TUTAJ_WKLEJ_SWOJ_SUPABASE_KEY_ANON_PUBLIC":
        st.error("⚠️ Uzupełnij klucz API w kodzie (funkcja init_connection)!")
        st.stop()
        
    return create_client(url, key)

supabase = init_connection()

# --- FUNKCJE POMOCNICZE (Pobieranie danych) ---
def get_categories():
    response = supabase.table("kategorie").select("*").execute()
    return pd.DataFrame(response.data)

def get_inventory():
    response = supabase.table("magazyn").select("*").order("id").execute()
    return pd.DataFrame(response.data)

def get_history():
    response = supabase.table("historia_transakcji").select("*").order("data_operacji", desc=True).execute()
    return pd.DataFrame(response.data)

def get_parameters():
    response = supabase.table("parametry").select("*").execute()
    return pd.DataFrame(response.data)

# --- LOGIKA BIZNESOWA ---
def update_stock(product_id, product_name, change_amount, operation_type, current_stock):
    """Aktualizuje stan magazynowy i dodaje wpis do historii"""
    new_stock = current_stock + change_amount
    
    # Zabezpieczenie przed ujemnym stanem
    if new_stock < 0:
        return False, "Stan magazynowy nie może być ujemny!"

    status = "dostępny"
    if new_stock == 0:
        status = "wyprzedane"
    elif new_stock < 10:
        status = "ostatnie sztuki"

    try:
        # 1. Aktualizacja tabeli magazyn
        supabase.table("magazyn").update({
            "ilosc": new_stock,
            "status": status,
            "data_aktualizacji": datetime.now().isoformat()
        }).eq("id", product_id).execute()

        # 2. Dodanie wpisu do historii transakcji
        supabase.table("historia_transakcji").insert({
            "produkt_nazwa": product_name,
            "typ_operacji": operation_type,
            "zmiana_ilosci": abs(change_amount),
            "data_operacji": datetime.now().isoformat()
        }).execute()
        
        return True, "Operacja zakończona sukcesem."
    except Exception as e:
        return False, str(e)

# --- INTERFEJS UŻYTKOWNIKA ---

# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2897/2897785.png", width=50)
    st.title("Magazyn Admin")
    page = st.radio("Nawigacja", ["Dashboard", "Magazyn", "Operacje (Przyjęcia/Wydania)", "Historia Transakcji", "Logistyka"])
    st.markdown("---")
    st.caption("v1.0.0 | Connected to Supabase")

# Pobranie danych na starcie
df_magazyn = get_inventory()
df_kategorie = get_categories()
df_historia = get_history()

# Łączenie kategorii z magazynem (dla ładnych nazw)
if not df_magazyn.empty and not df_kategorie.empty:
    df_magazyn = df_magazyn.merge(df_kategorie, left_on="kategoria_id", right_on="id", suffixes=("", "_kat"))

# --- STRONA: DASHBOARD ---
if page == "Dashboard":
    st.title("📊 Przegląd Magazynu")
    
    if df_magazyn.empty:
        st.warning("Brak produktów w bazie.")
    else:
        # KPI Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        total_items = df_magazyn['ilosc'].sum()
        total_value = (df_magazyn['ilosc'] * df_magazyn['cena']).sum()
        low_stock = df_magazyn[df_magazyn['ilosc'] < 20].shape[0]
        active_products = df_magazyn['id'].count()

        col1.metric("Całkowita ilość sztuk", f"{total_items}", delta="Sztuki")
        col2.metric("Wartość magazynu", f"{total_value:,.2f} PLN", delta="PLN")
        col3.metric("Niski stan (<20)", f"{low_stock}", delta_color="inverse")
        col4.metric("Aktywne produkty", f"{active_products}")

        # Wykresy
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("Wartość magazynu wg Kategorii")
            if 'nazwa' in df_magazyn.columns:
                fig_bar = px.bar(df_magazyn, x='nazwa', y='ilosc', color='status', 
                                 title="Ilość produktów w kategoriach", labels={'nazwa': 'Kategoria', 'ilosc': 'Ilość'})
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Brak przypisanych nazw kategorii.")

        with c2:
            st.subheader("Statusy produktów")
            status_counts = df_magazyn['status'].value_counts().reset_index()
            status_counts.columns = ['status', 'count']
            fig_pie = px.donut(status_counts, values='count', names='status', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_pie, use_container_width=True)

# --- STRONA: MAGAZYN ---
elif page == "Magazyn":
    st.title("📦 Stan Magazynowy")
    
    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("🔍 Szukaj produktu...", placeholder="Wpisz nazwę...")
    with col_filter:
        category_filter = st.selectbox("Filtruj kategorię", ["Wszystkie"] + list(df_kategorie['nazwa'].unique()) if not df_kategorie.empty else [])

    # Filtrowanie
    filtered_df = df_magazyn.copy()
    if search_query:
        filtered_df = filtered_df[filtered_df['nazwa_produktu'].str.contains(search_query, case=False, na=False)]
    if category_filter != "Wszystkie":
        filtered_df = filtered_df[filtered_df['nazwa'] == category_filter]

    # Display Dataframe
    st.dataframe(
        filtered_df[['id', 'nazwa_produktu', 'nazwa', 'ilosc', 'cena', 'status', 'data_aktualizacji']],
        column_config={
            "id": "ID",
            "nazwa_produktu": "Produkt",
            "nazwa": "Kategoria",
            "ilosc": st.column_config.NumberColumn("Ilość", format="%d szt."),
            "cena": st.column_config.NumberColumn("Cena", format="%.2f PLN"),
            "status": "Status",
            "data_aktualizacji": st.column_config.DatetimeColumn("Ostatnia zmiana", format="D MMM YYYY, HH:mm"),
        },
        use_container_width=True,
        hide_index=True
    )

    # Dodawanie nowego produktu
    with st.expander("➕ Dodaj nowy produkt"):
        with st.form("add_product_form"):
            c1, c2 = st.columns(2)
            new_name = c1.text_input("Nazwa produktu")
            new_cat = c2.selectbox("Kategoria", df_kategorie['nazwa'].tolist() if not df_kategorie.empty else [])
            
            c3, c4 = st.columns(2)
            new_qty = c3.number_input("Ilość początkowa", min_value=0, step=1)
            new_price = c4.number_input("Cena (PLN)", min_value=0.0, step=0.01)
            
            submitted = st.form_submit_button("Dodaj do bazy")
            if submitted:
                if new_name and new_cat:
                    cat_id = df_kategorie[df_kategorie['nazwa'] == new_cat]['id'].values[0]
                    supabase.table("magazyn").insert({
                        "nazwa_produktu": new_name,
                        "kategoria_id": int(cat_id),
                        "ilosc": int(new_qty),
                        "cena": float(new_price),
                        "status": "dostępny" if new_qty > 0 else "wyprzedane",
                        "data_aktualizacji": datetime.now().isoformat()
                    }).execute()
                    
                    # Log history for new product
                    supabase.table("historia_transakcji").insert({
                        "produkt_nazwa": new_name,
                        "typ_operacji": "NOWY PRODUKT",
                        "zmiana_ilosci": int(new_qty),
                        "data_operacji": datetime.now().isoformat()
                    }).execute()
                    
                    st.success("Produkt dodany!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Uzupełnij nazwę i kategorię.")

# --- STRONA: OPERACJE ---
elif page == "Operacje (Przyjęcia/Wydania)":
    st.title("🚛 Ruchy Magazynowe")
    
    tab1, tab2 = st.tabs(["📥 Przyjęcie towaru (Dostawa)", "📤 Wydanie towaru (Sprzedaż/Wysyłka)"])
    
    # --- DOSTAWA ---
    with tab1:
        st.subheader("Zarejestruj dostawę")
        selected_product_in = st.selectbox("Wybierz produkt do przyjęcia", df_magazyn['nazwa_produktu'].tolist(), key="in_prod")
        
        if selected_product_in:
            current_item = df_magazyn[df_magazyn['nazwa_produktu'] == selected_product_in].iloc[0]
            st.info(f"Obecny stan: **{current_item['ilosc']}** szt.")
            
            amount_in = st.number_input("Ilość do dodania", min_value=1, step=1, key="in_amount")
            
            if st.button("Zatwierdź dostawę", type="primary"):
                success, msg = update_stock(
                    int(current_item['id']), 
                    current_item['nazwa_produktu'], 
                    amount_in, 
                    "DOSTAWA", 
                    int(current_item['ilosc'])
                )
                if success:
                    st.success(f"Dodano {amount_in} szt. Nowy stan: {current_item['ilosc'] + amount_in}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)

    # --- WYDANIE ---
    with tab2:
        st.subheader("Zarejestruj wydanie")
        selected_product_out = st.selectbox("Wybierz produkt do wydania", df_magazyn['nazwa_produktu'].tolist(), key="out_prod")
        
        if selected_product_out:
            current_item_out = df_magazyn[df_magazyn['nazwa_produktu'] == selected_product_out].iloc[0]
            st.info(f"Obecny stan: **{current_item_out['ilosc']}** szt.")
            
            amount_out = st.number_input("Ilość do wydania", min_value=1, max_value=int(current_item_out['ilosc']), step=1, key="out_amount")
            operation_type = st.selectbox("Typ operacji", ["WYDANIE", "WYSYŁKA", "UTYLIZACJA", "KOREKTA"])
            
            if st.button("Zatwierdź wydanie", type="primary"):
                success, msg = update_stock(
                    int(current_item_out['id']), 
                    current_item_out['nazwa_produktu'], 
                    -amount_out, 
                    operation_type, 
                    int(current_item_out['ilosc'])
                )
                if success:
                    st.success(f"Wydano {amount_out} szt. Nowy stan: {current_item_out['ilosc'] - amount_out}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)

# --- STRONA: HISTORIA ---
elif page == "Historia Transakcji":
    st.title("📜 Historia Operacji")
    
    # Styled dataframe
    st.dataframe(
        df_historia,
        column_config={
            "id": "ID",
            "produkt_nazwa": "Produkt",
            "typ_operacji": st.column_config.TextColumn("Typ Operacji"),
            "zmiana_ilosci": st.column_config.NumberColumn("Ilość", format="%d"),
            "data_operacji": st.column_config.DatetimeColumn("Data", format="D MMM YYYY, HH:mm:ss"),
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.download_button(
        label="Pobierz CSV",
        data=df_historia.to_csv(index=False).encode('utf-8'),
        file_name='historia_magazynu.csv',
        mime='text/csv',
    )

# --- STRONA: LOGISTYKA ---
elif page == "Logistyka":
    st.title("🚚 Kalkulator Logistyczny")
    
    df_params = get_parameters()
    
    # Pobierz pojemność TIR z bazy (tabela parametry widoczna na Twoim screenie)
    pojemnosc_tir = 80 # Default
    if not df_params.empty:
        param_row = df_params[df_params['klucz'] == 'pojemnosc_tir']
        if not param_row.empty:
            pojemnosc_tir = param_row.iloc[0]['wartosc_int']
            st.caption(f"Parametr pobrany z bazy: {param_row.iloc[0]['opis']}")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Dane do transportu")
        total_items = df_magazyn['ilosc'].sum()
        st.metric("Całkowita liczba sztuk w magazynie", total_items)
        st.metric("Pojemność 1 TIR (palety/sztuki)", pojemnosc_tir)
    
    with col2:
        st.subheader("Zapotrzebowanie")
        if pojemnosc_tir > 0:
            trucks_needed = total_items / pojemnosc_tir
            st.metric("Potrzebne TIRy", f"{trucks_needed:.2f}")
            
            # Progress bar visualization
            full_trucks = int(trucks_needed)
            remainder = trucks_needed - full_trucks
            st.write(f"Pełne ciężarówki: **{full_trucks}**")
            st.write(f"Zapełnienie ostatniej: **{remainder*100:.1f}%**")
            st.progress(remainder)
        else:
            st.error("Błąd parametru pojemności TIR (0).")
