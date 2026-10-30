"""
Κάθε είδους προϊόν με ένα barcode.

Αναζήτηση (παράλληλα, δωρεάν, χωρίς εγγραφή):
  Open Food Facts (τρόφιμα), Open Beauty Facts (καλλυντικά), Open Pet Food Facts (τροφές ζώων),
  Open Products Facts (λοιπά) και UPCitemdb (γενική βάση, κυρίως ηλεκτρικά/ηλεκτρονικά, 100 αναζητήσεις/ημέρα).
Ό,τι βρεθεί αποθηκεύεται στο κινητό, ώστε να ανοίγει και χωρίς internet.
"""
import json
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import food as F

KINDS = {"food": "Τρόφιμο", "beauty": "Καλλυντικό / προσωπική φροντίδα", "petfood": "Τροφή ζώων",
         "medicine": "Φάρμακο / συμπλήρωμα", "electronics": "Ηλεκτρικό / ηλεκτρονικό", "general": "Άλλο προϊόν"}
OFF_DBS = [("food", "https://world.openfoodfacts.org"), ("beauty", "https://world.openbeautyfacts.org"),
           ("petfood", "https://world.openpetfoodfacts.org"), ("general", "https://world.openproductsfacts.org")]
UPC_URL = "https://api.upcitemdb.com/prod/trial/lookup?upc={code}"
CACHE_DAYS = 30
TIMEOUT = 8

ELECTRONICS_WORDS = ("electronics", "computer", "phone", "camera", "audio", "video", "television", "appliance",
                     "kitchen appliances", "headphone", "cable", "charger", "battery", "laptop", "tablet", "printer",
                     "tools", "lighting", "lamp")
MEDICINE_WORDS = ("medicine", "drug", "pharmac", "vitamin", "supplement", "health care", "φάρμακ", "συμπλήρωμα")


# ------------------------------------------------------------------ αποθήκευση στο κινητό
def _cache():
    return F._load("products_cache.json", {})


def _cache_put(p):
    c = _cache()
    c[p["code"]] = {"t": time.time(), "p": p}
    if len(c) > 400:
        for k in sorted(c, key=lambda k: c[k]["t"])[: len(c) - 400]:
            c.pop(k, None)
    F._save("products_cache.json", c)


def cached(code, max_age_days=None):
    e = _cache().get(code)
    if not e:
        return None
    if max_age_days is not None and time.time() - e["t"] > max_age_days * 86400:
        return None
    return e["p"]


# ------------------------------------------------------------------ αναζήτηση
def _off(kind, base, code):
    js = F._get(f"{base}/api/v2/product/{code}.json?fields={F.FIELDS}", timeout=TIMEOUT)
    if js.get("status") != 1 or not js.get("product"):
        return None
    p = js["product"]
    p["code"] = p.get("code") or code
    p["kind"] = kind
    p["db"] = base.split("//")[1].split(".")[1]
    if kind == "general":
        p["kind"] = guess_kind(p)
    return p


def _upc(code):
    js = F._get(UPC_URL.format(code=code), timeout=TIMEOUT)
    items = js.get("items") or []
    if not items:
        return None
    it = items[0]
    p = {"code": code, "product_name": it.get("title", ""), "brands": it.get("brand", ""),
         "generic_name": it.get("description", "")[:600], "category_text": it.get("category", ""),
         "model": it.get("model", ""), "image_front_small_url": (it.get("images") or [""])[0], "db": "upcitemdb"}
    lo, hi = it.get("lowest_recorded_price"), it.get("highest_recorded_price")
    if lo:
        p["price_range"] = f"{lo}–{hi} (διεθνείς τιμές)"
    p["kind"] = guess_kind(p)
    return p


def guess_kind(p):
    text = " ".join([str(p.get("category_text", "")), " ".join(p.get("categories_tags") or []),
                     str(p.get("product_name", ""))]).lower()
    if any(w in text for w in MEDICINE_WORDS):
        return "medicine"
    if any(w in text for w in ELECTRONICS_WORDS):
        return "electronics"
    return p.get("kind") if p.get("kind") in KINDS else "general"


def _wikidata(code):
    """Wikidata: ελεύθερη εγκυκλοπαιδική βάση, έχει barcode (GTIN) για αρκετά επώνυμα προϊόντα."""
    q = ('SELECT ?itemLabel ?brandLabel ?image ?desc WHERE { ?item wdt:P3962 "%s". '
         'OPTIONAL { ?item wdt:P1716 ?brand } OPTIONAL { ?item wdt:P18 ?image } '
         'OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc) IN ("el","en")) } '
         'SERVICE wikibase:label { bd:serviceParam wikibase:language "el,en". } } LIMIT 1' % code)
    js = F._get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q), timeout=TIMEOUT)
    rows = (js.get("results") or {}).get("bindings") or []
    if not rows:
        return None
    r = rows[0]

    def v(k):
        return (r.get(k) or {}).get("value", "")
    img = v("image")
    p = {"code": code, "product_name": v("itemLabel"), "brands": v("brandLabel"), "generic_name": v("desc"),
         "image_front_small_url": (img + "?width=300") if img else "", "db": "wikidata", "kind": "general"}
    p["kind"] = guess_kind(p)
    return p


SOURCE_NAMES = {"openfoodfacts": "Open Food Facts", "openbeautyfacts": "Open Beauty Facts",
                "openpetfoodfacts": "Open Pet Food Facts", "openproductsfacts": "Open Products Facts",
                "upcitemdb": "UPCitemdb", "wikidata": "Wikidata"}
_FILL = ("product_name", "brands", "generic_name", "image_front_small_url", "category_text", "model", "quantity",
         "price_range")


def fetch(code):
    """Ψάχνει παράλληλα σε 6 πηγές και ενώνει τις πληροφορίες. Επιστρέφει (προϊόν ή None, σημείωση)."""
    code = F.clean_code(code)
    if len(code) < 6:
        raise ValueError("Ο κωδικός barcode δεν είναι σωστός.")
    mine = F.local_product(code)
    if mine:
        mine.setdefault("kind", "food")
        return mine, ""
    fresh = cached(code, CACHE_DAYS)
    if fresh:
        return fresh, ""
    jobs = {k: (lambda kk=k, bb=b: _off(kk, bb, code)) for k, b in OFF_DBS}
    jobs["upc"] = lambda: _upc(code)
    jobs["wikidata"] = lambda: _wikidata(code)
    results, errors = {}, 0
    ex = ThreadPoolExecutor(max_workers=6)
    futs = {k: ex.submit(fn) for k, fn in jobs.items()}
    deadline = time.time() + TIMEOUT + 4
    for k, fu in futs.items():
        try:
            results[k] = fu.result(timeout=max(0.1, deadline - time.time()))
        except Exception:  # noqa: BLE001
            results[k] = None
            errors += 1
    ex.shutdown(wait=False)
    order = ["food", "beauty", "petfood", "general", "upc", "wikidata"]
    found = [results[k] for k in order if results.get(k)]
    if found:
        p = dict(found[0])
        srcs = [p.get("db", "")]
        for extra in found[1:]:
            used = False
            for f in _FILL:
                if not p.get(f) and extra.get(f):
                    p[f] = extra[f]
                    used = True
            if used:
                srcs.append(extra.get("db", ""))
        p["sources"] = [SOURCE_NAMES.get(x, x) for x in srcs if x]
        _cache_put(p)
        return p, ""
    old = cached(code)
    if old:
        return old, "Χωρίς σύνδεση: εμφανίζονται τα αποθηκευμένα στοιχεία."
    if errors == len(jobs):
        raise ConnectionError("Δεν υπάρχει σύνδεση με τις βάσεις προϊόντων.")
    return None, ""


def clear_cache():
    F._save("products_cache.json", {})


# ------------------------------------------------------------------ ελληνικό barcode
def greek_barcode(code):
    code = F.clean_code(code)
    return len(code) == 13 and code[:3] in ("520", "521")


GREEK_NOTE = ("Barcode καταχωρημένο στην Ελλάδα (520/521). Δείχνει ότι η εταιρεία που το κατοχύρωσε έχει "
              "ελληνικό μητρώο GS1, όχι απαραίτητα ότι το προϊόν ή οι πρώτες ύλες είναι ελληνικά.")


# ------------------------------------------------------------------ καλλυντικά: συστατικά
BEAUTY_RULES = [
    ("Αρώματα (parfum)", ("parfum", "fragrance", "aroma"), 0.4, 0.4,
     "συχνή αιτία αλλεργίας στο δέρμα"),
    ("Αλλεργιογόνα αρωμάτων", ("limonene", "linalool", "citronellol", "geraniol", "eugenol", "coumarin", "citral",
                               "hexyl cinnamal", "benzyl salicylate", "benzyl benzoate", "cinnamal", "isoeugenol",
                               "hydroxycitronellal", "farnesol", "amyl cinnamal", "alpha-isomethyl ionone",
                               "benzyl cinnamate", "anise alcohol", "cinnamyl alcohol", "evernia"), 0.25, 1.5,
     "δηλώνονται υποχρεωτικά στην ΕΕ ως πιθανά αλλεργιογόνα"),
    ("Συντηρητικά με επιφυλάξεις", ("methylisothiazolinone", "methylchloroisothiazolinone", "propylparaben",
                                    "butylparaben", "dmdm hydantoin", "imidazolidinyl urea", "diazolidinyl urea",
                                    "quaternium-15", "2-bromo-2-nitropropane", "bronopol", "triclosan", "bha", "bht"),
     0.8, 2.4, "πιθανή ευαισθητοποίηση ή αμφιλεγόμενη ασφάλεια σε υψηλή έκθεση"),
    ("Φίλτρα UV με επιφυλάξεις", ("benzophenone-3", "oxybenzone", "ethylhexyl methoxycinnamate", "octinoxate",
                                  "homosalate", "octocrylene"), 0.5, 1.5, "υπό αξιολόγηση για ορμονική δράση"),
    ("Ερεθιστικά επιφανειοδραστικά", ("sodium lauryl sulfate",), 0.4, 0.4,
     "μπορεί να ερεθίσει ευαίσθητο δέρμα"),
]


def beauty_score(p):
    text = F.ingredients_text(p).lower()
    if not text:
        return {"score": None, "why": ["Δεν υπάρχουν συστατικά στη βάση για αξιολόγηση."], "confidence": None,
                "flags": []}
    s, why, flags = 8.5, ["Βάση 8,5 για καλλυντικό με γνωστά συστατικά"], []
    for name, words, each, cap, reason in BEAUTY_RULES:
        found = sorted({w for w in words if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text)})
        if found:
            d = -min(cap, each * len(found))
            s += d
            why.append(f"{name}: {', '.join(found)} ({F._n(d)})")
            flags.append((name, found, reason))
    if not flags:
        why.append("Χωρίς συστατικά από τις λίστες επιφυλάξεων")
    if any(x in (p.get("labels_tags") or []) for x in ("en:organic", "en:eu-organic", "en:cosmos-organic")):
        s += 0.3
        why.append("Βιολογικό: +0,3")
    return {"score": round(max(1.0, min(10.0, s)), 1), "why": why, "confidence": "μέτρια (από τα συστατικά)",
            "flags": flags}


# ------------------------------------------------------------------ τροφές ζώων
def pet_score(p):
    n = p.get("nutriments") or {}
    text = F.ingredients_text(p).lower()
    if not n and not text:
        return {"score": None, "why": ["Δεν υπάρχουν στοιχεία για αξιολόγηση."], "confidence": None}
    s, why = 6.0, ["Βάση 6"]
    pro = F._num(n, "proteins_100g")
    if pro is not None:
        d = 1.5 if pro >= 30 else (1.0 if pro >= 25 else (0.0 if pro >= 18 else -1.0))
        s += d
        why.append(f"Πρωτεΐνη {F._n(pro, False)}%: {F._n(d)}")
    first = re.split(r"[,(;]", text)[0] if text else ""
    if any(w in first for w in ("chicken", "beef", "lamb", "salmon", "fish", "turkey", "duck", "meat", "κοτόπουλο",
                                "βοδινό", "αρνί", "σολομ", "ψάρι", "γαλοπούλα", "κρέας")):
        s += 0.8
        why.append("Πρώτο συστατικό κρέας/ψάρι: +0,8")
    elif any(w in first for w in ("cereal", "wheat", "maize", "corn", "δημητριακ", "σιτάρι", "καλαμπόκι")):
        s -= 0.8
        why.append("Πρώτο συστατικό δημητριακά: −0,8")
    if "sugar" in text or "ζάχαρη" in text:
        s -= 0.5
        why.append("Περιέχει ζάχαρη: −0,5")
    codes = F.additive_codes(p)
    if codes:
        d = -min(1.0, 0.2 * len(codes))
        s += d
        why.append(f"{len(codes)} πρόσθετα: {F._n(d)}")
    return {"score": round(max(1.0, min(10.0, s)), 1), "why": why, "confidence": "χαμηλή (εκτίμηση)"}


# ------------------------------------------------------------------ βαθμός ανά είδος
def score_any(p):
    kind = p.get("kind", "food")
    if kind == "food":
        d = F.score_details(p)
        d["flags"] = []
        return d
    if kind == "beauty":
        return beauty_score(p)
    if kind == "petfood":
        d = pet_score(p)
        d["flags"] = []
        return d
    msg = {"medicine": "Για φάρμακα δεν δίνεται βαθμός: η σωστή επιλογή εξαρτάται από τον γιατρό/φαρμακοποιό.",
           "electronics": "Για ηλεκτρικά/ηλεκτρονικά δεν υπάρχουν αντικειμενικά δεδομένα ποιότητας. Βάλε τη δική "
                          "σου βαθμολογία και δες κριτικές και ενεργειακή σήμανση παρακάτω.",
           "general": "Για αυτό το είδος δεν υπάρχουν αντικειμενικά δεδομένα ποιότητας. Βάλε τη δική σου "
                      "βαθμολογία παρακάτω."}.get(kind, "")
    return {"score": None, "why": [msg], "confidence": None, "flags": []}


def name_any(p):
    n = F.name_of(p)
    if p.get("model") and p["model"] not in n:
        n += f" ({p['model']})"
    return n


# ------------------------------------------------------------------ δική μου βαθμολογία / σημειώσεις
def user_info(code):
    return F._load("user_notes.json", {}).get(F.clean_code(code), {})


def set_user_info(code, **kw):
    d = F._load("user_notes.json", {})
    e = d.setdefault(F.clean_code(code), {})
    e.update(kw)
    F._save("user_notes.json", d)


def warranty_end(info):
    """Ημερομηνία λήξης εγγύησης από ημερομηνία αγοράς και μήνες."""
    import datetime
    try:
        d = datetime.datetime.strptime(info.get("bought", ""), "%d/%m/%Y").date()
    except ValueError:
        return None
    m = F._num({"m": info.get("warranty_months")}, "m")
    if not m:
        return None
    y, mo = divmod(d.month - 1 + int(m), 12)
    import calendar
    day = min(d.day, calendar.monthrange(d.year + y, mo + 1)[1])
    return datetime.date(d.year + y, mo + 1, day)


# ------------------------------------------------------------------ χρήσιμοι σύνδεσμοι
def _g(q):
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)


def links_for(p):
    kind = p.get("kind", "food")
    name = name_any(p)
    short = " ".join(name.split()[:6])
    out = []
    if kind in ("food", "petfood"):
        out.append(("Έλεγχος ανακλήσεων (ΕΦΕΤ)", _g(f"site:efet.gr ανάκληση {short}")))
    elif kind == "medicine":
        out.append(("Ανακλήσεις φαρμάκων (ΕΟΦ)", _g(f"site:eof.gr ανάκληση {short}")))
    else:
        out.append(("Έλεγχος ανακλήσεων ασφαλείας (ΕΕ – Safety Gate)", _g(f"Safety Gate recall {short}")))
    if kind == "medicine":
        out.append(("Πληροφορίες φαρμάκου (galinos.gr)", _g(f"site:galinos.gr {short}")))
        out.append(("ΕΟΦ: εγκεκριμένα φάρμακα", _g(f"site:eof.gr {short}")))
    if kind == "electronics":
        out.append(("Κριτικές και τιμές (Skroutz)", "https://www.skroutz.gr/search?keyphrase=" +
                    urllib.parse.quote(short)))
        out.append(("Ενεργειακή σήμανση ΕΕ (EPREL)", "https://eprel.ec.europa.eu/screen/home"))
        out.append(("Κριτικές στο διαδίκτυο", _g(f"{short} κριτική review")))
    if kind == "beauty":
        out.append(("Κριτικές", _g(f"{short} κριτική")))
    if kind == "general":
        out.append(("Τιμές (Skroutz)", "https://www.skroutz.gr/search?keyphrase=" + urllib.parse.quote(short)))
    out.append(("Αναζήτηση barcode στο διαδίκτυο", _g(p.get("code", ""))))
    return out


MEDICINE_NOTE = ("Για φάρμακα και συμπληρώματα διάβαζε πάντα το φύλλο οδηγιών και ρώτα τον γιατρό ή τον "
                 "φαρμακοποιό σου. Τα ελληνικά φάρμακα έχουν ειδική ταινία γνησιότητας και συχνά δεν υπάρχουν "
                 "στις διεθνείς βάσεις barcode.")


def save_local_generic(code, name, brand, kind, quantity="", ingredients=""):
    code = F.clean_code(code)
    p = {"code": code, "product_name": name, "brands": brand, "quantity": quantity, "kind": kind,
         "ingredients_text": ingredients, "local": True}
    db = F._load("my_products.json", {})
    db[code] = p
    F._save("my_products.json", db)
    return p


# ------------------------------------------------------------------ εναλλακτικές για κάθε είδος
BASE_BY_KIND = {"food": "https://world.openfoodfacts.org", "beauty": "https://world.openbeautyfacts.org",
                "petfood": "https://world.openpetfoodfacts.org", "general": "https://world.openproductsfacts.org"}
GREEK_CAT_TAGS = {"Γαλακτοκομικά": "en:dairies", "Τυριά": "en:cheeses", "Κρέας & αλλαντικά": "en:meats",
                  "Ψάρια": "en:fishes", "Ψωμί & αρτοσκευάσματα": "en:breads", "Δημητριακά": "en:breakfast-cereals",
                  "Ζυμαρικά, ρύζι & όσπρια": "en:pastas", "Μπισκότα & γλυκά": "en:biscuits",
                  "Σνακ": "en:salty-snacks", "Λάδι & λίπη": "en:vegetable-oils", "Κονσέρβες & έτοιμα": "en:canned-foods",
                  "Ροφήματα & αναψυκτικά": "en:sodas", "Χυμοί": "en:fruit-juices", "Καφές & τσάι": "en:coffees"}


def _cats(p):
    cats = [c for c in (p.get("categories_tags") or []) if c.startswith("en:")]
    if not cats and p.get("category") in GREEK_CAT_TAGS:
        cats = [GREEK_CAT_TAGS[p["category"]]]
    return cats


def _v2_search(base, cat, greece):
    q = {"categories_tags": cat, "fields": F.FIELDS, "page_size": 40, "sort_by": "unique_scans_n"}
    if greece:
        q["countries_tags"] = "en:greece"
    js = F._get(f"{base}/api/v2/search?" + urllib.parse.urlencode(q), timeout=TIMEOUT + 2)
    return js.get("products", [])


def alternatives_any(p, limit=12, max_seconds=25):
    """Καλύτερες (ή παρόμοιες) επιλογές της ίδιας κατηγορίας. Επιστρέφει (λίστα (βαθμός, προϊόν), τίτλος)."""
    kind = p.get("kind", "food")
    start = time.time()
    if kind in BASE_BY_KIND and _cats(p):
        base = BASE_BY_KIND[kind]
        my = score_any(p)["score"]
        found = {}
        for cat in list(reversed(_cats(p)[-3:])):
            for greece in (True, False):
                if time.time() - start > max_seconds:
                    break
                try:
                    res = _v2_search(base, cat, greece)
                except Exception:  # noqa: BLE001
                    continue
                for x in res:
                    if x.get("code") == p.get("code") or not x.get("code"):
                        continue
                    x["kind"] = kind
                    sc = score_any(x)["score"]
                    if sc is None:
                        continue
                    if my is None or sc > my + 0.2 or (my >= 9 and sc >= my - 0.3):
                        found.setdefault(x["code"], (sc, x))
                if len(found) >= 6:
                    break
            if len(found) >= 6:
                break
        lst = sorted(found.values(), key=lambda t: -t[0])[:limit]
        title = ("Εξίσου καλές επιλογές" if my is not None and my >= 9 else "Καλύτερες επιλογές") + " στην ίδια κατηγορία"
        return lst, title
    # ηλεκτρικά / φάρμακα / λοιπά: παρόμοια προϊόντα από τη γενική βάση
    words = " ".join((p.get("product_name") or "").split()[:4])
    if not words:
        return [], ""
    try:
        js = F._get("https://api.upcitemdb.com/prod/trial/search?" +
                    urllib.parse.urlencode({"s": words, "match_mode": 0, "type": "product"}), timeout=TIMEOUT + 2)
    except Exception:  # noqa: BLE001
        return [], ""
    out = []
    for it in (js.get("items") or [])[:limit]:
        if it.get("ean") == p.get("code"):
            continue
        x = {"code": it.get("ean") or it.get("upc") or "", "product_name": it.get("title", ""),
             "brands": it.get("brand", ""), "category_text": it.get("category", ""), "model": it.get("model", ""),
             "image_front_small_url": (it.get("images") or [""])[0], "db": "upcitemdb", "kind": kind}
        if it.get("lowest_recorded_price"):
            x["price_range"] = f"{it['lowest_recorded_price']}–{it.get('highest_recorded_price')} (διεθνείς τιμές)"
        out.append((None, x))
    return out, "Παρόμοια προϊόντα"


def share_text(p, d):
    lines = [name_any(p), f"Barcode: {p.get('code', '')}"]
    if d.get("score") is not None:
        lines.append(f"Βαθμός ποιότητας: {F._n(d['score'], False)}/10 ({F.verdict(d['score'])})")
    if p.get("nutriscore_grade"):
        lines.append(f"Nutri-Score: {p['nutriscore_grade'].upper()}")
    bp = F.prices_for(p.get("code"))
    if bp:
        lines.append(f"Φθηνότερο: {bp[0]['price']:.2f} € στο {bp[0]['store']}".replace(".", ",", 1))
    lines.append("(από την εφαρμογή Ποιότητα)")
    return "\n".join(lines)


def search_all(term, page_size=20):
    """Αναζήτηση με όνομα σε τρόφιμα και καλλυντικά ταυτόχρονα, με όριο χρόνου."""
    def one(kind, base, greece):
        q = {"search_terms": term, "search_simple": 1, "action": "process", "json": 1, "page_size": page_size,
             "fields": F.FIELDS, "sort_by": "unique_scans_n"}
        if greece:
            q.update({"tagtype_0": "countries", "tag_contains_0": "contains", "tag_0": "greece"})
        js = F._get(f"{base}/cgi/search.pl?" + urllib.parse.urlencode(q), timeout=15)
        out = js.get("products", [])
        for x in out:
            x["kind"] = kind
        return out
    ex = ThreadPoolExecutor(max_workers=3)
    futs = [ex.submit(one, "food", BASE_BY_KIND["food"], True), ex.submit(one, "beauty", BASE_BY_KIND["beauty"], False)]
    res, seen = [], set()
    deadline = time.time() + 18
    for fu in futs:
        try:
            for x in fu.result(timeout=max(0.1, deadline - time.time())):
                if x.get("code") and x["code"] not in seen:
                    seen.add(x["code"])
                    res.append(x)
        except Exception:  # noqa: BLE001
            continue
    if not [x for x in res if x["kind"] == "food"]:
        try:
            for x in one("food", BASE_BY_KIND["food"], False):
                if x.get("code") and x["code"] not in seen:
                    res.append(x)
        except Exception:  # noqa: BLE001
            pass
    ex.shutdown(wait=False)
    return res


# ------------------------------------------------------------------ περισσότερες πληροφορίες
def extra_facts(p):
    """Λίστα (τίτλος, κείμενο) με επιπλέον στοιχεία όπου υπάρχουν."""
    out = []
    emb = (p.get("emb_codes") or "").strip()
    if emb:
        first = emb.split(",")[0].strip()
        note = ""
        up = first.upper().replace(" ", "")
        if up.startswith("EL") or up.startswith("GR"):
            note = " (συσκευάστηκε/μεταποιήθηκε σε μονάδα στην Ελλάδα)"
        out.append(("Κωδικός μονάδας συσκευασίας", first + note))
    for key in ("ecoscore_data", "environmental_score_data"):
        d = p.get(key) or {}
        co2 = ((d.get("agribalyse") or {}).get("co2_total"))
        if co2:
            try:
                out.append(("Αποτύπωμα άνθρακα", f"{float(co2):.1f} kg CO2 ανά κιλό προϊόντος".replace(".", ",")))
                break
            except (TypeError, ValueError):
                pass
    if p.get("unique_scans_n"):
        out.append(("Δημοτικότητα", f"σκαναρίστηκε από {p['unique_scans_n']} χρήστες της βάσης"))
    comp = p.get("completeness")
    try:
        if comp is not None:
            out.append(("Πληρότητα στοιχείων", f"{float(comp) * 100:.0f}%"))
    except (TypeError, ValueError):
        pass
    if p.get("stores"):
        out.append(("Καταστήματα", str(p["stores"])[:120]))
    for line in F.origin(p):
        k, _, v = line.partition(": ")
        out.append((k, v))
    if p.get("packaging"):
        out.append(("Συσκευασία", str(p["packaging"])[:120]))
    if p.get("serving_size"):
        out.append(("Μερίδα", str(p["serving_size"])))
    return out


def db_page(p):
    base = {"openfoodfacts": "https://world.openfoodfacts.org", "openbeautyfacts": "https://world.openbeautyfacts.org",
            "openpetfoodfacts": "https://world.openpetfoodfacts.org",
            "openproductsfacts": "https://world.openproductsfacts.org"}.get(p.get("db") or "openfoodfacts")
    if not base or p.get("local"):
        return None
    return f"{base}/product/{p.get('code', '')}"
