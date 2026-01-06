import ftplib
import time
from openai import OpenAI
from dotenv import load_dotenv
import io
import os

# Načtení proměnných z .env
load_dotenv()

# --- 1. Nastavení ---
FTP_HOST = "webdisk.vse.cz"
FTP_USER = "AD\\rakf00"
FTP_PASS = os.getenv("FTP_PASS") 

# 📂 Složky
FTP_DIR_INPUT = "/HOME/rakf00/"
FTP_DIR_OUTPUT = "/HOME/rakf00/exty/"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 

FILE_TO_WATCH = "a.txt"
FILE_TO_CREATE = "data.txt"

# --- 2. Připojení k OpenAI ---
try:
    if not OPENAI_API_KEY:
        print("⚠️ VAROVÁNÍ: API klíč nebyl načten (zkontroluj .env).")
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"❌ Chyba při inicializaci OpenAI: {e}")
    exit()

def get_gpt_response(prompt):
    print("  🤖 Kontaktuji OpenAI API...")
    try:
        completion = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "Odpovídej stručně a k věci."},
                {"role": "user", "content": f"""
Pokud odpovědi mají písmena např. (A-D), použij je.
Pokud písmena chybí, přiřaď je v pořadí, jak odpovědi přicházejí.
Výstup vždy ve formátu:
číslo otázky: písmeno odpovědi. Např 1:A
...
Zadání:
{prompt}
"""}
            ]
        )
        print("  ✅ Odpověď od AI získána.")
        return completion.choices[0].message.content
    except Exception as e:
        print(f"  ❌ Chyba při volání OpenAI API: {e}")
        return None

# --- 3. Funkce pro připojení ---
def get_ftp_connection(directory):
    """Vytvoří a vrátí FTP spojení."""
    try:
        ftp = ftplib.FTP_TLS(FTP_HOST, FTP_USER, FTP_PASS, timeout=30)
        ftp.prot_p()
        ftp.set_pasv(True)
        if directory != "/":
            ftp.cwd(directory)
        return ftp
    except Exception as e:
        print(f"  ❌ Chyba připojení k FTP: {e}")
        return None

# --- 4. Hlavní smyčka ---
print(f"--- Spouštím OPRAVENÝ skript (Kódování FIX) ---")
print(f"Sleduji: {FTP_DIR_INPUT}{FILE_TO_WATCH}")

while True:
    obsah_promptu = None
    soubor_nalezen = False 

    # --- FÁZE 1: Kontrola a stažení ---
    print("\n🔍 Kontroluji server...")
    ftp = get_ftp_connection(FTP_DIR_INPUT)
    
    if ftp:
        try:
            file_list = ftp.nlst()
            if FILE_TO_WATCH in file_list:
                print(f"  📄 Soubor '{FILE_TO_WATCH}' nalezen. Stahuji...")
                mem_file = io.BytesIO()
                ftp.retrbinary(f'RETR {FILE_TO_WATCH}', mem_file.write)
                mem_file.seek(0)
                
                # --- OPRAVA KÓDOVÁNÍ (ZDE TO PADALO) ---
                raw_bytes = mem_file.getvalue()
                try:
                    # 1. Pokus o UTF-8
                    raw_content = raw_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # 2. Pokud selže, použij Windows-1250 (čeština)
                    print("  ⚠️ Detekováno starší kódování (Windows-1250), převádím...")
                    raw_content = raw_bytes.decode('windows-1250', errors='ignore')
                # ---------------------------------------

                if not raw_content or not raw_content.strip():
                    print(f"  ⚠️ Soubor je PRÁZDNÝ. Přeskakuji.")
                    soubor_nalezen = False
                else:
                    obsah_promptu = raw_content
                    soubor_nalezen = True
                    print(f"  📥 Staženo. Jdu zpracovat.")
            else:
                print(f"  💤 Soubor nenalezen.")
        except Exception as e:
            print(f"  ❌ Chyba FTP (čtení): {e}")
        finally:
            try: ftp.quit() 
            except: pass

    # --- FÁZE 2: Akce (Upload + Delete) ---
    if soubor_nalezen and obsah_promptu:
        response_text = get_gpt_response(obsah_promptu)

        if response_text:
            # 1. NAHRÁNÍ
            print("  🚀 Nahrávám výsledek...")
            try:
                ftp_out = get_ftp_connection(FTP_DIR_OUTPUT)
                response_file = io.BytesIO(response_text.encode('utf-8'))
                ftp_out.storbinary(f'STOR {FILE_TO_CREATE}', response_file)
                print(f"  💾 Soubor '{FILE_TO_CREATE}' nahrán.")
                ftp_out.quit()
            except Exception as e:
                print(f"  ❌ Chyba při nahrávání: {e}")

            # 2. SMAZÁNÍ (Natvrdo)
            print("  🗑️ Mažu vstupní soubor...")
            try:
                ftp_in = get_ftp_connection(FTP_DIR_INPUT)
                ftp_in.delete(FILE_TO_WATCH)
                print(f"  ✅ Soubor '{FILE_TO_WATCH}' SMAZÁN.")
                ftp_in.quit()
            except Exception as e:
                print(f"  ❌ Chyba při mazání: {e}")

    # --- Pauza ---
    print("⏳ Čekám 30s...")
    time.sleep(30)

