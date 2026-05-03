# 🎟 SYSTÈME DE CONTRÔLE D'ACCÈS — DOCUMENTATION TECHNIQUE

## Architecture du Système

```
┌─────────────────────────────────────────────────────────────┐
│  GÉNÉRATION (1x avant l'événement)                          │
│  Python → 1000 UUID+HMAC → Supabase + QR Images PNG (300DPI)│
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  SUPABASE (Temps Réel)                                       │
│  bracelets / scan_logs / staff + RLS + Fonction Atomique    │
└──────┬──────────────────────────────────────┬───────────────┘
       │                                      │
┌──────▼───────┐                    ┌─────────▼───────────────┐
│ scanner.html │                    │     admin.html          │
│ Smartphone   │                    │  Dashboard Temps Réel   │
│ Staff x N    │                    │  Admin seulement        │
└──────────────┘                    └─────────────────────────┘
```

---

## 1. SÉCURITÉ — Comment les faux QR codes sont impossibles

### Mécanisme HMAC-SHA256
```
Format du token: {uuid4}:{hmac_sha256(uuid4, SECRET_KEY)}

Exemple:
  uuid = "550e8400-e29b-41d4-a716-446655440000"
  token = "550e8400-e29b-41d4-a716-446655440000:a3f9b2c1d4e5..."

Forger un token = trouver la clé HMAC sans la connaître
→ Computationnellement impossible (SHA-256 est une fonction à sens unique)
```

### Défenses en couches
| Couche | Protection |
|--------|-----------|
| UUID v4 | 2^122 possibilités → impossible à deviner |
| HMAC-SHA256 | Signature cryptographique → impossible à forger |
| `UNIQUE` SQL | Impossible d'insérer deux fois le même token |
| `FOR UPDATE NOWAIT` | Élimine la race condition entre 2 scanners |
| RLS Supabase | Seul le staff authentifié peut interagir |
| Service Key | La génération ne peut venir que du backend |

---

## 2. INSTALLATION

### Prérequis
```bash
pip install qrcode[pil] supabase python-dotenv pillow pandas openpyxl
```

### Configuration
```bash
cp .env.example .env
# Remplir SUPABASE_URL, SUPABASE_SERVICE_KEY, SECRET_HMAC_KEY
```

### Génération des bracelets
```bash
python generate_qr.py
```
→ Crée `qr_output/B-0001.png` à `B-1000.png` (300 DPI)
→ Insère 1000 tokens dans Supabase
→ Génère `IMPRIMEUR_bracelets_manifest.csv`

---

## 3. SETUP SUPABASE

### Étapes Dashboard Supabase
1. Créer un projet Supabase
2. **SQL Editor** → Coller et exécuter `supabase_schema.sql`
3. **Authentication → Providers** → Activer Email
4. **Database → Replication** → Activer les tables `bracelets` et `scan_logs`
5. Créer les comptes staff via **Authentication → Users**
6. Insérer dans la table `staff` avec leur `user_id`

### Créer un compte staff (SQL)
```sql
-- Après avoir créé l'utilisateur via Auth dashboard:
INSERT INTO staff (user_id, display_name, role)
VALUES ('UUID_DE_LUSER_AUTH', 'Prénom Nom', 'scanner');

-- Pour un admin:
INSERT INTO staff (user_id, display_name, role)
VALUES ('UUID_DE_LUSER_AUTH', 'Admin Principal', 'admin');
```

---

## 4. INSTRUCTIONS POUR L'IMPRIMEUR

### Format de livraison
Envoyer le fichier `IMPRIMEUR_bracelets_manifest.csv` à l'imprimeur.

**Colonnes du CSV :**
| Colonne | Description |
|---------|-------------|
| `bracelet_num` | Numéro visible sur le bracelet (ex: 0042) |
| `qr_data` | Contenu EXACT à encoder dans le QR code |
| `qr_filename` | Fichier image correspondant (ex: B-0042.png) |
| `checksum` | 8 derniers caractères pour vérification rapide |

**Exigences techniques :**
- QR code version auto, correction d'erreur **niveau H (30%)**
- Résolution minimum : **300 DPI**
- Module minimum : **0.3mm** (pour résistance aux griffures/eau)
- **Vérification** : L'imprimeur doit scanner 5% des bracelets avant livraison et confirmer le checksum

**Vérification post-livraison :**
```bash
# Vérifier l'intégrité du CSV livré
sha256sum IMPRIMEUR_bracelets_manifest.csv
# Comparer avec le hash dans INTEGRITY_checksums.json
```

---

## 5. MODE DÉGRADÉ (Offline)

Si le réseau est coupé pendant l'événement :
- Les scans sont stockés localement (localStorage)
- L'interface affiche "HORS LIGNE" en orange
- Les doublons déjà scannés en session locale sont détectés
- À la reconnexion, synchronisation automatique vers Supabase

**Limitation offline** : Si deux smartphones scannent le même bracelet quand les deux sont offline, le doublon ne sera détecté qu'à la synchronisation. Prévoyez du WiFi fiable aux entrées.

---

## 6. DÉPLOIEMENT

### Option A : Pages statiques (recommandé)
Héberger `scanner.html` et `admin.html` sur :
- Netlify Drop (gratuit, glisser-déposer)
- Vercel
- GitHub Pages

### Option B : Local (réseau interne)
```bash
python -m http.server 8080
# Accès: http://192.168.x.x:8080/scanner.html
```

### Checklist pré-événement
- [ ] Bracelets générés et vérifiés
- [ ] Supabase schema appliqué
- [ ] Comptes staff créés et testés
- [ ] Connexion Realtime activée
- [ ] Test de scan sur 5 bracelets
- [ ] Test mode offline (couper WiFi)
- [ ] Batterie téléphones staff > 80%
- [ ] URL scanner.html en favoris sur chaque téléphone

---

## 7. FICHIERS DU PROJET

```
bracelet-system/
├── generate_qr.py          # Script Python génération
├── supabase_schema.sql     # Schema SQL + RLS + Fonctions
├── scanner.html            # Interface scan staff (mobile)
├── admin.html              # Dashboard admin temps réel
├── .env.example            # Template configuration
└── qr_output/              # (généré) Images PNG + CSV imprimeur
    ├── B-0001.png
    ├── ...
    ├── B-1000.png
    ├── IMPRIMEUR_bracelets_manifest.csv
    ├── BACKUP_admin_bracelets.xlsx
    └── INTEGRITY_checksums.json
```
