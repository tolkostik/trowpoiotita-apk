"""
Προφίλ υγείας και σύγκριση προϊόντων.

ΠΡΟΣΟΧΗ: οι ειδοποιήσεις βασίζονται στα στοιχεία της βάσης και στα συστατικά.
Για σοβαρές αλλεργίες ελέγχεις πάντα και την ετικέτα της συσκευασίας.
"""
import json
import re

import food as F

ALLERGEN_KEYS = ["milk", "gluten", "eggs", "nuts", "peanuts", "soybeans", "fish", "crustaceans", "molluscs",
                 "celery", "mustard", "sesame-seeds", "sulphur-dioxide-and-sulphites", "lupin"]

# λέξεις στα συστατικά που δείχνουν αλλεργιογόνο, όταν λείπουν οι ετικέτες της βάσης
ALLERGEN_WORDS = {
    "milk": ("γάλα", "γάλακτος", "βούτυρο", "τυρί", "κρέμα γάλακτος", "γιαούρτ", "ορός γάλακτος", "λακτόζη",
             "καζεΐν", "milk", "butter", "cheese", "cream", "whey", "lactose", "casein"),
    "gluten": ("σίτ", "σιτάρ", "αλεύρι", "κριθάρ", "σίκαλη", "βρώμη", "ζέα", "γλουτένη", "σιμιγδάλ",
               "wheat", "barley", "rye", "oat", "spelt", "gluten", "semolina"),
    "eggs": ("αυγ", "αβγ", "egg"),
    "nuts": ("αμύγδαλ", "καρύδ", "φουντούκ", "κάσιου", "φιστίκι αιγίνης", "πεκάν", "μακαντάμια",
             "almond", "walnut", "hazelnut", "cashew", "pistachio", "pecan", "macadamia"),
    "peanuts": ("αράπικο φιστίκι", "αράπικα φιστίκια", "φυστικοβούτυρο", "peanut"),
    "soybeans": ("σόγια", "soy", "soja"),
    "fish": ("ψάρι", "τόνος", "σολομ", "σαρδέλ", "γαύρο", "μπακαλιάρ", "fish", "tuna", "salmon", "anchov"),
    "crustaceans": ("γαρίδ", "καβούρ", "αστακ", "shrimp", "prawn", "crab", "lobster", "crustacean"),
    "molluscs": ("μύδι", "χταπόδ", "καλαμάρ", "σουπι", "στρείδ", "mussel", "squid", "octopus", "oyster", "mollusc"),
    "celery": ("σέλινο", "celery"),
    "mustard": ("μουστάρδ", "σινάπ", "mustard"),
    "sesame-seeds": ("σουσάμ", "ταχίνι", "sesame", "tahini"),
    "sulphur-dioxide-and-sulphites": ("θειώδ", "sulphite", "sulfite", "e220", "e221", "e222", "e223", "e224",
                                      "e226", "e227", "e228"),
    "lupin": ("λούπιν", "lupin"),
}
MEAT_FISH_CATS = ("en:meats", "en:meat", "en:fishes", "en:seafood", "en:sausages", "en:hams", "en:poultries")

DIETS = [("vegan", "Vegan"), ("vegetarian", "Χορτοφάγος"), ("celiac", "Χωρίς γλουτένη (κοιλιοκάκη)"),
         ("lactose", "Δυσανεξία στη λακτόζη"), ("diabetes", "Διαβήτης (λίγη ζάχαρη)"),
         ("hypertension", "Υπέρταση (λίγο αλάτι)"), ("cholesterol", "Χοληστερίνη (λίγα κορεσμένα)"),
         ("palm", "Αποφυγή φοινικέλαιου"), ("additives", "Αποφυγή προσθέτων με επιφυλάξεις")]

PROFILE_FILE = "profile.json"


def load_profile():
    try:
        return json.loads((F.DATA_DIR / PROFILE_FILE).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"allergens": [], "diets": []}


def save_profile(prof):
    F.DATA_DIR.mkdir(parents=True, exist_ok=True)
    F._save(PROFILE_FILE, prof)


def _nut(p, key):
    return F._num(p.get("nutriments") or {}, key)


def _salt(p):
    s = _nut(p, "salt_100g")
    if s is None:
        na = _nut(p, "sodium_100g")
        s = na * 2.5 if na is not None else None
    return s


def detect_allergens(p):
    """{αλλεργιογόνο: 'περιέχει' | 'ίχνη' | 'πιθανό'}"""
    out = {}
    for t in F._tags(p.get("allergens_tags")):
        out[t] = "περιέχει"
    for t in F._tags(p.get("traces_tags")):
        out.setdefault(t, "ίχνη")
    text = F.ingredients_text(p).lower()
    if text:
        for key, words in ALLERGEN_WORDS.items():
            if key not in out and any(w in text for w in words):
                out[key] = "πιθανό"
    return out


def check(p, prof=None):
    """Επιστρέφει λίστα (επίπεδο, μήνυμα): επίπεδο 'red' (ακατάλληλο), 'orange' (προσοχή), 'info'."""
    prof = prof or load_profile()
    alerts = []
    al = detect_allergens(p)
    has_info = bool(p.get("allergens_tags") or p.get("traces_tags") or F.ingredients_text(p))
    for key in prof.get("allergens", []):
        name = F.ALLERGENS.get(key, key)
        st = al.get(key)
        if st == "περιέχει":
            alerts.append(("red", f"Περιέχει {name}"))
        elif st == "πιθανό":
            alerts.append(("red", f"Πιθανόν περιέχει {name} (από τα συστατικά)"))
        elif st == "ίχνη":
            alerts.append(("orange", f"Μπορεί να περιέχει ίχνη: {name}"))
    if prof.get("allergens") and not has_info:
        alerts.append(("orange", "Δεν υπάρχουν στοιχεία για αλλεργιογόνα: έλεγξε την ετικέτα"))

    diets = set(prof.get("diets", []))
    an = p.get("ingredients_analysis_tags") or []
    cats = p.get("categories_tags") or []
    labels = p.get("labels_tags") or []
    animal = any(c in cats for c in MEAT_FISH_CATS)
    if "vegan" in diets:
        if "en:non-vegan" in an or animal or any(k in al for k in ("milk", "eggs", "fish", "crustaceans", "molluscs")):
            alerts.append(("red", "Δεν είναι vegan"))
        elif "en:maybe-vegan" in an or "en:vegan-status-unknown" in an:
            alerts.append(("orange", "Ίσως να μην είναι vegan: έλεγξε τα συστατικά"))
    if "vegetarian" in diets:
        if "en:non-vegetarian" in an or animal or any(k in al for k in ("fish", "crustaceans", "molluscs")):
            alerts.append(("red", "Δεν είναι χορτοφαγικό"))
    if "celiac" in diets and "gluten" not in prof.get("allergens", []):
        st = al.get("gluten")
        gf = any(x in labels for x in ("en:gluten-free", "en:no-gluten"))
        if st in ("περιέχει", "πιθανό") and not gf:
            alerts.append(("red", "Περιέχει γλουτένη"))
        elif st == "ίχνη" and not gf:
            alerts.append(("orange", "Μπορεί να περιέχει ίχνη γλουτένης"))
    if "lactose" in diets and "milk" not in prof.get("allergens", []):
        if al.get("milk") in ("περιέχει", "πιθανό") and "en:lactose-free" not in labels:
            alerts.append(("orange", "Περιέχει γάλα (λακτόζη)"))
    sug, salt, sat = _nut(p, "sugars_100g"), _salt(p), _nut(p, "saturated-fat_100g")
    bev = F.is_beverage(p)
    if "diabetes" in diets and sug is not None:
        hi, mid = (5.0, 2.5) if bev else (12.5, 5.0)
        if sug > hi:
            alerts.append(("red", f"Πολλή ζάχαρη: {F._n(sug, False)} g/100{'ml' if bev else 'g'}"))
        elif sug > mid:
            alerts.append(("orange", f"Μέτρια ζάχαρη: {F._n(sug, False)} g/100{'ml' if bev else 'g'}"))
    if "hypertension" in diets and salt is not None:
        if salt > 1.5:
            alerts.append(("red", f"Πολύ αλάτι: {F._n(salt, False)} g/100 g"))
        elif salt > 0.6:
            alerts.append(("orange", f"Μέτριο αλάτι: {F._n(salt, False)} g/100 g"))
    if "cholesterol" in diets and sat is not None:
        if sat > 5:
            alerts.append(("red", f"Πολλά κορεσμένα λιπαρά: {F._n(sat, False)} g/100 g"))
        elif sat > 1.5:
            alerts.append(("orange", f"Μέτρια κορεσμένα λιπαρά: {F._n(sat, False)} g/100 g"))
    if "palm" in diets and ("en:palm-oil" in an or "φοινικέλαι" in F.ingredients_text(p).lower()):
        alerts.append(("red", "Περιέχει φοινικέλαιο"))
    if "additives" in diets:
        bad = [c.upper() for c in F.additive_codes(p) if "en:" + c in F.CONCERN]
        if bad:
            alerts.append(("red", "Πρόσθετα με επιφυλάξεις: " + ", ".join(bad)))
    return alerts


def worst(alerts):
    lv = {a[0] for a in alerts}
    return "red" if "red" in lv else ("orange" if "orange" in lv else None)


# ------------------------------------------------------------------ ποσότητα & τιμή ανά κιλό
_Q_RX = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|κιλ\w*|ml|cl|lt|λίτρ\w*|gr|γραμ\w*|γρ\w*|g|l|λ)"
                   r"(?![a-z])", re.I)


def quantity(p):
    """Ποσότητα σε κιλά ή λίτρα: (τιμή, 'kg' | 'l') ή None."""
    q = (p.get("quantity") or "").lower().replace("ℓ", "l")
    m = _Q_RX.search(q)
    if not m:
        return None
    n = int(m.group(1)) if m.group(1) else 1
    v = float(m.group(2).replace(",", ".")) * n
    u = m.group(3).lower()
    if u == "kg" or u.startswith("κιλ"):
        return v, "kg"
    if u in ("g", "gr") or u.startswith(("γρ", "γραμ")):
        return v / 1000, "kg"
    if u in ("l", "lt", "λ") or u.startswith("λίτρ"):
        return v, "l"
    if u == "ml":
        return v / 1000, "l"
    if u == "cl":
        return v / 100, "l"
    return None


def per_unit(price, p):
    q = quantity(p)
    if not q or q[0] <= 0:
        return None
    return price / q[0], q[1]


def best_price(p):
    rows = F.prices_for(p.get("code"))
    return rows[0] if rows else None


# ------------------------------------------------------------------ σύγκριση
def compare_rows(a, b):
    """Γραμμές σύγκρισης: (ετικέτα, κείμενο Α, κείμενο Β, ποιο είναι καλύτερο: 'a'|'b'|None)."""
    rows = []

    def add(label, va, vb, fmt, lower_better=True):
        ta = fmt(va) if va is not None else "–"
        tb = fmt(vb) if vb is not None else "–"
        win = None
        if va is not None and vb is not None and abs(va - vb) > 1e-9:
            win = ("a" if va < vb else "b") if lower_better else ("a" if va > vb else "b")
        rows.append((label, ta, tb, win))

    sa, sb = F.score(a)[0], F.score(b)[0]
    add("Βαθμός", sa, sb, lambda v: F._n(v, False), lower_better=False)
    ga, gb = (a.get("nutriscore_grade") or "").upper(), (b.get("nutriscore_grade") or "").upper()
    rows.append(("Nutri-Score", ga or "–", gb or "–",
                 None if not (ga and gb) or ga == gb else ("a" if ga < gb else "b")))
    na, nb = a.get("nova_group"), b.get("nova_group")
    try:
        na, nb = (int(na) if na else None), (int(nb) if nb else None)
    except (TypeError, ValueError):
        na = nb = None
    add("Επεξεργασία (NOVA)", na, nb, lambda v: str(int(v)))

    def kcal(p):
        v = _nut(p, "energy-kcal_100g")
        if v is None:
            kj = _nut(p, "energy_100g")
            v = kj / 4.184 if kj is not None else None
        return v
    add("Ενέργεια /100", kcal(a), kcal(b), lambda v: f"{v:.0f} kcal")
    for label, key in (("Ζάχαρη /100", "sugars_100g"), ("Κορεσμένα /100", "saturated-fat_100g")):
        add(label, _nut(a, key), _nut(b, key), lambda v: F._n(v, False) + " g")
    add("Αλάτι /100", _salt(a), _salt(b), lambda v: F._n(v, False) + " g")
    add("Φυτικές ίνες /100", _nut(a, "fiber_100g"), _nut(b, "fiber_100g"), lambda v: F._n(v, False) + " g", False)
    add("Πρωτεΐνες /100", _nut(a, "proteins_100g"), _nut(b, "proteins_100g"), lambda v: F._n(v, False) + " g", False)
    add("Πρόσθετα", len(F.additive_codes(a)), len(F.additive_codes(b)), lambda v: str(int(v)))
    rows.append(("Ποσότητα", a.get("quantity") or "–", b.get("quantity") or "–", None))
    pa, pb = best_price(a), best_price(b)
    add("Φθηνότερη τιμή", pa["price"] if pa else None, pb["price"] if pb else None,
        lambda v: f"{v:.2f} €".replace(".", ","))
    ua = per_unit(pa["price"], a) if pa else None
    ub = per_unit(pb["price"], b) if pb else None
    same_unit = ua and ub and ua[1] == ub[1]
    add("Τιμή ανά κιλό/λίτρο", ua[0] if ua else None, ub[0] if ub else None,
        lambda v: f"{v:.2f} €".replace(".", ","))
    if ua and ub and not same_unit:
        rows[-1] = (rows[-1][0], rows[-1][1], rows[-1][2], None)
    al_a, al_b = check(a), check(b)
    rows.append(("Ειδοποιήσεις προφίλ", str(len(al_a)) if al_a else "καμία", str(len(al_b)) if al_b else "καμία",
                 None if len(al_a) == len(al_b) else ("a" if len(al_a) < len(al_b) else "b")))
    return rows


def verdict(a, b):
    sa, sb = F.score(a)[0], F.score(b)[0]
    parts = []
    if sa is not None and sb is not None and abs(sa - sb) >= 0.1:
        parts.append(f"Καλύτερη ποιότητα: {'Α' if sa > sb else 'Β'}")
    pa, pb = best_price(a), best_price(b)
    ua = per_unit(pa["price"], a) if pa else None
    ub = per_unit(pb["price"], b) if pb else None
    if ua and ub and ua[1] == ub[1] and abs(ua[0] - ub[0]) > 0.005:
        parts.append(f"Οικονομικότερο ανά {'κιλό' if ua[1] == 'kg' else 'λίτρο'}: {'Α' if ua[0] < ub[0] else 'Β'}")
    return " · ".join(parts)


# ------------------------------------------------------------------ λίστα σύγκρισης
def load_compare():
    try:
        return json.loads((F.DATA_DIR / "compare.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def add_compare(p):
    lst = [x for x in load_compare() if x.get("code") != p.get("code")]
    lst.append(p)
    lst = lst[-2:]
    F.DATA_DIR.mkdir(parents=True, exist_ok=True)
    F._save("compare.json", lst)
    return lst


def clear_compare():
    F._save("compare.json", [])
