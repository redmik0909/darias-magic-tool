import json
import os
import re
import unicodedata
import urllib.request
import urllib.parse
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
ZONES_FILE = os.path.join(BASE_DIR, "zones.json")

# Données dans AppData — jamais écrasées lors des mises à jour
APP_DATA   = os.path.join(os.environ.get("APPDATA", BASE_DIR), "DariasMagicTool")
DATA_DIR   = os.path.join(APP_DATA, "rdv_data")
os.makedirs(DATA_DIR, exist_ok=True)

# Migration automatique — copie les anciens rdv_data vers AppData si nécessaire
_OLD_DATA_DIR = os.path.join(BASE_DIR, "rdv_data")
if os.path.exists(_OLD_DATA_DIR):
    import shutil
    for f in os.listdir(_OLD_DATA_DIR):
        old_f = os.path.join(_OLD_DATA_DIR, f)
        new_f = os.path.join(DATA_DIR, f)
        if os.path.isfile(old_f) and not os.path.exists(new_f):
            shutil.copy(old_f, new_f)

GEOCODIO_API_KEY  = "6426426bb3d928dc1be1c39e6633d8c8419e624"

def _load_locationiq_key():
    """Decrypt LocationIQ key from encrypted file using password from keyring."""
    try:
        import keyring
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        import base64

        enc_file  = os.path.join(BASE_DIR, "locationiq.enc")
        salt_file = os.path.join(BASE_DIR, "locationiq.salt")

        if not os.path.exists(enc_file) or not os.path.exists(salt_file):
            return ""

        pwd = keyring.get_password("DariasMagicTool", "locationiq_pwd")
        if not pwd:
            return ""

        with open(salt_file, "rb") as f:
            salt = f.read()
        with open(enc_file, "rb") as f:
            encrypted = f.read()

        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                          salt=salt, iterations=480000)
        key = base64.urlsafe_b64encode(kdf.derive(pwd.encode()))
        f   = Fernet(key)
        return f.decrypt(encrypted).decode()
    except Exception:
        return ""

def _locationiq_geocode(address, country="ca"):
    """Geocode using LocationIQ API. Returns raw result or None."""
    try:
        key = _load_locationiq_key()
        if not key:
            return None
        params = urllib.parse.urlencode({
            "key":             key,
            "q":               address,
            "countrycodes":    country,
            "addressdetails":  1,
            "format":          "json",
            "limit":           1,
            "accept-language": "fr",
        })
        url = f"https://us1.locationiq.com/v1/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "DariasMagicTool/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data and len(data) > 0:
            return data[0]
    except Exception:
        pass
    return None

# ── Text ───────────────────────────────────────────────────────────────────────
def normalize(text):
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[-–—']", " ", text)  # include apostrophe
    return re.sub(r"\s+", " ", text)

# ── Zones ──────────────────────────────────────────────────────────────────────
def load_zones():
    with open(ZONES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _get_mrc_for_city(city):
    """Ask Nominatim for the MRC/region of a city we don't recognize."""
    try:
        g = Nominatim(user_agent="darias_magic_tool_v2")
        loc = g.geocode(f"{city}, Québec, Canada", addressdetails=True, language="fr", timeout=10)
        if loc:
            addr = loc.raw.get("address", {})
            return (
                addr.get("county") or
                addr.get("state_district") or
                addr.get("state") or ""
            )
    except Exception:
        pass
    return ""


def _match_to_zone(text, data):
    """Try to match a text string to a zone using city list, MRC map, and region map."""
    if not text:
        return None
    norm = normalize(text)

    # Hors territoire
    for ht in data["hors_territoire"]:
        if norm == normalize(ht) or normalize(ht) in norm:
            return "hors_territoire"

    # City list
    for zone in data["zones"]:
        for ville in zone["villes"]:
            if norm == normalize(ville) or normalize(ville) in norm:
                return zone["id"]

    # MRC map
    for key, zid in MRC_MAP.items():
        if norm == key or key in norm or norm in key:
            return zid

    # Region map
    for key, zid in REGION_MAP.items():
        if norm == key or key in norm or norm in key:
            return zid

    return None


def find_zone(city, data):
    """
    city can be a plain city name OR a pipe-separated string:
    'city|county|region' returned by geocode_address.
    Tries each level until a zone is found.
    """
    # Parse pipe-separated levels if present
    parts = city.split("|") if "|" in city else [city, "", ""]
    city_name  = parts[0].strip() if len(parts) > 0 else city
    county     = parts[1].strip() if len(parts) > 1 else ""
    region     = parts[2].strip() if len(parts) > 2 else ""

    # Try each level
    for text in [city_name, county, region]:
        if not text:
            continue
        result = _match_to_zone(text, data)
        if result == "hors_territoire":
            return "hors_territoire", city_name
        if result:
            zone = next((z for z in data["zones"] if z["id"] == result), None)
            if zone:
                return zone, city_name or text

    return None, None

def get_all_reps(zones_data):
    seen, reps = set(), []
    for zone in zones_data["zones"]:
        for rep in zone["representants"]:
            if rep["nom"] not in seen:
                seen.add(rep["nom"])
                reps.append({"rep": rep, "zone": zone})
    return reps

# ── FSA → City map ─────────────────────────────────────────────────────────────
FSA_MAP = {
    "H7A": "Laval", "H7B": "Laval", "H7C": "Laval", "H7E": "Laval",
    "H7G": "Laval", "H7H": "Laval", "H7J": "Laval", "H7K": "Laval",
    "H7L": "Laval", "H7M": "Laval", "H7N": "Laval", "H7P": "Laval",
    "H7R": "Laval", "H7S": "Laval", "H7T": "Laval", "H7V": "Laval",
    "H7W": "Laval", "H7X": "Laval", "H7Y": "Laval",
    "H1A": "Montréal", "H1B": "Montréal", "H1C": "Montréal", "H1E": "Montréal",
    "H1G": "Montréal", "H1H": "Montréal", "H1J": "Montréal", "H1K": "Montréal",
    "H1L": "Montréal", "H1M": "Montréal", "H1N": "Montréal", "H1P": "Montréal",
    "H1R": "Montréal", "H1S": "Montréal", "H1T": "Montréal", "H1V": "Montréal",
    "H1W": "Montréal", "H1X": "Montréal", "H1Y": "Montréal", "H1Z": "Montréal",
    "H2A": "Montréal", "H2B": "Montréal", "H2C": "Montréal", "H2E": "Montréal",
    "H2G": "Montréal", "H2H": "Montréal", "H2J": "Montréal", "H2K": "Montréal",
    "H2L": "Montréal", "H2M": "Montréal", "H2N": "Montréal", "H2P": "Montréal",
    "H2R": "Montréal", "H2S": "Montréal", "H2T": "Montréal", "H2V": "Montréal",
    "H2W": "Montréal", "H2X": "Montréal", "H2Y": "Montréal", "H2Z": "Montréal",
    "H3A": "Montréal", "H3B": "Montréal", "H3C": "Montréal", "H3E": "Montréal",
    "H3G": "Montréal", "H3H": "Montréal", "H3J": "Montréal", "H3K": "Montréal",
    "H3L": "Montréal", "H3M": "Montréal", "H3N": "Montréal", "H3P": "Montréal",
    "H3R": "Montréal", "H3S": "Montréal", "H3T": "Montréal", "H3V": "Montréal",
    "H3W": "Montréal", "H3X": "Montréal", "H3Y": "Montréal", "H3Z": "Montréal",
    "H4A": "Montréal", "H4B": "Montréal", "H4C": "Montréal", "H4E": "Montréal",
    "H4G": "Montréal", "H4H": "Montréal", "H4J": "Montréal", "H4K": "Montréal",
    "H4L": "Montréal", "H4M": "Montréal", "H4N": "Montréal", "H4P": "Montréal",
    "H4R": "Montréal", "H4S": "Montréal", "H4T": "Montréal", "H4V": "Montréal",
    "H4W": "Montréal", "H4X": "Montréal", "H4Y": "Montréal", "H4Z": "Montréal",
    "H5A": "Montréal", "H5B": "Montréal",
    "H8N": "LaSalle", "H8P": "LaSalle", "H8R": "LaSalle", "H8S": "LaSalle",
    "H8T": "Lachine", "H8Y": "Kirkland", "H8Z": "Kirkland",
    "H9A": "Dollard-des-Ormeaux", "H9B": "Dollard-des-Ormeaux",
    "H9C": "Dollard-des-Ormeaux", "H9E": "Sainte-Anne-de-Bellevue",
    "H9G": "Beaconsfield", "H9H": "Beaconsfield", "H9J": "Kirkland",
    "H9K": "Pointe-Claire", "H9P": "Dorval", "H9R": "Pointe-Claire",
    "H9S": "Dorval", "H9W": "Senneville", "H9X": "Baie-d-Urfe",
    "J4G": "Longueuil", "J4H": "Longueuil", "J4J": "Longueuil", "J4K": "Longueuil",
    "J4L": "Longueuil", "J4M": "Longueuil", "J4N": "Longueuil",
    "J4V": "Saint-Hubert", "J4W": "Saint-Hubert", "J4X": "Saint-Hubert",
    "J4Y": "Saint-Hubert", "J4Z": "Brossard",
    "J4B": "Boucherville", "J4E": "Boucherville",
    "J3Y": "Saint-Jean-sur-Richelieu", "J3Z": "Saint-Jean-sur-Richelieu",
    "J3B": "Saint-Jean-sur-Richelieu",
    "J2W": "Saint-Hyacinthe", "J2S": "Saint-Hyacinthe", "J2T": "Saint-Hyacinthe",
    "J3E": "Chambly", "J3L": "Chambly",
    "J4T": "Saint-Bruno", "J3V": "Saint-Bruno",
    "J4S": "Greenfield Park",
    "J0L": "Hemmingford", "J0J": "Marieville",
    "J7G": "Saint-Eustache", "J7R": "Saint-Eustache",
    "J7E": "Deux-Montagnes",
    "J7C": "Mirabel", "J7J": "Mirabel", "J7N": "Mirabel",
    "J7Z": "Saint-Jérôme", "J5L": "Saint-Jérôme", "J7L": "Saint-Jérôme",
    "J6E": "Joliette", "J6K": "Joliette",
    "J7H": "Boisbriand", "J7W": "Blainville", "J7B": "Sainte-Thérèse",
    "J7A": "Rosemère",
    "J6V": "Saint-Lin-Laurentides",
    "J6W": "Mascouche",
    "J5W": "Terrebonne", "J6X": "Terrebonne", "J6Y": "Terrebonne",
    "J0N": "Sainte-Anne-des-Plaines", "J0R": "Saint-Sauveur",
    "J0K": "Saint-Felix-de-Valois",
    "J5T": "Lanoraie", "J0G": "Sorel-Tracy",
    "G1A": "Québec", "G1B": "Québec", "G1C": "Québec", "G1E": "Québec",
    "G1G": "Québec", "G1H": "Québec", "G1J": "Québec", "G1K": "Québec",
    "G1L": "Québec", "G1M": "Québec", "G1N": "Québec", "G1P": "Québec",
    "G1R": "Québec", "G1S": "Québec", "G1T": "Québec", "G1V": "Québec",
    "G1W": "Québec", "G1X": "Québec", "G1Y": "Québec",
    "G2A": "Québec", "G2B": "Québec", "G2C": "Québec", "G2E": "Québec",
    "G2G": "Québec", "G2J": "Québec", "G2K": "Québec", "G2L": "Québec",
    "G2M": "Québec", "G2N": "Québec",
    "G3A": "Québec", "G3B": "Québec", "G3C": "Québec", "G3E": "Québec",
    "G3G": "Québec", "G3J": "Québec", "G3K": "Québec",
    "G6V": "Lévis", "G6W": "Lévis", "G6X": "Lévis", "G6Z": "Lévis", "G7A": "Lévis",
    "G8T": "Trois-Rivières", "G8V": "Trois-Rivières", "G8W": "Trois-Rivières",
    "G8X": "Trois-Rivières", "G8Y": "Trois-Rivières", "G8Z": "Trois-Rivières",
    "G9A": "Trois-Rivières", "G9B": "Trois-Rivières",
    "G9N": "Shawinigan", "G9P": "Shawinigan",
    "J3T": "Nicolet", "G9H": "Bécancour",
    "J8L": "Gatineau", "J8M": "Gatineau", "J8P": "Gatineau", "J8R": "Gatineau",
    "J8T": "Gatineau", "J8V": "Gatineau", "J8X": "Gatineau", "J8Y": "Gatineau",
    "J8Z": "Gatineau", "J9A": "Gatineau", "J9H": "Gatineau", "J9J": "Gatineau",
    "J1E": "Sherbrooke", "J1G": "Sherbrooke", "J1H": "Sherbrooke",
    "J1J": "Sherbrooke", "J1K": "Sherbrooke", "J1L": "Sherbrooke",
    "J1M": "Sherbrooke", "J1N": "Sherbrooke", "J1R": "Sherbrooke",
    "J1X": "Magog",
    "J2G": "Granby", "J2H": "Granby",
    "G7G": "Chicoutimi", "G7H": "Chicoutimi", "G7J": "Chicoutimi",
    "G7K": "Chicoutimi", "G7S": "Chicoutimi", "G7T": "Chicoutimi",
    "G8B": "Alma", "G8C": "Alma", "G8E": "Alma",
    "J2A": "Drummondville", "J2B": "Drummondville", "J2C": "Drummondville",
    "G6P": "Victoriaville", "G6S": "Victoriaville", "G6T": "Victoriaville",
    "G6G": "Thetford Mines", "G6H": "Thetford Mines",
}

# ── MRC/Région → Zone mapping ─────────────────────────────────────────────────
# Quand une ville n'est pas trouvée directement, on utilise sa MRC ou région
MRC_MAP = {
    # Rive-Sud / Montérégie
    "marguerite-d'youville": "montreal_rive_sud",
    "marguerite d youville": "montreal_rive_sud",
    "roussillon": "montreal_rive_sud",
    "le haut-richelieu": "montreal_rive_sud",
    "haut-richelieu": "montreal_rive_sud",
    "la vallée-du-richelieu": "montreal_rive_sud",
    "vallee du richelieu": "montreal_rive_sud",
    "rouville": "montreal_rive_sud",
    "les maskoutains": "montreal_rive_sud",
    "maskoutains": "montreal_rive_sud",
    "brome-missisquoi": "montreal_rive_sud",
    "longueuil": "montreal_rive_sud",
    "agglomération de longueuil": "montreal_rive_sud",
    "vaudreuil-soulanges": "montreal_rive_sud",
    "beauharnois-salaberry": "montreal_rive_sud",
    "le haut-saint-laurent": "montreal_rive_sud",
    "haut saint laurent": "montreal_rive_sud",
    "montérégie": "montreal_rive_sud",
    "monteregie": "montreal_rive_sud",
    # Rive-Nord / Laurentides / Laval
    "thérèse-de-blainville": "rive_nord",
    "therese de blainville": "rive_nord",
    "deux-montagnes": "rive_nord",
    "mirabel": "rive_nord",
    "la rivière-du-nord": "rive_nord",
    "riviere du nord": "rive_nord",
    "laurentides": "rive_nord",
    "les laurentides": "rive_nord",
    "argenteuil": "rive_nord",
    "laval": "rive_nord",
    "les moulins": "rive_nord",
    "l'assomption": "rive_nord",
    "assomption": "rive_nord",
    # Lanaudière / TR
    "joliette": "lanaudiere_tr",
    "d'autray": "lanaudiere_tr",
    "autray": "lanaudiere_tr",
    "matawinie": "lanaudiere_tr",
    "montcalm": "lanaudiere_tr",
    "les moulins": "lanaudiere_tr",
    "lanaudière": "lanaudiere_tr",
    "lanaudiere": "lanaudiere_tr",
    "francheville": "lanaudiere_tr",
    "maskinongé": "lanaudiere_tr",
    "maskinonge": "lanaudiere_tr",
    "bécancour": "lanaudiere_tr",
    "becancour": "lanaudiere_tr",
    "nicolet-yamaska": "lanaudiere_tr",
    "mauricie": "lanaudiere_tr",
    # Québec / Lévis
    "québec": "quebec",
    "communauté métropolitaine de québec": "quebec",
    "lévis": "quebec",
    "levis": "quebec",
    "la côte-de-beaupré": "quebec",
    "cote de beaupre": "quebec",
    "l'île-d'orléans": "quebec",
    "ile d orleans": "quebec",
    "portneuf": "quebec",
    "charlevoix": "quebec",
    "chaudière-appalaches": "quebec",
    "chaudiere appalaches": "quebec",
    "bellechasse": "quebec",
    "la nouvelle-beauce": "sherbrooke_beauce",
    "robert-cliche": "sherbrooke_beauce",
    "beauce-sartigan": "sherbrooke_beauce",
    # Gatineau / Outaouais
    "gatineau": "gatineau",
    "les collines-de-l'outaouais": "gatineau",
    "collines de l outaouais": "gatineau",
    "papineau": "gatineau",
    "outaouais": "gatineau",
    "pontiac": "gatineau",
    # Sherbrooke / Estrie
    "sherbrooke": "sherbrooke_beauce",
    "memphrémagog": "sherbrooke_beauce",
    "memphremagog": "sherbrooke_beauce",
    "le val-saint-françois": "sherbrooke_beauce",
    "val saint francois": "sherbrooke_beauce",
    "coaticook": "sherbrooke_beauce",
    "le haut-saint-françois": "sherbrooke_beauce",
    "haut saint francois": "sherbrooke_beauce",
    "estrie": "sherbrooke_beauce",
    "granit": "sherbrooke_beauce",
    # Saguenay
    "saguenay": "saguenay",
    "lac-saint-jean-est": "saguenay",
    "lac saint jean est": "saguenay",
    "domaine-du-roy": "saguenay",
    "domaine du roy": "saguenay",
    "maria-chapdelaine": "saguenay",
    "le fjord-du-saguenay": "saguenay",
    "fjord du saguenay": "saguenay",
    "saguenay-lac-saint-jean": "saguenay",
}

# ── Région administrative → Zone mapping ──────────────────────────────────────
REGION_MAP = {
    # Montérégie → Rive-Sud
    "monteregie": "montreal_rive_sud",
    "montérégie": "montreal_rive_sud",
    # Laval → Rive-Nord
    "laval": "rive_nord",
    # Laurentides → Rive-Nord
    "laurentides": "rive_nord",
    "les laurentides": "rive_nord",
    # Lanaudière → Lanaudière/TR
    "lanaudiere": "lanaudiere_tr",
    "lanaudière": "lanaudiere_tr",
    # Mauricie → Lanaudière/TR
    "mauricie": "lanaudiere_tr",
    "la mauricie": "lanaudiere_tr",
    # Centre-du-Québec → Sherbrooke/Beauce
    "centre-du-quebec": "sherbrooke_beauce",
    "centre du quebec": "sherbrooke_beauce",
    "centre-du-québec": "sherbrooke_beauce",
    # Estrie → Sherbrooke/Beauce
    "estrie": "sherbrooke_beauce",
    # Chaudière-Appalaches → Québec
    "chaudiere-appalaches": "quebec",
    "chaudière-appalaches": "quebec",
    "chaudiere appalaches": "quebec",
    # Capitale-Nationale → Québec
    "capitale-nationale": "quebec",
    "capitale nationale": "quebec",
    # Saguenay-Lac-Saint-Jean → Saguenay
    "saguenay-lac-saint-jean": "saguenay",
    "saguenay lac saint jean": "saguenay",
    # Outaouais → Gatineau
    "outaouais": "gatineau",
    # Montréal → Montréal/Rive-Sud
    "montreal": "montreal_rive_sud",
    "montréal": "montreal_rive_sud",
}

# ── Geocoding ──────────────────────────────────────────────────────────────────
def _resolve_postal_code(postal_code):
    """Resolve postal code to (city, display_address)."""
    clean     = postal_code.replace(" ", "").upper()
    formatted = clean[:3] + " " + clean[3:]
    fsa       = clean[:3]

    if fsa in FSA_MAP:
        city = FSA_MAP[fsa]
        return city, f"{formatted}, {city}, Québec, Canada"

    try:
        g   = Nominatim(user_agent="darias_magic_tool_v2")
        loc = g.geocode(f"{formatted}, Canada", addressdetails=True,
                        language="fr", timeout=10)
        if loc:
            addr = loc.raw.get("address", {})
            city = (addr.get("city") or addr.get("town") or
                    addr.get("village") or addr.get("municipality") or "")
            if city:
                return city, loc.address
    except Exception:
        pass

    return None, None


def _parse_pasted_address(address):
    """
    Parse pasted addresses like:
    '189 RUE DES MARGUERITESSAINT-AMABLE QC  J0L 1N0'
    Returns cleaned address string for Nominatim.
    """
    addr = address.strip()

    # Extract postal code
    postal_match = re.search(r'([A-Z][0-9][A-Z])\s*([0-9][A-Z][0-9])', addr.upper())
    postal = None
    if postal_match:
        postal = postal_match.group(1) + postal_match.group(2)
        # Remove postal code from address
        addr = addr[:postal_match.start()].strip()

    # Remove province code (QC, ON, etc.)
    addr = re.sub(r'\s+[A-Z]{2}\s*$', '', addr.strip())

    # Add comma and Quebec for Nominatim
    if postal:
        return f"{addr}, Quebec, Canada", postal
    return f"{addr}, Quebec, Canada", None


def geocode_address(address):
    """Returns (city, full_address) or (None, None). Used by Accueil page."""
    clean     = address.replace(" ", "").upper()
    is_postal = bool(re.match(r"^[A-Z][0-9][A-Z][0-9][A-Z][0-9]$", clean))

    if is_postal:
        city, display = _resolve_postal_code(clean)
        return (city, display) if city else (None, None)

    # Parse pasted address format
    cleaned_addr, postal = _parse_pasted_address(address)

    g = Nominatim(user_agent="darias_magic_tool_v2")
    queries = [cleaned_addr]
    if postal:
        # Also try with just the postal code as fallback
        fsa = postal[:3]
        if fsa in FSA_MAP:
            city_from_fsa = FSA_MAP[fsa]
            queries.append(f"{cleaned_addr.split(',')[0]}, {city_from_fsa}, Quebec, Canada")
    queries += [address + ", Québec, Canada", address + ", Canada"]
    for query in queries:
        try:
            loc = g.geocode(query, addressdetails=True, language="fr", timeout=10)
            if loc:
                addr = loc.raw.get("address", {})

                # On retourne toutes les infos utiles séparées par |
                # pour que find_zone puisse essayer chaque niveau
                city    = (addr.get("city") or addr.get("town") or
                           addr.get("village") or addr.get("hamlet") or
                           addr.get("municipality") or addr.get("suburb") or "")
                county  = addr.get("county") or ""
                region  = addr.get("state_district") or addr.get("state") or ""

                # On retourne city|county|region comme identifiant
                # find_zone va essayer chaque niveau
                combined = city or county or region
                if combined:
                    return f"{city}|{county}|{region}", loc.address

        except (GeocoderTimedOut, GeocoderServiceError):
            continue
    return None, None


def geocode_coords(address):
    """
    Returns (lat, lon, display_name) or None. Used by Route page.
    - Postal codes → Geocodio
    - Addresses    → Nominatim (sans filtre country_codes)
    """
    clean     = address.replace(" ", "").upper()
    is_postal = bool(re.match(r"^[A-Z][0-9][A-Z][0-9][A-Z][0-9]$", clean))

    if is_postal:
        formatted = clean[:3] + " " + clean[3:]
        try:
            params = urllib.parse.urlencode({
                "q": formatted + ", Canada",
                "api_key": GEOCODIO_API_KEY,
                "country": "CA",
                "limit": 1,
            })
            url = "https://api.geocod.io/v1.7/geocode?" + params
            req = urllib.request.Request(url, headers={"User-Agent": "darias_magic_tool_v2"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            results = data.get("results", [])
            if results:
                loc     = results[0]
                lat     = loc["location"]["lat"]
                lon     = loc["location"]["lng"]
                display = loc.get("formatted_address", formatted)
                return lat, lon, display
        except Exception:
            pass

        fsa  = clean[:3]
        city = FSA_MAP.get(fsa)
        if city:
            try:
                g   = Nominatim(user_agent="darias_magic_tool_v2")
                loc = g.geocode(f"{city}, Quebec, Canada", timeout=10)
                if loc:
                    return loc.latitude, loc.longitude, f"{formatted}, {city}, Quebec"
            except Exception:
                pass
        return None

    # Adresse normale — LocationIQ
    for query in [address + ", Canada", address]:
        result = _locationiq_geocode(query)
        if result:
            lat     = float(result.get("lat", 0))
            lon     = float(result.get("lon", 0))
            display = result.get("display_name", address)
            if lat and lon:
                return lat, lon, display

    return None


# ── OSRM Routing ───────────────────────────────────────────────────────────────
def osrm_route(coords):
    """Returns (duration_matrix, order, total_seconds, geometry) or (None,None,None,None)."""
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)

    table_url = (f"https://router.project-osrm.org/table/v1/driving/{coord_str}"
                 f"?annotations=duration")
    try:
        with urllib.request.urlopen(table_url, timeout=15) as r:
            table_data = json.loads(r.read())
        durations = table_data.get("durations", [])
    except Exception:
        return None, None, None, None

    trip_url = (f"https://router.project-osrm.org/trip/v1/driving/{coord_str}"
                f"?roundtrip=false&source=first&annotations=duration")
    try:
        with urllib.request.urlopen(trip_url, timeout=15) as r:
            trip_data = json.loads(r.read())
    except Exception:
        return durations, list(range(len(coords))), None, None

    waypoints = trip_data.get("waypoints", [])
    order     = [wp["waypoint_index"] for wp in waypoints]
    trips     = trip_data.get("trips", [])
    total     = trips[0]["duration"] if trips else None
    geometry  = trips[0].get("geometry") if trips else None

    return durations, order, total, geometry


def decode_polyline(encoded):
    """Decode Google encoded polyline to list of (lat, lon)."""
    coords = []
    index, lat, lng = 0, 0, 0
    while index < len(encoded):
        b, shift, result = 0, 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat
        shift, result = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if result & 1 else result >> 1
        lng += dlng
        coords.append((lat / 1e5, lng / 1e5))
    return coords


# ── RDV Storage ────────────────────────────────────────────────────────────────
def rep_data_file(rep_nom):
    safe = re.sub(r"[^a-z0-9]", "_", normalize(rep_nom))
    return os.path.join(DATA_DIR, f"{safe}.json")

def load_rep_rdv(rep_nom):
    f = rep_data_file(rep_nom)
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return {}

def save_rep_rdv(rep_nom, data):
    with open(rep_data_file(rep_nom), "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)