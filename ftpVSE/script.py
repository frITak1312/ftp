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
    ftp = None
    soubor_nalezen = False
    obsah_promptu = None

    # --- FÁZE 1: Kontrola a stažení ---
    try:
        print("\nKontroluji server (vstupní složku)...")
        ftp = get_ftp_connection(FTP_DIR_INPUT)
        print("  Připojeno (fáze 1).")

        file_list = ftp.nlst()

        if FILE_TO_WATCH in file_list:
            print(f"  [NALEZENO] Soubor '{FILE_TO_WATCH}'. Stahuji...")
            mem_file = io.BytesIO()
            ftp.retrbinary(f'RETR {FILE_TO_WATCH}', mem_file.write)
            mem_file.seek(0)
            obsah_promptu = mem_file.getvalue().decode('utf-8')
            soubor_nalezen = True
            print(f"  Staženo {len(obsah_promptu)} znaků.")
        else:
            print(f"  Soubor '{FILE_TO_WATCH}' nenalezen. Čekám.")

    except (*ftplib.all_errors, socket.timeout) as e:
        print(f"  [CHYBA FÁZE 1] {e}. Zkouším znovu za 30s.")
    finally:
        if ftp:
            ftp.close()
            print("  Spojení (fáze 1) uzavřeno.")

    # --- FÁZE 2: OpenAI a Nahrání ---
    if soubor_nalezen and obsah_promptu:
        response_text = get_gpt_response(obsah_promptu)

        if response_text:
            ftp_upload = None
            try:
                print("  Připojuji se (fáze 2) pro nahrání...")
                ftp_upload = get_ftp_connection(FTP_DIR_OUTPUT)

                response_file = io.BytesIO(response_text.encode('utf-8'))

                try:
                    ftp_upload.delete(FILE_TO_CREATE)
                except Exception:
                    pass  # Pokud neexistuje, nevadí

                print(f"  Nahrávám '{FILE_TO_CREATE}' do {FTP_DIR_OUTPUT}...")
                try:
                    ftp_upload.storbinary(f'STOR {FILE_TO_CREATE}', response_file)
                    print(f"  Soubor '{FILE_TO_CREATE}' úspěšně nahrán.")
                except socket.timeout:
                    print(f"  [INFO] 'storbinary' timeout, ale soubor je pravděpodobně nahrán.")

                ftp_upload.close()
                print("  Spojení (fáze 2) uzavřeno.")

                time.sleep(2)
                ftp_delete = None
                try:
                    print("  Připojuji se (fáze 3) pro mazání vstupního souboru...")
                    ftp_delete = get_ftp_connection(FTP_DIR_INPUT)
                    ftp_delete.delete(FILE_TO_WATCH)
                    print(f"  [ÚSPĚCH] Původní soubor '{FILE_TO_WATCH}' smazán.")
                    print("-" * 20)
                except (*ftplib.all_errors, socket.timeout) as e:
                    print(f"  [CHYBA FÁZE 3] Nepodařilo se smazat '{FILE_TO_WATCH}': {e}")
                finally:
                    if ftp_delete:
                        ftp_delete.close()
                        print("  Spojení (fáze 3) uzavřeno.")

            except (*ftplib.all_errors, socket.timeout) as e:
                print(f"  [CHYBA FÁZE 2] {e}. Soubor 'a.txt' NEBYL smazán.")
            finally:
                if ftp_upload and ftp_upload.sock:
                    ftp_upload.close()
                    print("  Spojení (fáze 2) nouzově uzavřeno.")
        else:
            print("  Chyba OpenAI, 'a.txt' nebude smazán. Zkouším znovu za 30s.")

    # --- Pauza ---
    time.sleep(30)

