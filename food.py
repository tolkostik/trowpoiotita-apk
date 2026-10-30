"""
Ποιότητα τροφίμων από το barcode, με βαθμό 1–10 (ένα δεκαδικό).

Πηγή: Open Food Facts (ανοιχτή βάση, δωρεάν, χωρίς εγγραφή).
Ο βαθμός είναι διατροφικός και βγαίνει με διαφανή τρόπο:
  βάση από τους πόντους του Nutri-Score, μέσα στη ζώνη του γράμματός του
  (A 8,6–10 · B 7,2–8,5 · C 5,0–7,1 · D 3,0–4,9 · E 1,0–2,9)
  + επεξεργασία NOVA (1: +0,6 · 2: +0,3 · 3: 0 · 4: −0,8)
  − πρόσθετα (−0,15 το καθένα, έως −0,9) και πρόσθετα με επιφυλάξεις (−0,4, έως −1,2)
  − φοινικέλαιο (−0,3) · + βιολογικό (+0,2)
Αν λείπει το Nutri-Score, υπολογίζεται από τον διατροφικό πίνακα (μέτρια αξιοπιστία)
ή εκτιμάται από τα συστατικά (χαμηλή αξιοπιστία).
"""
import datetime
import json
import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path


def _n(x, sign=True):
    if abs(x) < 0.005:
        return "0"
    t = f"{x:+.2f}" if sign else f"{x:.2f}"
    t = t.rstrip("0").rstrip(".").replace(".", ",").replace("-", "−")
    return t


UA = "PoiotitaTrofimon/1.0 (Android; personal use)"
FIELDS = ("code,product_name,product_name_el,generic_name,generic_name_el,brands,quantity,nutriscore_grade,"
          "nutriscore_score,nutriscore_data,nova_group,additives_tags,additives_n,nutriments,categories_tags,"
          "image_front_small_url,image_front_url,ingredients_text_el,ingredients_text,ingredients_n,"
          "allergens_tags,traces_tags,labels_tags,ingredients_analysis_tags,origins,manufacturing_places,"
          "countries_tags,ecoscore_grade,environmental_score_grade,packaging,serving_size,stores,emb_codes,"
          "unique_scans_n,completeness,ecoscore_data,environmental_score_data,nutrient_levels")
PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=" + FIELDS
SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl?"
EKATANALOTIS = "https://e-katanalotis.gov.gr/"

GRADE_BASE = {"a": 9.0, "b": 7.5, "c": 6.0, "d": 4.0, "e": 2.0}
GRADE_TEXT = {"a": "A (εξαιρετικό)", "b": "B (καλό)", "c": "C (μέτριο)", "d": "D (φτωχό)", "e": "E (κακό)"}
NOVA_ADJ = {1: 1.0, 2: 0.5, 3: 0.0, 4: -1.0}
NOVA_TEXT = {1: "1 – ανεπεξέργαστο", 2: "2 – βασικό υλικό μαγειρικής", 3: "3 – επεξεργασμένο",
             4: "4 – υπερεπεξεργασμένο"}
# πρόσθετα για τα οποία υπάρχουν αξιόλογες επιφυλάξεις (νιτρώδη, αζωχρωστικές, κ.ά.)
CONCERN = {"en:e249", "en:e250", "en:e251", "en:e252", "en:e102", "en:e104", "en:e110", "en:e122",
           "en:e124", "en:e129", "en:e171", "en:e320", "en:e321", "en:e951", "en:e950", "en:e954",
           "en:e621", "en:e338", "en:e407"}

DATA_DIR = Path.home() / ".poiotita"


def set_dir(p):
    global DATA_DIR
    DATA_DIR = Path(p)


def _get(url, timeout=25):
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def clean_code(code):
    return "".join(ch for ch in str(code) if ch.isdigit())


def fetch_product(code):
    code = clean_code(code)
    if len(code) < 6:
        raise ValueError("Ο κωδικός barcode δεν είναι σωστός.")
    mine = local_product(code)
    if mine:
        return mine
    js = _get(PRODUCT_URL.format(code=code))
    if js.get("status") != 1 or not js.get("product"):
        return None
    p = js["product"]
    p["code"] = p.get("code") or code
    return p


def search(term, greece_only=True, page_size=25):
    q = {"search_terms": term, "search_simple": 1, "action": "process", "json": 1,
         "page_size": page_size, "fields": FIELDS, "sort_by": "unique_scans_n"}
    if greece_only:
        q.update({"tagtype_0": "countries", "tag_contains_0": "contains", "tag_0": "greece"})
    js = _get(SEARCH_URL + urllib.parse.urlencode(q))
    return js.get("products", [])


# ------------------------------------------------------------------ βαθμός
def name_of(p):
    n = p.get("product_name_el") or p.get("product_name") or p.get("generic_name") or "Άγνωστο προϊόν"
    b = (p.get("brands") or "").split(",")[0].strip()
    q = p.get("quantity") or ""
    return " ".join(x for x in (n, f"– {b}" if b and b.lower() not in n.lower() else "", q) if x).strip()


# ζώνες βαθμού ανά γράμμα Nutri-Score: (πόντοι από, έως) -> (βαθμός από, έως)
_FOOD_BANDS = {"a": ((-15, -1), (10.0, 8.6)), "b": ((0, 2), (8.5, 7.2)), "c": ((3, 10), (7.1, 5.0)),
               "d": ((11, 18), (4.9, 3.0)), "e": ((19, 40), (2.9, 1.0))}
_BEV_BANDS = {"a": ((-20, 0), (10.0, 8.6)), "b": ((-10, 1), (8.5, 7.2)), "c": ((2, 5), (7.1, 5.0)),
              "d": ((6, 9), (4.9, 3.0)), "e": ((10, 25), (2.9, 1.0))}
_ULTRA_WORDS = ("σιρόπι γλυκόζης", "σιρόπι φρουκτόζης", "glucose syrup", "fructose syrup", "γλυκόζη-φρουκτόζη",
                "αρώματα", "άρωμα", "flavouring", "flavoring", "υδρογονωμέν", "hydrogenated", "φοινικέλαι",
                "palm oil", "γλυκαντικ", "sweetener", "τροποποιημένο άμυλο", "modified starch", "μαλτοδεξτρίνη",
                "maltodextrin", "ενισχυτικ", "flavour enhancer", "χρωστικ", "colour", "color", "γαλακτωματοποιητ",
                "emulsifier", "πρωτεΐνη ορού γάλακτος", "whey protein isolate", "ιμβερτοποιημένο", "dextrose",
                "δεξτρόζη")
_E_RX = re.compile(r"\b[EΕ]\s?-?(\d{3,4}[a-fA-F]?)\b")


def is_beverage(p):
    if p.get("beverage"):
        return True
    nd = p.get("nutriscore_data") or {}
    if nd.get("is_beverage") in (1, True, "1"):
        return True
    tags = p.get("categories_tags") or []
    return "en:beverages" in tags and "en:plant-based-milk-alternatives" not in tags


def _num(n, *keys):
    for k in keys:
        v = n.get(k)
        try:
            if v is not None and v != "":
                return float(v)
        except (TypeError, ValueError):
            continue
    return None


def nutriscore_from_nutriments(p):
    n = p.get("nutriments") or {}
    kcal = _num(n, "energy-kcal_100g")
    if kcal is None:
        kj = _num(n, "energy_100g", "energy-kj_100g")
        kcal = kj / 4.184 if kj is not None else None
    sug = _num(n, "sugars_100g")
    sat = _num(n, "saturated-fat_100g")
    salt = _num(n, "salt_100g")
    if salt is None:
        na = _num(n, "sodium_100g")
        salt = na * 2.5 if na is not None else None
    if None in (kcal, sug, sat, salt):
        return None
    fib = _num(n, "fiber_100g") or 0.0
    pro = _num(n, "proteins_100g") or 0.0
    fr = _num(n, "fruits-vegetables-nuts-estimate-from-ingredients_100g", "fruits-vegetables-nuts_100g",
              "fruits-vegetables-legumes-estimate-from-ingredients_100g") or 0.0
    return nutriscore(kcal, sug, sat, salt, fib, pro, fr, is_beverage(p))


def _band(grade, pts, beverage):
    (plo, phi), (shi, slo) = (_BEV_BANDS if beverage else _FOOD_BANDS)[grade]
    if pts is None:
        return (shi + slo) / 2
    t = 0.0 if phi == plo else (pts - plo) / (phi - plo)
    t = max(0.0, min(1.0, t))
    return shi - t * (shi - slo)


def ingredients_text(p):
    return (p.get("ingredients_text_el") or p.get("ingredients_text") or "").strip()


def additive_codes(p):
    codes = {x.split(":")[-1].lower() for x in (p.get("additives_tags") or [])}
    for m in _E_RX.findall(ingredients_text(p)):
        codes.add("e" + m.lower())
    return sorted(codes, key=lambda c: (len(c), c))


def score_details(p):
    """Λεπτομερής βαθμός 1–10 με ένα δεκαδικό, εξηγήσεις και αξιοπιστία."""
    why = []
    bev = is_beverage(p)
    grade = (p.get("nutriscore_grade") or "").lower()
    pts = p.get("nutriscore_score", p.get("nutriscore_points"))
    try:
        pts = float(pts) if pts is not None else None
    except (TypeError, ValueError):
        pts = None
    source = None
    if grade in GRADE_BASE:
        base, source = _band(grade, pts, bev), "high"
        why.append(f"Nutri-Score {GRADE_TEXT[grade]}" + (f", {int(pts)} πόντοι" if pts is not None else "")
                   + f": βάση {_n(round(base, 1), False)}")
    else:
        calc = nutriscore_from_nutriments(p)
        if calc:
            grade, pts = calc
            base, source = _band(grade, pts, bev), "medium"
            why.append(f"Nutri-Score υπολογισμένο από τον διατροφικό πίνακα: {GRADE_TEXT[grade]}, "
                       f"{int(pts)} πόντοι: βάση {_n(round(base, 1), False)}")
    text = ingredients_text(p).lower()
    codes = additive_codes(p)
    if source is None:
        if not text and not codes and p.get("nova_group") in (None, ""):
            return {"score": None, "why": ["Δεν υπάρχουν διατροφικά στοιχεία ούτε συστατικά για βαθμολογία. "
                                           "Μπορείς να προσθέσεις τα στοιχεία της ετικέτας."],
                    "confidence": None}
        base, source = 6.0, "low"
        why.append("Χωρίς διατροφικό πίνακα: εκτίμηση από τα συστατικά, βάση 6")
    # επεξεργασία
    nova = p.get("nova_group")
    try:
        nova = int(nova)
    except (TypeError, ValueError):
        nova = None
    ultra = [w for w in _ULTRA_WORDS if w in text]
    estimated = False
    if nova is None and (text or codes):
        estimated = True
        n_ingr = len([x for x in re.split(r"[,;]", text) if x.strip()]) if text else 0
        nova = 4 if (ultra or len(codes) >= 2) else (1 if n_ingr <= 1 else 3)
    adj = {1: 0.6, 2: 0.3, 3: 0.0, 4: -0.8}.get(nova, 0.0) * (0.5 if estimated else 1.0)
    s = base + adj
    if nova in NOVA_TEXT:
        why.append(f"Επεξεργασία NOVA {NOVA_TEXT[nova]}{' (εκτίμηση)' if estimated else ''}: {_n(adj)}")
    if source == "low" and ultra:
        u = -min(1.2, 0.3 * len(ultra))
        s += u
        why.append(f"Σημάδια υπερεπεξεργασίας στα συστατικά ({len(ultra)}): {_n(u)}")
    if codes:
        a = -min(0.9, 0.15 * len(codes))
        s += a
        why.append(f"{len(codes)} {'πρόσθετο' if len(codes) == 1 else 'πρόσθετα'}: {_n(a)}")
        bad = [c for c in codes if "en:" + c in CONCERN]
        if bad:
            b = -min(1.2, 0.4 * len(bad))
            s += b
            why.append(f"Πρόσθετα με επιφυλάξεις ({', '.join(c.upper() for c in bad)}): {_n(b)}")
    elif source != "low":
        why.append("Χωρίς πρόσθετα")
    analysis = p.get("ingredients_analysis_tags") or []
    if "en:palm-oil" in analysis:
        s -= 0.3
        why.append("Περιέχει φοινικέλαιο: −0,3")
    labels = p.get("labels_tags") or []
    if any(x in labels for x in ("en:organic", "en:eu-organic")):
        s += 0.2
        why.append("Βιολογικό: +0,2")
    s = round(max(1.0, min(10.0, s)), 1)
    conf = {"high": "υψηλή", "medium": "μέτρια", "low": "χαμηλή (εκτίμηση)"}[source]
    return {"score": s, "why": why, "confidence": conf}


def score(p):
    d = score_details(p)
    return d["score"], d["why"]


def nutrient_lights(p):
    """Φανάρια ανά 100 g: ζάχαρη, αλάτι, κορεσμένα λιπαρά, λιπαρά."""
    n = p.get("nutriments") or {}
    spec = [("Ζάχαρη", "sugars_100g", 5, 22.5), ("Αλάτι", "salt_100g", 0.3, 1.5),
            ("Κορεσμένα λιπαρά", "saturated-fat_100g", 1.5, 5), ("Λιπαρά", "fat_100g", 3, 17.5)]
    out = []
    for label, key, low, high in spec:
        v = n.get(key)
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        level = "χαμηλή" if v <= low else ("υψηλή" if v > high else "μέτρια")
        out.append((label, v, level))
    return out


def verdict(s):
    if s is None:
        return "Χωρίς βαθμό"
    if s >= 9.3:
        return "Εξαιρετικό"
    if s >= 8.5:
        return "Άριστο"
    if s >= 7:
        return "Πολύ καλό"
    if s >= 5.5:
        return "Μέτριο"
    if s >= 4:
        return "Φτωχό"
    return "Κακό"


# ------------------------------------------------------------------ ιστορικό
def load_history():
    return _load("history.json", [])


def add_history(p, s):
    h = [x for x in load_history() if x.get("code") != p.get("code")]
    h.insert(0, {"code": p.get("code"), "name": name_of(p), "score": s,
                 "when": datetime.datetime.now().strftime("%d/%m %H:%M")})
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _save("history.json", h[:200])


# ------------------------------------------------------------------ Nutri-Score από την ετικέτα
_FOOD_E = [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]
_FOOD_S = [4.5, 9, 13.5, 18, 22.5, 27, 31, 36, 40, 45]
_BEV_E = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270]
_BEV_S = [0, 1.5, 3, 4.5, 6, 7.5, 9, 10.5, 12, 13.5]
_SAT = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
_NA = [90, 180, 270, 360, 450, 540, 630, 720, 810, 900]
_FIB = [0.9, 1.9, 2.8, 3.7, 4.7]
_PRO = [1.6, 3.2, 4.8, 6.4, 8.0]


def _pts(v, thr):
    return sum(1 for t in thr if v > t)


def nutriscore(kcal, sugars, satfat, salt, fiber=0.0, protein=0.0, fruit_pct=0.0, beverage=False):
    """Nutri-Score (αλγόριθμος FSA/Santé publique France) ανά 100 g ή 100 ml. Επιστρέφει (γράμμα, πόντοι)."""
    kj = kcal * 4.184
    neg = (_pts(kj, _BEV_E if beverage else _FOOD_E) + _pts(sugars, _BEV_S if beverage else _FOOD_S)
           + _pts(satfat, _SAT) + _pts(salt * 400, _NA))
    if beverage:
        fr = 10 if fruit_pct > 80 else (4 if fruit_pct > 60 else (2 if fruit_pct > 40 else 0))
    else:
        fr = 5 if fruit_pct > 80 else (2 if fruit_pct > 60 else (1 if fruit_pct > 40 else 0))
    fib, pro = _pts(fiber, _FIB), _pts(protein, _PRO)
    full_fruit = fr >= (10 if beverage else 5)
    pos = fr + fib + (pro if (neg < 11 or full_fruit) else 0)
    s = neg - pos
    if beverage:
        g = "b" if s <= 1 else ("c" if s <= 5 else ("d" if s <= 9 else "e"))
    else:
        g = "a" if s <= -1 else ("b" if s <= 2 else ("c" if s <= 10 else ("d" if s <= 18 else "e")))
    return g, s


CATEGORIES = ["Γαλακτοκομικά", "Τυριά", "Κρέας & αλλαντικά", "Ψάρια", "Ψωμί & αρτοσκευάσματα",
              "Δημητριακά", "Ζυμαρικά, ρύζι & όσπρια", "Μπισκότα & γλυκά", "Σνακ", "Λάδι & λίπη",
              "Κονσέρβες & έτοιμα", "Ροφήματα & αναψυκτικά", "Χυμοί", "Καφές & τσάι", "Άλλο"]
_CAT_KEYS = [("Γαλακτοκομικά", ("dairies", "milk", "yogurt", "yoghurt")), ("Τυριά", ("cheese",)),
             ("Κρέας & αλλαντικά", ("meat", "sausage", "ham")), ("Ψάρια", ("fish", "seafood")),
             ("Ψωμί & αρτοσκευάσματα", ("bread", "bakery")), ("Δημητριακά", ("cereal", "breakfast")),
             ("Ζυμαρικά, ρύζι & όσπρια", ("pasta", "rice", "legume", "pulses")),
             ("Μπισκότα & γλυκά", ("biscuit", "cookie", "chocolate", "sweet", "confection")),
             ("Σνακ", ("snack", "chips", "crisps")), ("Λάδι & λίπη", ("oil", "fats", "butter")),
             ("Χυμοί", ("juice",)), ("Καφές & τσάι", ("coffee", "tea")),
             ("Ροφήματα & αναψυκτικά", ("beverage", "drink", "soda", "water"))]


def category_of(p):
    if p.get("category") in CATEGORIES:
        return p["category"]
    tags = " ".join(p.get("categories_tags") or []).lower()
    for cat, keys in _CAT_KEYS:
        if any(k in tags for k in keys):
            return cat
    return "Άλλο"


# ------------------------------------------------------------------ δικά μου προϊόντα
import os as _os
import threading as _threading

_IO_LOCK = _threading.RLock()


def _load(name, default):
    with _IO_LOCK:
        try:
            return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return default


def _save(name, data):
    """Ασφαλής εγγραφή: πρώτα σε προσωρινό αρχείο και μετά αντικατάσταση, με κλείδωμα για τα παράλληλα νήματα.
    Έτσι ένα αρχείο δεν «χαλάει» ποτέ μισογραμμένο, ακόμα κι αν κλείσει απότομα η εφαρμογή."""
    with _IO_LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = DATA_DIR / (name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        _os.replace(tmp, DATA_DIR / name)


def local_product(code):
    return _load("my_products.json", {}).get(clean_code(code))


def save_local_product(code, name, brand, quantity, category, beverage, kcal, sugars, satfat, salt,
                       fiber, protein, fruit_pct, nova, additives_text):
    code = clean_code(code)
    grade, pts = nutriscore(kcal, sugars, satfat, salt, fiber, protein, fruit_pct, beverage)
    adds = []
    for tok in additives_text.replace(";", ",").replace(" ", ",").split(","):
        t = tok.strip().lower().replace("ε", "e")
        if t:
            adds.append("en:" + (t if t.startswith("e") else "e" + t))
    p = {"code": code, "product_name": name, "brands": brand, "quantity": quantity, "category": category,
         "nutriscore_grade": grade, "nutriscore_points": pts, "nova_group": nova, "additives_tags": adds,
         "nutriments": {"energy-kcal_100g": kcal, "sugars_100g": sugars, "saturated-fat_100g": satfat,
                        "salt_100g": salt, "fiber_100g": fiber, "proteins_100g": protein},
         "local": True, "beverage": beverage}
    db = _load("my_products.json", {})
    db[code] = p
    _save("my_products.json", db)
    return p


def off_add_url(code):
    return f"https://world.openfoodfacts.org/cgi/product.pl?type=add&code={clean_code(code)}"


# ------------------------------------------------------------------ τιμές
STORES = ["ΑΒ Βασιλόπουλος", "Σκλαβενίτης", "Lidl", "My Market", "Μασούτης", "Κρητικός", "Γαλαξίας",
          "Market In", "Bazaar", "Discount Markt", "Χαλκιαδάκης", "Άλλο"]


def add_price(p, store, region, price):
    """Καταγράφει τιμή. Επιστρέφει λίστα μηνυμάτων (ακρίβυνε/φθήνυνε/χαμηλότερη που έχεις δει)."""
    price = round(float(price), 2)
    code = p.get("code")
    prices = _load("prices.json", [])
    old_same = next((x for x in prices if x["code"] == code and x["store"] == store
                     and x.get("region", "") == region), None)
    hist = price_history(code)
    msgs = []

    def e(x):
        return f"{x:.2f}".replace(".", ",") + " €"
    if old_same and abs(old_same["price"] - price) >= 0.01:
        diff = price - old_same["price"]
        pct = diff / old_same["price"] * 100 if old_same["price"] else 0
        word = "ακρίβυνε" if diff > 0 else "φθήνυνε"
        msgs.append(("up" if diff > 0 else "down",
                     f"Στο {store} {word} κατά {e(abs(diff))} ({pct:+.0f}%) από την τελευταία φορά "
                     f"({e(old_same['price'])}, {old_same['date']})."))
    if hist:
        lo = min(h["price"] for h in hist)
        if price < lo - 0.005:
            msgs.append(("best", f"Η χαμηλότερη τιμή που έχεις δει ποτέ για αυτό το προϊόν (πριν: {e(lo)})."))
        elif price > lo * 1.15:
            msgs.append(("up", f"Είναι {((price / lo) - 1) * 100:.0f}% πάνω από τη χαμηλότερη που έχεις δει "
                               f"({e(lo)})."))
    prices = [x for x in prices if x is not old_same]
    now = datetime.datetime.now()
    prices.append({"code": code, "name": name_of(p), "category": category_of(p),
                   "score": score(p)[0], "store": store, "region": region, "price": price,
                   "date": now.strftime("%d/%m/%Y")})
    _save("prices.json", prices)
    allh = _load("price_history.json", [])
    allh.append({"code": code, "store": store, "region": region, "price": price, "t": now.strftime("%Y-%m-%d")})
    _save("price_history.json", allh[-5000:])
    return msgs


def price_history(code):
    """Όλες οι τιμές που έχουν καταγραφεί για ένα προϊόν, με χρονική σειρά (και οι παλιές καταγραφές)."""
    out = [h for h in _load("price_history.json", []) if h["code"] == code]
    have = {(h["store"], h.get("region", ""), h["t"]) for h in out}
    for x in _load("prices.json", []):           # τιμές από παλαιότερες εκδόσεις χωρίς ιστορικό
        if x["code"] != code:
            continue
        try:
            t = datetime.datetime.strptime(x["date"], "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        if (x["store"], x.get("region", ""), t) not in have:
            out.append({"code": code, "store": x["store"], "region": x.get("region", ""), "price": x["price"],
                        "t": t})
    return sorted(out, key=lambda h: h["t"])


def delete_price(code, store, region):
    prices = [x for x in _load("prices.json", []) if not (x["code"] == code and x["store"] == store
                                                         and x.get("region", "") == region)]
    _save("prices.json", prices)


def all_prices(region=None):
    ps = _load("prices.json", [])
    if region and region != "Όλες":
        ps = [x for x in ps if x.get("region", "") == region]
    return ps


def regions():
    return sorted({x.get("region", "") for x in _load("prices.json", []) if x.get("region")})


def prices_for(code, region=None):
    return sorted([x for x in all_prices(region) if x["code"] == code], key=lambda x: x["price"])


def cheapest_by_category(region=None):
    """{κατηγορία: [(προϊόν, φθηνότερη εγγραφή, πλήθος καταστημάτων)], ...}"""
    by_code = {}
    for x in all_prices(region):
        by_code.setdefault(x["code"], []).append(x)
    out = {}
    for code, lst in by_code.items():
        lst.sort(key=lambda x: x["price"])
        out.setdefault(lst[0]["category"], []).append((lst[0], len(lst)))
    for cat in out:
        out[cat].sort(key=lambda t: t[0]["price"])
    return out


def get_setting(k, d=None):
    return _load("settings.json", {}).get(k, d)


def set_setting(k, v):
    s = _load("settings.json", {})
    s[k] = v
    _save("settings.json", s)


# ------------------------------------------------------------------ πληροφορίες προϊόντος
ALLERGENS = {"milk": "Γάλα", "gluten": "Γλουτένη", "eggs": "Αυγά", "nuts": "Ξηροί καρποί",
             "peanuts": "Αράπικα φιστίκια", "soybeans": "Σόγια", "fish": "Ψάρι", "crustaceans": "Οστρακοειδή",
             "molluscs": "Μαλάκια", "celery": "Σέλινο", "mustard": "Μουστάρδα", "sesame-seeds": "Σουσάμι",
             "sulphur-dioxide-and-sulphites": "Θειώδη", "lupin": "Λούπινο"}
LABELS = {"en:organic": "Βιολογικό", "en:eu-organic": "Βιολογικό ΕΕ", "en:pdo": "ΠΟΠ",
          "en:pgi": "ΠΓΕ", "en:vegan": "Vegan", "en:vegetarian": "Χορτοφαγικό", "en:gluten-free": "Χωρίς γλουτένη",
          "en:no-added-sugar": "Χωρίς προσθήκη ζάχαρης", "en:no-preservatives": "Χωρίς συντηρητικά",
          "en:fair-trade": "Δίκαιο εμπόριο", "en:lactose-free": "Χωρίς λακτόζη", "en:no-gluten": "Χωρίς γλουτένη",
          "en:made-in-greece": "Παράγεται στην Ελλάδα", "en:halal": "Halal", "en:kosher": "Kosher"}
ADDITIVES = {
    "e100": "κουρκουμίνη", "e101": "ριβοφλαβίνη", "e102": "ταρτραζίνη", "e110": "κίτρινο sunset FCF",
    "e120": "καρμίνιο", "e122": "αζορουβίνη", "e124": "πονσώ 4R", "e129": "κόκκινο allura AC",
    "e133": "μπλε brilliant FCF", "e140": "χλωροφύλλες", "e150a": "καραμελόχρωμα", "e150d":
    "καραμελόχρωμα θειώδους αμμωνίας", "e160a": "καροτένια", "e160c": "εκχύλισμα πάπρικας",
    "e162": "κόκκινο παντζαριού", "e170": "ανθρακικό ασβέστιο", "e171": "διοξείδιο τιτανίου",
    "e200": "σορβικό οξύ", "e202": "σορβικό κάλιο", "e210": "βενζοϊκό οξύ", "e211": "βενζοϊκό νάτριο",
    "e220": "διοξείδιο θείου", "e223": "μεταδιθειώδες νάτριο", "e224": "μεταδιθειώδες κάλιο",
    "e249": "νιτρώδες κάλιο", "e250": "νιτρώδες νάτριο", "e251": "νιτρικό νάτριο", "e252": "νιτρικό κάλιο",
    "e260": "οξικό οξύ", "e270": "γαλακτικό οξύ", "e281": "προπιονικό νάτριο", "e282": "προπιονικό ασβέστιο",
    "e290": "διοξείδιο του άνθρακα", "e296": "μηλικό οξύ", "e300": "ασκορβικό οξύ (βιταμίνη C)",
    "e301": "ασκορβικό νάτριο", "e306": "τοκοφερόλες (βιταμίνη E)", "e307": "άλφα-τοκοφερόλη",
    "e316": "ερυθορβικό νάτριο", "e320": "BHA", "e321": "BHT", "e322": "λεκιθίνες", "e325": "γαλακτικό νάτριο",
    "e330": "κιτρικό οξύ", "e331": "κιτρικά νάτρια", "e332": "κιτρικά κάλια", "e333": "κιτρικά ασβέστια",
    "e334": "τρυγικό οξύ", "e338": "φωσφορικό οξύ", "e339": "φωσφορικά νάτρια", "e340": "φωσφορικά κάλια",
    "e341": "φωσφορικά ασβέστια", "e401": "αλγινικό νάτριο", "e406": "άγαρ", "e407": "καραγενάνη",
    "e410": "κόμμι χαρουπιού", "e412": "κόμμι γκουάρ", "e414": "αραβικό κόμμι", "e415": "κόμμι ξανθάνης",
    "e420": "σορβιτόλη", "e422": "γλυκερόλη", "e440": "πηκτίνες", "e450": "διφωσφορικά", "e451": "τριφωσφορικά",
    "e452": "πολυφωσφορικά", "e460": "κυτταρίνη", "e466": "καρβοξυμεθυλοκυτταρίνη",
    "e471": "μονο- και διγλυκερίδια λιπαρών οξέων", "e472e": "εστέρες διακετυλοτρυγικού οξέος",
    "e475": "πολυγλυκερολεστέρες λιπαρών οξέων", "e476": "πολυρικινελαϊκός πολυγλυκερολεστέρας",
    "e481": "στεατοϋλο-2-γαλακτυλικό νάτριο", "e500": "ανθρακικά νάτρια (σόδα)", "e501": "ανθρακικά κάλια",
    "e503": "ανθρακικά αμμώνια", "e504": "ανθρακικά μαγνήσια", "e509": "χλωριούχο ασβέστιο",
    "e570": "λιπαρά οξέα", "e575": "γλυκονο-δέλτα-λακτόνη", "e621": "γλουταμινικό μονονάτριο",
    "e627": "γουανυλικό δινάτριο", "e631": "ινοσινικό δινάτριο", "e635": "5'-ριβονουκλεοτίδια",
    "e900": "διμεθυλοπολυσιλοξάνη", "e903": "κερί καρναούβης", "e904": "κόμμεα λάκκας",
    "e950": "ακεσουλφάμη K", "e951": "ασπαρτάμη", "e952": "κυκλαμικό οξύ", "e954": "σακχαρίνη",
    "e955": "σουκραλόζη", "e960": "γλυκοζίτες στεβιόλης", "e965": "μαλτιτόλη", "e967": "ξυλιτόλη",
    "e968": "ερυθριτόλη", "e1422": "ακετυλιωμένο αμυλοφωσφορικό", "e1442": "υδροξυπροπυλο-αμυλοφωσφορικό",
    "e1450": "οκτενυλοηλεκτρικό άμυλο νατρίου",
}
NUTRITION_ROWS = [("Ενέργεια", "energy-kcal_100g", "kcal"), ("Λιπαρά", "fat_100g", "g"),
                  ("  κορεσμένα", "saturated-fat_100g", "g"), ("Υδατάνθρακες", "carbohydrates_100g", "g"),
                  ("  σάκχαρα", "sugars_100g", "g"), ("Φυτικές ίνες", "fiber_100g", "g"),
                  ("Πρωτεΐνες", "proteins_100g", "g"), ("Αλάτι", "salt_100g", "g")]


def _tags(tags):
    return [t.split(":", 1)[-1] for t in (tags or [])]


def allergens(p):
    a = [ALLERGENS.get(t, t.replace("-", " ")) for t in _tags(p.get("allergens_tags"))]
    tr = [ALLERGENS.get(t, t.replace("-", " ")) for t in _tags(p.get("traces_tags"))]
    return a, [x for x in tr if x not in a]


def labels(p):
    out = [LABELS[t] for t in (p.get("labels_tags") or []) if t in LABELS]
    an = p.get("ingredients_analysis_tags") or []
    if "en:vegan" in an and "Vegan" not in out:
        out.append("Vegan (από τα συστατικά)")
    elif "en:vegetarian" in an and "Χορτοφαγικό" not in out:
        out.append("Χορτοφαγικό (από τα συστατικά)")
    return list(dict.fromkeys(out))


def palm_oil(p):
    an = p.get("ingredients_analysis_tags") or []
    if "en:palm-oil" in an:
        return "Περιέχει φοινικέλαιο"
    if "en:palm-oil-free" in an:
        return "Χωρίς φοινικέλαιο"
    return ""


def additives_named(p):
    return [(c.upper(), ADDITIVES.get(c, ""), "en:" + c in CONCERN) for c in additive_codes(p)]


def nutrition_table(p):
    n = p.get("nutriments") or {}
    rows = []
    for label, key, unit in NUTRITION_ROWS:
        v = _num(n, key)
        if v is None and key == "energy-kcal_100g":
            kj = _num(n, "energy_100g", "energy-kj_100g")
            v = kj / 4.184 if kj is not None else None
        if v is None and key == "salt_100g":
            na = _num(n, "sodium_100g")
            v = na * 2.5 if na is not None else None
        if v is not None:
            rows.append((label, v, unit))
    return rows


COUNTRIES = {"greece": "Ελλάδα", "cyprus": "Κύπρος", "italy": "Ιταλία", "germany": "Γερμανία",
             "france": "Γαλλία", "spain": "Ισπανία", "netherlands": "Ολλανδία", "belgium": "Βέλγιο",
             "turkey": "Τουρκία", "bulgaria": "Βουλγαρία", "poland": "Πολωνία", "united-kingdom": "Ην. Βασίλειο"}


def origin(p):
    parts = []
    if p.get("origins"):
        parts.append(f"Προέλευση: {p['origins']}")
    if p.get("manufacturing_places"):
        parts.append(f"Παραγωγή: {p['manufacturing_places']}")
    sold = [COUNTRIES.get(t, None) for t in _tags(p.get("countries_tags"))]
    sold = [x for x in sold if x]
    if sold:
        parts.append("Πωλείται σε: " + ", ".join(sold[:6]))
    return parts


def eco_grade(p):
    g = (p.get("environmental_score_grade") or p.get("ecoscore_grade") or "").lower()
    return g.upper() if g in ("a", "a-plus", "b", "c", "d", "e", "f") else ""


def alternatives(p, limit=12):
    """Προϊόντα της ίδιας κατηγορίας που πωλούνται στην Ελλάδα, με καλύτερο βαθμό."""
    cats = [c for c in (p.get("categories_tags") or []) if c.startswith("en:")]
    if not cats:
        return []
    my = score(p)[0] or 0
    found = []
    for cat in reversed(cats[-3:]):        # από την πιο ειδική κατηγορία
        q = {"action": "process", "json": 1, "page_size": 40, "fields": FIELDS, "sort_by": "unique_scans_n",
             "tagtype_0": "categories", "tag_contains_0": "contains", "tag_0": cat,
             "tagtype_1": "countries", "tag_contains_1": "contains", "tag_1": "greece"}
        try:
            res = _get(SEARCH_URL + urllib.parse.urlencode(q)).get("products", [])
        except Exception:  # noqa: BLE001
            res = []
        for x in res:
            if x.get("code") == p.get("code"):
                continue
            s = score(x)[0]
            if s is not None and s > my + 0.2:
                found.append((s, x))
        if len(found) >= 5:
            break
    uniq = {}
    for s, x in sorted(found, key=lambda t: -t[0]):
        uniq.setdefault(x.get("code"), (s, x))
    return list(uniq.values())[:limit]


def image_url(p):
    # μικρή εικόνα: οι μεγάλες φωτογραφίες γεμίζουν τη μνήμη και μπορεί να κλείσει η εφαρμογή
    return p.get("image_front_small_url") or p.get("image_front_url") or ""


def download_image(url, code):
    if not url:
        return None
    path = DATA_DIR / "img" / f"{clean_code(code) or 'x'}.jpg"
    if path.exists():
        return str(path)
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
        data = r.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)
