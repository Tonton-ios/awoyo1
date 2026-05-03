"""
=============================================================
  SYSTÈME DE BILLETTERIE - GÉNÉRATEUR QR CODES SÉCURISÉS
  Stack: Python + Supabase + qrcode + uuid + hmac
=============================================================
  pip install qrcode[pil] supabase python-dotenv pillow pandas openpyxl
"""

import uuid
import hmac
import hashlib
import os
import json
import csv
import qrcode
import pandas as pd
from datetime import datetime
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ───────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Service role key (backend only!)
SECRET_HMAC_KEY = os.getenv("SECRET_HMAC_KEY", "CHANGE_THIS_TO_A_STRONG_SECRET_64_CHARS_MIN")
TOTAL_BRACELETS = 1070
OUTPUT_DIR = Path("./qr_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── SÉCURITÉ : SIGNATURE HMAC ────────────────────────────
def generate_secure_token(uid: str) -> str:
    """
    Génère un token signé HMAC-SHA256.
    Format final: {uid}:{signature_hex}
    - Impossible à forger sans la clé secrète
    - UUID v4 garantit l'unicité
    - HMAC garantit l'authenticité
    """
    signature = hmac.new(
        SECRET_HMAC_KEY.encode(),
        uid.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{uid}:{signature}"

def verify_token(token: str) -> tuple[bool, str]:
    """Vérifie l'intégrité d'un token. Retourne (valid, uid)."""
    try:
        uid, sig = token.rsplit(":", 1)
        expected_sig = hmac.new(
            SECRET_HMAC_KEY.encode(),
            uid.encode(),
            hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(sig, expected_sig):
            return True, uid
        return False, ""
    except Exception:
        return False, ""

# ─── GÉNÉRATION QR CODES ──────────────────────────────────
def generate_qr_image(token: str, bracelet_num: int) -> Path:
    """Génère une image QR code haute qualité pour impression."""
    qr = qrcode.QRCode(
        version=None,          # Auto-détection taille optimale
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30% correction d'erreur
        box_size=12,
        border=4,
    )
    qr.add_data(token)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Naming: B-0001.png → B-1000.png
    filename = OUTPUT_DIR / f"B-{bracelet_num:04d}.png"
    img.save(filename, dpi=(300, 300))  # 300 DPI pour impression
    return filename

# ─── INSERTION SUPABASE EN BATCH ──────────────────────────
def insert_batch_to_supabase(records: list[dict], client: Client):
    """Insère par batch de 100 pour optimiser les performances."""
    BATCH_SIZE = 100
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        result = client.table("bracelets").insert(batch).execute()
        print(f"  ✓ Batch {i//BATCH_SIZE + 1}: {len(batch)} bracelets insérés")
    return True

# ─── EXPORT POUR IMPRIMEUR ────────────────────────────────
def export_for_printer(records: list[dict]):
    """
    Génère un fichier CSV pour l'imprimeur.
    Colonnes: bracelet_num, token (données QR), qr_filename
    NE PAS partager la colonne uid seule - toujours le token complet.
    """
    export_data = [
        {
            "bracelet_num": r["bracelet_num"],
            "qr_data": r["token"],           # Contenu exact à encoder dans le QR
            "qr_filename": f"B-{r['bracelet_num']:04d}.png",
            "checksum": r["token"][-8:],     # 8 derniers chars pour vérification rapide
        }
        for r in records
    ]
    
    # CSV pour imprimeur
    csv_path = OUTPUT_DIR / "IMPRIMEUR_bracelets_manifest.csv"
    df = pd.DataFrame(export_data)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    
    # Excel pour backup lisible
    xlsx_path = OUTPUT_DIR / "BACKUP_admin_bracelets.xlsx"
    admin_df = pd.DataFrame(records)
    admin_df.to_excel(xlsx_path, index=False)
    
    print(f"\n📄 Export imprimeur → {csv_path}")
    print(f"💾 Backup admin     → {xlsx_path}")
    
    # Vérification d'intégrité: hash du fichier
    with open(csv_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    print(f"🔐 SHA-256 du CSV   : {file_hash}")
    
    integrity_path = OUTPUT_DIR / "INTEGRITY_checksums.json"
    with open(integrity_path, "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat(),
            "total_bracelets": TOTAL_BRACELETS,
            "csv_sha256": file_hash,
            "secret_key_hint": SECRET_HMAC_KEY[:4] + "..." + SECRET_HMAC_KEY[-4:]
        }, f, indent=2)

# ─── MAIN ─────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  GÉNÉRATION DES BRACELETS QR CODES SÉCURISÉS")
    print(f"  Quantité: {TOTAL_BRACELETS} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️  Variables SUPABASE_URL / SUPABASE_SERVICE_KEY manquantes dans .env")
        print("   → Mode LOCAL SEULEMENT (pas d'insertion Supabase)")
    
    supabase_client = None
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✓ Connexion Supabase établie\n")
    except Exception as e:
        print(f"⚠️  Supabase non connecté: {e}\n")

    records = []
    print("📦 Génération des tokens et QR codes...")
    
    for i in range(1, TOTAL_BRACELETS + 1):
        uid = str(uuid.uuid4())
        token = generate_secure_token(uid)
        
        # Génération image QR
        qr_path = generate_qr_image(token, i)
        
        records.append({
            "uid": uid,
            "token": token,
            "bracelet_num": i,
            "scanned": False,
            "scanned_at": None,
            "scanned_by": None,
            "created_at": datetime.utcnow().isoformat(),
        })
        
        if i % 100 == 0:
            print(f"  → {i}/{TOTAL_BRACELETS} générés...")

    print(f"\n✓ {TOTAL_BRACELETS} QR codes générés dans {OUTPUT_DIR}/")

    # Insertion Supabase
    if supabase_client:
        print("\n⬆️  Insertion dans Supabase...")
        insert_batch_to_supabase(records, supabase_client)
        print("✓ Insertion terminée!")

    # Export fichiers
    print("\n📁 Export des fichiers...")
    export_for_printer(records)

    print("\n" + "=" * 60)
    print("  ✅ GÉNÉRATION COMPLÈTE")
    print(f"  {TOTAL_BRACELETS} bracelets prêts pour impression")
    print("=" * 60)

if __name__ == "__main__":
    main()
