from supabase import create_client, Client
import pandas as pd

# Dane połączenia (podane przez Ciebie)
url = "https://pmgklpkyljdvhhxklnmq.supabase.co"
key = "sb_publishable_d0ujpfmIqQlSzL7Xnj60wA_M-coVjs3"

supabase: Client = create_client(url, key)

def pobierz_magazyn():
    # Pobieramy dane z tabeli magazyn wraz z nazwą kategorii
    response = supabase.table("magazyn").select("*, kategorie(nazwa)").execute()
    data = response.data

    if not data:
        print("Brak danych w tabeli.")
        return

    # Tworzymy DataFrame dla łatwiejszego wyświetlania
    df = pd.DataFrame(data)
    
    # Wyciągamy nazwę kategorii z zagnieżdżonego słownika
    df['kategoria'] = df['kategorie'].apply(lambda x: x['nazwa'] if x else 'Brak')
    df = df.drop(columns=['kategorie'])

    # --- LOGIKA BIZNESOWA ---
    # 1. Sprawdzanie czy punkty są odrzucone
    statusy_odrzucone = ["wysyłka", "wyprzedane", "utylizuj"]
    df['punkty_liczone'] = df['status'].apply(lambda x: "NIE" if x in statusy_odrzucone else "TAK")

    # 2. Logika dla choinek (poniżej 30 sztuk = utylizacja)
    # Zakładamy, że nazwa_produktu zawiera słowo 'Choinka'
    mask_choinki_utylizacja = (df['nazwa_produktu'].str.contains('Choinka', case=False)) & (df['ilosc'] < 30)
    df.loc[mask_choinki_utylizacja, 'status'] = 'utylizuj'
    df.loc[mask_choinki_utylizacja, 'punkty_liczone'] = 'NIE'

    # Wyświetlanie tabeli w konsoli
    print("\n--- STAN MAGAZYNOWY ---")
    print(df[['id', 'nazwa_produktu', 'ilosc', 'cena', 'status', 'kategoria', 'punkty_liczone']].to_string(index=False))

if __name__ == "__main__":
    pobierz_magazyn()
