import ftplib
import time
from openai import OpenAI
from dotenv import load_dotenv
import io
import os
import socket  # Důležité pro zachycení 'timeout'


load_dotenv()


# --- 1. Nastavení ---
FTP_HOST = "webdisk.vse.cz"
FTP_USER = "AD\\rakf00"
FTP_PASS = os.getenv("FTP_PASS")  # Získejte heslo z proměnné prostředí

# 📂 Složky pro vstup a výstup
FTP_DIR_INPUT = "/HOME/rakf00/"
FTP_DIR_OUTPUT = "/HOME/rakf00/exty/"

OPENAI_API_KEY = os.getenv("OPEN_API_KEY")  # Získejte OpenAI API klíč z proměnné prostředí

FILE_TO_WATCH = "a.txt"
FILE_TO_CREATE = "data.txt"

# --- 2. Připojení k OpenAI ---
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Chyba při inicializaci OpenAI (zkontrolujte API klíč): {e}")
    exit()


def get_gpt_response(prompt):
    """Pošle text na API OpenAI a vrátí odpověď."""
    print("  Kontaktuji OpenAI API...")
    try:
        completion = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "Odpovídej stručně a k věci."},
                {"role": "user", "content": f"""
Pokud odpovědi mají písmena (A-D), použij je.
Pokud písmena chybí, přiřaď je v pořadí, jak odpovědi přicházejí.
Výstup vždy ve formátu:
1:A
2:B
...
{prompt}
"""}
            ]
        )
        print("  Odpověď od AI získána.")
        return completion.choices[0].message.content
    except Exception as e:
        print(f"  Chyba při volání OpenAI API: {e}")
        return None


# --- 3. Funkce pro připojení ---
def get_ftp_connection(directory):
    """Vytvoří, nastaví a vrátí nové FTP spojení."""
    ftp = ftplib.FTP_TLS(FTP_HOST, FTP_USER, FTP_PASS, timeout=30)
    ftp.prot_p()
    ftp.set_pasv(True)
    if directory != "/":
        ftp.cwd(directory)
    return ftp


# --- 4. Hlavní smyčka ---
print(f"--- Spouštím finální skript (v. 8) ---")
print(f"Sleduji soubor '{FILE_TO_WATCH}' ve složce: {FTP_DIR_INPUT}")
print(f"Výstupy se budou ukládat do: {FTP_DIR_OUTPUT}")

while True:
    obsah_promptu = None
    soubor_nalezen = False # Defaultně false, dokud nepotvrdíme, že má obsah

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
                raw_content = mem_file.getvalue().decode('utf-8')

                # --- ZDE JE TA ZMĚNA ---
                if not raw_content or not raw_content.strip():
                    print(f"  ⚠️ Soubor '{FILE_TO_WATCH}' je PRÁZDNÝ. Přeskakuji a zkusím to za 30s.")
                    soubor_nalezen = False # Explicitně říkáme, že nemáme co zpracovat
                else:
                    obsah_promptu = raw_content
                    soubor_nalezen = True
                    print(f"  📥 Staženo {len(obsah_promptu)} znaků. Jdu zpracovat.")
                # -----------------------

            else:
                print(f"  💤 Soubor '{FILE_TO_WATCH}' nenalezen.")
        except Exception as e:
            print(f"  ❌ Chyba při čtení FTP: {e}")
        finally:
            try: ftp.quit()
            except: pass

    # --- FÁZE 2: Zpracování a nahrání (Pouze pokud NENÍ prázdný) ---
    if soubor_nalezen and obsah_promptu:
        response_text = get_gpt_response(obsah_promptu)

        if response_text:
            print("  🚀 Připojuji se pro nahrání výsledku...")
            ftp_upload = get_ftp_connection(FTP_DIR_OUTPUT)

            if ftp_upload:
                try:
                    response_file = io.BytesIO(response_text.encode('utf-8'))
                    ftp_upload.storbinary(f'STOR {FILE_TO_CREATE}', response_file)
                    print(f"  💾 Soubor '{FILE_TO_CREATE}' úspěšně nahrán.")
                    try: ftp_upload.quit()
                    except: pass

                    # --- FÁZE 3: Mazání vstupu ---
                    print("  🗑️ Mazání původního souboru...")
                    ftp_delete = get_ftp_connection(FTP_DIR_INPUT)
                    if ftp_delete:
                        ftp_delete.delete(FILE_TO_WATCH)
                        print(f"  ✅ Soubor '{FILE_TO_WATCH}' smazán.")
                        try: ftp_delete.quit()
                        except: pass

                except Exception as e:
                    print(f"  ❌ Chyba při nahrávání/mazání: {e}")
                    try: ftp_upload.close()
                    except: pass

    # --- Pauza ---
    print("⏳ Čekám 30s...")
    time.sleep(30)


