"""Λίστα αγορών και ντουλάπι με ημερομηνίες λήξης."""
import datetime
import time

import food as F
import health as H
import products as P


def _now_id():
    return int(time.time() * 1000)


# ------------------------------------------------------------------ λίστα αγορών
def shop_items():
    return F._load("shopping.json", [])


def _save_shop(items):
    F._save("shopping.json", items)


def shop_add(p=None, name="", qty=1):
    items = shop_items()
    code = (p or {}).get("code", "")
    for it in items:
        if code and it.get("code") == code and not it.get("done"):
            it["qty"] = it.get("qty", 1) + qty
            _save_shop(items)
            return it
    it = {"id": _now_id(), "code": code, "name": P.name_any(p) if p else name.strip(), "qty": qty,
          "score": P.score_any(p)["score"] if p else None, "kind": (p or {}).get("kind", ""), "done": False}
    if p and p.get("code") and not p.get("local"):
        P._cache_put(p)        # για να ανοίγει γρήγορα και χωρίς internet
    items.append(it)
    _save_shop(items)
    return it


def shop_update(iid, **kw):
    items = shop_items()
    for it in items:
        if it["id"] == iid:
            it.update(kw)
            if it.get("qty", 1) <= 0:
                items.remove(it)
            break
    _save_shop(items)


def shop_remove(iid):
    _save_shop([it for it in shop_items() if it["id"] != iid])


def shop_clear_done():
    _save_shop([it for it in shop_items() if not it.get("done")])


def shop_summary(region=None):
    """Σύνολα του καλαθιού: κόστος, μέσος βαθμός, καλύτερο κατάστημα."""
    items = [it for it in shop_items() if not it.get("done")]
    total_qty = sum(it.get("qty", 1) for it in items)
    scored = [(it["score"], it.get("qty", 1)) for it in items if it.get("score") is not None]
    avg = sum(s * q for s, q in scored) / sum(q for _, q in scored) if scored else None
    # φθηνότερη τιμή κάθε προϊόντος (οπουδήποτε) και ανά κατάστημα
    best_total, missing = 0.0, []
    stores = {}
    for it in items:
        prices = F.prices_for(it.get("code"), region) if it.get("code") else []
        if not prices:
            missing.append(it["name"])
            continue
        best_total += prices[0]["price"] * it.get("qty", 1)
        seen = {}
        for pr in prices:
            key = pr["store"]
            if key not in seen or pr["price"] < seen[key]:
                seen[key] = pr["price"]
        for st, price in seen.items():
            s = stores.setdefault(st, {"total": 0.0, "covered": 0})
            s["total"] += price * it.get("qty", 1)
            s["covered"] += 1
    priced = len(items) - len(missing)
    ranking = sorted(stores.items(), key=lambda kv: (-kv[1]["covered"], kv[1]["total"]))
    return {"items": len(items), "qty": total_qty, "avg_score": avg, "best_total": best_total,
            "priced": priced, "missing": missing, "stores": ranking}


# ------------------------------------------------------------------ ντουλάπι
def pantry_items():
    return F._load("pantry.json", [])


def _save_pantry(items):
    F._save("pantry.json", items)


def parse_date(s):
    s = (s or "").strip().replace("-", "/").replace(".", "/")
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%Y", "%m/%y"):
        try:
            d = datetime.datetime.strptime(s, fmt).date()
            if fmt in ("%m/%Y", "%m/%y"):          # «λήξη 05/2027» = τέλος του μήνα
                import calendar
                d = d.replace(day=calendar.monthrange(d.year, d.month)[1])
            return d
        except ValueError:
            continue
    return None


def pantry_add(p=None, name="", expiry="", qty=1):
    d = parse_date(expiry)
    if not d:
        raise ValueError("Γράψε ημερομηνία λήξης, π.χ. 15/11/2026 ή 05/2027.")
    items = pantry_items()
    it = {"id": _now_id(), "code": (p or {}).get("code", ""), "name": P.name_any(p) if p else name.strip(),
          "expiry": d.strftime("%d/%m/%Y"), "qty": qty, "added": datetime.date.today().strftime("%d/%m/%Y"),
          "kind": (p or {}).get("kind", "")}
    items.append(it)
    _save_pantry(items)
    return it


def pantry_remove(iid):
    _save_pantry([it for it in pantry_items() if it["id"] != iid])


def pantry_use_one(iid):
    items = pantry_items()
    for it in items:
        if it["id"] == iid:
            it["qty"] = it.get("qty", 1) - 1
            if it["qty"] <= 0:
                items.remove(it)
            break
    _save_pantry(items)


def status(it):
    """(επίπεδο, κείμενο, ημέρες): expired / today / soon (≤3) / week (≤7) / ok."""
    d = parse_date(it["expiry"])
    days = (d - datetime.date.today()).days if d else 9999
    if days < 0:
        return "expired", f"έληξε πριν από {-days} {'ημέρα' if days == -1 else 'ημέρες'}", days
    if days == 0:
        return "today", "λήγει σήμερα", days
    if days <= 3:
        return "soon", f"λήγει σε {days} {'ημέρα' if days == 1 else 'ημέρες'}", days
    if days <= 7:
        return "week", f"λήγει σε {days} ημέρες", days
    return "ok", f"λήγει {it['expiry']}", days


def pantry_sorted():
    return sorted(pantry_items(), key=lambda it: status(it)[2])


def pantry_alert_count():
    exp = soon = 0
    for it in pantry_items():
        lv = status(it)[0]
        if lv == "expired":
            exp += 1
        elif lv in ("today", "soon"):
            soon += 1
    return exp, soon


def quick_date(days=None, months=None):
    d = datetime.date.today()
    if days:
        d += datetime.timedelta(days=days)
    if months:
        import calendar
        y, m = divmod(d.month - 1 + months, 12)
        d = d.replace(year=d.year + y, month=m + 1, day=min(d.day, calendar.monthrange(d.year + y, m + 1)[1]))
    return d.strftime("%d/%m/%Y")


_ = H  # το προφίλ υγείας χρησιμοποιείται στην οθόνη της λίστας
