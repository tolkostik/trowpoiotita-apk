"""
Πρόσθετα της οθόνης (ξεχωριστό αρχείο για να μένει ελαφρύ το κύριο πρόγραμμα):
  • Εμφάνιση: μέγεθος γραμμάτων, φωτεινό/σκοτεινό θέμα.
  • Γράφημα ιστορικού τιμών.
  • Οδηγός πρώτης χρήσης.
  • Αναίρεση διαγραφών.
"""
import datetime

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import food as F

FONT_SCALES = {"Κανονικά": 1.0, "Μεγάλα": 1.2, "Πολύ μεγάλα": 1.4}

THEMES = {
    "light": {"bg": (0.955, 0.96, 0.955, 1), "card": (1, 1, 1, 1), "ink": [0.11, 0.14, 0.2, 1]},
    "dark": {"bg": (0.07, 0.08, 0.1, 1), "card": (0.15, 0.17, 0.21, 1), "ink": [0.9, 0.91, 0.93, 1]},
}

INK = list(THEMES["light"]["ink"])          # χρώμα κειμένου του τρέχοντος θέματος (το αλλάζει το apply_ui)
SERIES_COLORS = [(0.15, 0.39, 0.79), (0.06, 0.6, 0.38), (0.9, 0.5, 0.05), (0.7, 0.2, 0.6), (0.75, 0.15, 0.12),
                 (0.3, 0.6, 0.75)]


def ui_settings():
    return {"font": "Κανονικά", "theme": "light", "guide_seen": False, **F._load("ui.json", {})}


def save_ui(**kw):
    s = ui_settings()
    s.update(kw)
    F._save("ui.json", s)


def apply_ui(kv_text):
    """Εφαρμόζεται στην εκκίνηση, πριν φτιαχτεί η οθόνη. Επιστρέφει το KV με τα χρώματα του θέματος."""
    from kivy.core.window import Window
    from kivy.metrics import Metrics
    s = ui_settings()
    try:
        Metrics.fontscale = FONT_SCALES.get(s["font"], 1.0)
    except Exception:  # noqa: BLE001
        pass
    th = THEMES.get(s["theme"], THEMES["light"])
    Window.clearcolor = th["bg"]
    INK[:] = th["ink"]
    ink = ", ".join(str(x) for x in th["ink"])
    card = ", ".join(str(x) for x in th["card"])
    out = []
    lines = kv_text.split("\n")
    for i, line in enumerate(lines):
        near = " ".join(lines[max(0, i - 3):i])
        if "color: 0.11, 0.14, 0.2, 1" in line and "background_color" not in near:
            line = line.replace("color: 0.11, 0.14, 0.2, 1", f"color: {ink}")      # κείμενο πάνω στη σελίδα
        line = line.replace("rgba: 1, 1, 1, 1", f"rgba: {card}")                     # φόντο καρτών
        out.append(line)
    return "\n".join(out)


# ------------------------------------------------------------------ γράφημα τιμών
class PriceChart(Widget):
    """Απλό γράφημα γραμμών: μία γραμμή ανά κατάστημα."""

    def __init__(self, series, **kw):
        super().__init__(**kw)
        self.series = series            # {κατάστημα: [(ημερομηνία, τιμή), ...]}
        self.labels = []
        self.bind(pos=self.redraw, size=self.redraw)

    def redraw(self, *a):
        self.canvas.clear()
        for lb in self.labels:
            self.remove_widget(lb)
        self.labels = []
        pts = [(d, v) for s in self.series.values() for d, v in s]
        if not pts or self.width < 50:
            return
        d0 = min(d for d, _ in pts)
        d1 = max(d for d, _ in pts)
        lo = min(v for _, v in pts)
        hi = max(v for _, v in pts)
        if hi - lo < 0.01:
            lo, hi = lo * 0.95, hi * 1.05 + 0.01
        pad_l, pad_r, pad_b, pad_t = dp(52), dp(10), dp(26), dp(10)
        x0, y0 = self.x + pad_l, self.y + pad_b
        w, h = self.width - pad_l - pad_r, self.height - pad_b - pad_t
        span = max(1, (d1 - d0).days)

        def X(d):
            return x0 + (w * ((d - d0).days / span) if span else w / 2)

        def Y(v):
            return y0 + h * (v - lo) / (hi - lo)
        with self.canvas:
            Color(0.5, 0.52, 0.56, 0.25)
            Rectangle(pos=(x0, y0), size=(w, h))
            Color(0.5, 0.52, 0.56, 0.6)
            Line(points=[x0, y0, x0 + w, y0], width=1)
            Line(points=[x0, y0, x0, y0 + h], width=1)
            for i, (store, data) in enumerate(self.series.items()):
                r, g, b = SERIES_COLORS[i % len(SERIES_COLORS)]
                Color(r, g, b, 1)
                coords = []
                for d, v in data:
                    coords += [X(d), Y(v)]
                if len(coords) >= 4:
                    Line(points=coords, width=dp(1.6))
                for j in range(0, len(coords), 2):
                    Ellipse(pos=(coords[j] - dp(3.5), coords[j + 1] - dp(3.5)), size=(dp(7), dp(7)))
        for text, pos in ((f"{hi:.2f}€", (self.x, y0 + h - dp(10))), (f"{lo:.2f}€", (self.x, y0 - dp(6))),
                          (d0.strftime("%d/%m/%y"), (x0 - dp(4), self.y)),
                          (d1.strftime("%d/%m/%y"), (x0 + w - dp(52), self.y))):
            lb = Label(text=text.replace(".", ","), font_size="11sp", color=INK, size_hint=(None, None),
                       size=(dp(56), dp(20)), pos=pos)
            self.add_widget(lb)
            self.labels.append(lb)


def history_series(code):
    out = {}
    for h in F.price_history(code):
        try:
            d = datetime.datetime.strptime(h["t"], "%Y-%m-%d").date()
        except ValueError:
            continue
        key = h["store"] + (f" ({h['region']})" if h.get("region") else "")
        out.setdefault(key, []).append((d, h["price"]))
    return out


def chart_block(code):
    """Επιστρέφει widget με γράφημα και υπόμνημα, ή None αν υπάρχουν λιγότερες από 2 καταγραφές."""
    series = history_series(code)
    total = sum(len(v) for v in series.values())
    if total < 2:
        return None
    box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(230), padding=(dp(8), dp(4)))
    box.add_widget(PriceChart(series))
    legend = "   ".join(
        f"[color={'%02x%02x%02x' % tuple(int(c * 255) for c in SERIES_COLORS[i % len(SERIES_COLORS)])}]■[/color] {k}"
        for i, k in enumerate(series))
    box.add_widget(Label(text=legend, markup=True, color=INK, font_size="12sp", size_hint_y=None, height=dp(24),
                         halign="left", valign="middle", text_size=(None, None)))
    return box


# ------------------------------------------------------------------ οδηγός
GUIDE = [
    ("Καλώς ήρθες!", "Η Ποιότητα σού λέει πόσο καλό είναι ένα προϊόν, πού είναι φθηνότερο και αν σου ταιριάζει. "
                     "Μια γρήγορη ξενάγηση, 30 δευτερόλεπτα."),
    ("Σκανάρισμα", "Πάτα το μεγάλο κουμπί στην Αρχική. Ανοίγει ο σαρωτής της Google: στόχευσε το barcode και "
                   "τελείωσε. Έχει δικό του φακό για σκοτεινά ράφια."),
    ("Το προϊόν", "Ο κύκλος δείχνει τον βαθμό στα 10. Από κάτω: Nutri-Score, ειδοποιήσεις για το προφίλ σου και "
                  "ενότητες που ανοίγουν με ένα πάτημα (διατροφικά, συστατικά, τιμές, εναλλακτικές, πηγές)."),
    ("Τιμές & λίστα", "Γράψε την τιμή που βλέπεις: η εφαρμογή κρατά ιστορικό και σου λέει αν ακρίβυνε. Η λίστα "
                      "αγορών δείχνει κόστος, μέση ποιότητα και φθηνότερο κατάστημα για όλο το καλάθι."),
    ("Εγώ", "Δήλωσε αλλεργίες και διατροφή στο «Προφίλ υγείας» και διάλεξε εμφάνιση (μεγάλα γράμματα, σκοτεινό "
            "θέμα). Καλές αγορές!"),
]


# ------------------------------------------------------------------ αναίρεση
class Undo:
    """Κρατά αντίγραφο των αρχείων πριν από μια διαγραφή, για επαναφορά με ένα πάτημα."""

    def __init__(self, bar, label, button):
        self.bar, self.label, self.button = bar, label, button
        self.snapshot = None
        self.refresh = None
        self.ev = None
        button.bind(on_release=lambda *a: self.restore())

    def run(self, files, text, action, refresh):
        self.snapshot = {f: F._load(f, None) for f in files}
        action()
        self.refresh = refresh
        refresh()
        self.label.text = text
        self.bar.height = dp(52)
        self.bar.opacity = 1
        if self.ev:
            self.ev.cancel()
        self.ev = Clock.schedule_once(lambda dt: self.hide(), 7)

    def restore(self):
        if self.snapshot:
            for f, data in self.snapshot.items():
                if data is not None:
                    F._save(f, data)
            self.snapshot = None
            if self.refresh:
                self.refresh()
        self.hide()

    def hide(self):
        self.bar.height = 0
        self.bar.opacity = 0
        self.snapshot = None
