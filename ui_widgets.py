"""
Γραφικά στοιχεία της νέας εμφάνισης (ζωγραφισμένα, χωρίς εικόνες):
δείκτης βαθμού σε κύκλο, μπάρα Nutri-Score, μπάρες θρεπτικών, εικονίδια, ντεγκραντέ, κάρτες, ενότητες που ανοιγοκλείνουν.
"""
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

# ------------------------------------------------------------------ χρώματα
PAL = {
    "light": {"bg": (0.949, 0.957, 0.973, 1), "card": (1, 1, 1, 1), "ink": (0.09, 0.125, 0.2, 1),
              "muted": (0.42, 0.45, 0.52, 1), "line": (0.88, 0.9, 0.93, 1), "shadow": (0.1, 0.15, 0.3, 0.07)},
    "dark": {"bg": (0.06, 0.08, 0.125, 1), "card": (0.1, 0.13, 0.196, 1), "ink": (0.91, 0.925, 0.957, 1),
             "muted": (0.6, 0.64, 0.72, 1), "line": (0.18, 0.21, 0.28, 1), "shadow": (0, 0, 0, 0.25)},
}
C = dict(PAL["light"])
PRIMARY = (0.231, 0.357, 0.859, 1)       # μπλε-βιολετί
PRIMARY2 = (0.443, 0.29, 0.82, 1)        # βιολετί (ντεγκραντέ)
ACCENT = (0.96, 0.62, 0.0, 1)
GOOD = (0.184, 0.62, 0.267, 1)
BAD = (0.878, 0.192, 0.192, 1)
WARN = (0.94, 0.55, 0.0, 1)
NUTRI = {"a": (0.0, 0.51, 0.25, 1), "b": (0.52, 0.73, 0.18, 1), "c": (0.99, 0.80, 0.0, 1),
         "d": (0.94, 0.51, 0.0, 1), "e": (0.9, 0.24, 0.07, 1)}


def set_theme(name):
    C.update(PAL.get(name, PAL["light"]))


def score_rgba(s):
    if s is None:
        return (0.6, 0.63, 0.68, 1)
    if s >= 8.5:
        return (0.0, 0.6, 0.35, 1)
    if s >= 7:
        return (0.4, 0.7, 0.2, 1)
    if s >= 5.5:
        return (0.95, 0.7, 0.05, 1)
    if s >= 4:
        return (0.94, 0.45, 0.1, 1)
    return (0.85, 0.2, 0.15, 1)


def hexc(rgba):
    return "#%02x%02x%02x" % tuple(int(c * 255) for c in rgba[:3])


def gradient(c1, c2, n=64):
    """Κάθετο ντεγκραντέ ως υφή (από c1 πάνω σε c2 κάτω)."""
    tex = Texture.create(size=(1, n), colorfmt="rgba")
    buf = bytearray()
    for i in range(n):
        t = i / (n - 1)
        for k in range(4):
            buf.append(int(255 * (c2[k] * (1 - t) + c1[k] * t)))
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    return tex


# ------------------------------------------------------------------ κύκλος βαθμού
class ScoreRing(Widget):
    """Κύκλος βαθμού. Ζωγραφίζεται αφού πάρει την τελική του θέση (αλλιώς μένει μετατοπισμένος)."""
    value = NumericProperty(0)          # 0..10 (ζωντανά, για την κίνηση)
    target = NumericProperty(-1)        # -1 = χωρίς βαθμό
    thickness = NumericProperty(dp(10))
    text_size_sp = NumericProperty(30)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.lbl = Label(bold=True, markup=True, halign="center", valign="middle")
        self.add_widget(self.lbl)
        self._trig = Clock.create_trigger(self.redraw, 0)
        self.bind(pos=self._trig, size=self._trig, value=self._trig, target=self._trig)
        Clock.schedule_once(self.redraw, 0.2)
        Clock.schedule_once(self.redraw, 0.6)

    def set_score(self, s, animate=True):
        self.target = -1 if s is None else float(s)
        if s is None:
            self.value = 0
            return
        if animate:
            self.value = 0
            Animation(value=float(s), d=0.9, t="out_cubic").start(self)
        else:
            self.value = float(s)

    def redraw(self, *a):
        self.canvas.before.clear()
        d = min(self.width, self.height)
        if d <= 2:
            return
        cx, cy = self.center_x, self.center_y
        r = d / 2 - self.thickness / 2 - dp(1)
        col = score_rgba(None if self.target < 0 else self.target)
        with self.canvas.before:
            Color(*C["line"])
            Line(circle=(cx, cy, r), width=self.thickness / 2)
            if self.target >= 0 and self.value > 0:
                Color(*col)
                Line(circle=(cx, cy, r, 0, 360 * min(1.0, self.value / 10)), width=self.thickness / 2, cap="round")
        # η ετικέτα έχει ακριβώς το μέγεθος και τη θέση του κύκλου, και το κείμενο κεντραρισμένο μέσα του
        self.lbl.size = (d, d)
        self.lbl.text_size = (d, d)
        self.lbl.pos = (cx - d / 2, cy - d / 2)
        self.lbl.color = C["ink"]
        fs = sp(self.text_size_sp) * (d / dp(130)) ** 0.5 if d < dp(130) else sp(self.text_size_sp)
        self.lbl.font_size = fs
        num = "–" if self.target < 0 else f"{self.value:.1f}".replace(".", ",")
        self.lbl.text = num + (f"\n[size={int(fs * 0.36)}]/10[/size]" if self.target >= 0 else "")


# ------------------------------------------------------------------ Nutri-Score A–E
class NutriStrip(Widget):
    grade = StringProperty("")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.labels = []
        for g in "ABCDE":
            lb = Label(text=g, bold=True, color=(1, 1, 1, 1))
            self.add_widget(lb)
            self.labels.append(lb)
        self._trig = Clock.create_trigger(self.redraw, 0)
        self.bind(pos=self._trig, size=self._trig, grade=self._trig)
        Clock.schedule_once(self.redraw, 0.2)

    def redraw(self, *a):
        self.canvas.before.clear()
        n = 5
        gap = dp(3)
        w = (self.width - gap * (n - 1) - dp(10)) / n
        cur = self.grade.lower()
        with self.canvas.before:
            for i, g in enumerate("abcde"):
                big = g == cur
                hh = self.height if big else self.height * 0.72
                x = self.x + i * (w + gap) + (dp(5) if i else 0)
                y = self.y + (self.height - hh) / 2
                col = NUTRI[g]
                Color(col[0], col[1], col[2], 1 if (big or not cur) else 0.35)
                RoundedRectangle(pos=(x - (dp(5) if big else 0), y), size=(w + (dp(10) if big else 0), hh),
                                 radius=[dp(6)])
                lb = self.labels[i]
                lb.center = (x + w / 2, self.center_y)
                lb.font_size = sp(20 if big else 13)


# ------------------------------------------------------------------ μπάρα θρεπτικού
class NutrientBar(BoxLayout):
    """Ετικέτα, τιμή και μπάρα με χρώμα (χαμηλή/μέτρια/υψηλή)."""

    def __init__(self, label, value, unit, level, maxv, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(46), **kw)
        col = {"χαμηλή": GOOD, "μέτρια": WARN, "υψηλή": BAD}.get(level, PRIMARY)
        top = Label(text=f"[b]{label}[/b]   {value}{unit}" + (f"   [color={hexc(col)}]{level}[/color]" if level else ""),
                    markup=True, color=C["ink"], halign="left", valign="middle", size_hint_y=None, height=dp(24))
        top.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.add_widget(top)
        self.bar = Widget(size_hint_y=None, height=dp(12))
        self.add_widget(self.bar)
        frac = 0.0
        try:
            frac = max(0.02, min(1.0, float(str(value).replace(",", ".")) / maxv))
        except ValueError:
            pass

        def draw(*a):
            b = self.bar
            b.canvas.clear()
            with b.canvas:
                Color(*C["line"])
                RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(6)])
                Color(*col)
                RoundedRectangle(pos=b.pos, size=(b.width * frac, b.height), radius=[dp(6)])
        self.bar.bind(pos=draw, size=draw)


# ------------------------------------------------------------------ εικονίδια (ζωγραφιστά)
class Icon(Widget):
    kind = StringProperty("home")
    rgba = ListProperty([1, 1, 1, 1])

    def __init__(self, **kw):
        super().__init__(**kw)
        self._trig = Clock.create_trigger(self.redraw, 0)
        self.bind(pos=self._trig, size=self._trig, kind=self._trig, rgba=self._trig)
        Clock.schedule_once(self.redraw, 0.2)
        Clock.schedule_once(self.redraw, 0.6)

    def redraw(self, *a):
        self.canvas.clear()
        s = min(self.width, self.height) * 0.8
        if s <= 2:
            return
        x0, y0 = self.center_x - s / 2, self.center_y - s / 2
        w = max(1.2, s / 14)
        with self.canvas:
            Color(*self.rgba)
            k = self.kind
            if k == "home":
                Line(points=[x0, y0 + s * 0.5, x0 + s / 2, y0 + s * 0.95, x0 + s, y0 + s * 0.5], width=w)
                Line(rectangle=(x0 + s * 0.17, y0 + s * 0.05, s * 0.66, s * 0.5), width=w)
            elif k == "search":
                Line(circle=(x0 + s * 0.42, y0 + s * 0.58, s * 0.3), width=w)
                Line(points=[x0 + s * 0.63, y0 + s * 0.37, x0 + s * 0.95, y0 + s * 0.05], width=w * 1.3)
            elif k == "list":
                for i, yy in enumerate((0.8, 0.5, 0.2)):
                    Ellipse(pos=(x0, y0 + s * yy - w), size=(w * 2.2, w * 2.2))
                    Line(points=[x0 + s * 0.28, y0 + s * yy, x0 + s, y0 + s * yy], width=w)
            elif k == "user":
                Line(circle=(x0 + s / 2, y0 + s * 0.7, s * 0.22), width=w)
                Line(ellipse=(x0 + s * 0.1, y0 - s * 0.35, s * 0.8, s * 0.75, -90, 90), width=w)
            elif k == "barcode":
                xs = [0, 0.1, 0.16, 0.3, 0.38, 0.45, 0.6, 0.66, 0.78, 0.86, 0.96]
                ws = [2, 1, 3, 1, 2, 3, 1, 2, 1, 3, 2]
                for xx, ww in zip(xs, ws):
                    Rectangle(pos=(x0 + s * xx, y0 + s * 0.12), size=(w * ww * 0.8, s * 0.76))
            elif k == "compare":
                Line(rectangle=(x0, y0 + s * 0.1, s * 0.4, s * 0.8), width=w)
                Line(rectangle=(x0 + s * 0.6, y0 + s * 0.1, s * 0.4, s * 0.8), width=w)
            elif k == "share":
                for (px, py) in ((0.2, 0.5), (0.8, 0.85), (0.8, 0.15)):
                    Ellipse(pos=(x0 + s * px - w * 2, y0 + s * py - w * 2), size=(w * 4, w * 4))
                Line(points=[x0 + s * 0.2, y0 + s * 0.5, x0 + s * 0.8, y0 + s * 0.85], width=w)
                Line(points=[x0 + s * 0.2, y0 + s * 0.5, x0 + s * 0.8, y0 + s * 0.15], width=w)
            elif k == "swap":
                Line(points=[x0, y0 + s * 0.7, x0 + s, y0 + s * 0.7], width=w)
                Line(points=[x0 + s * 0.75, y0 + s * 0.9, x0 + s, y0 + s * 0.7, x0 + s * 0.75, y0 + s * 0.5], width=w)
                Line(points=[x0, y0 + s * 0.3, x0 + s, y0 + s * 0.3], width=w)
                Line(points=[x0 + s * 0.25, y0 + s * 0.5, x0, y0 + s * 0.3, x0 + s * 0.25, y0 + s * 0.1], width=w)
            elif k == "plus":
                Line(points=[x0 + s / 2, y0 + s * 0.1, x0 + s / 2, y0 + s * 0.9], width=w * 1.2)
                Line(points=[x0 + s * 0.1, y0 + s / 2, x0 + s * 0.9, y0 + s / 2], width=w * 1.2)


class IconButton(ButtonBehavior, BoxLayout):
    """Στρογγυλό κουμπί ενέργειας με εικονίδιο και λεζάντα."""
    bg = ListProperty([1, 1, 1, 1])

    def __init__(self, icon, text, color=PRIMARY, **kw):
        super().__init__(orientation="vertical", padding=(0, dp(6)), spacing=dp(2), **kw)
        self.color = color
        self.circle = Widget(size_hint_y=None, height=dp(46))
        self.icon = Icon(kind=icon, rgba=list(color), size_hint=(None, None), size=(dp(24), dp(24)))
        self.circle.add_widget(self.icon)
        self.add_widget(self.circle)
        self.lab = Label(text=text, color=C["ink"], font_size=sp(12), size_hint_y=None, height=dp(20))
        self.add_widget(self.lab)
        self._trig = Clock.create_trigger(self._d, 0)
        self.circle.bind(pos=self._trig, size=self._trig)
        Clock.schedule_once(self._d, 0.2)

    def _d(self, *a):
        c = self.circle
        c.canvas.before.clear()
        r = dp(23)
        with c.canvas.before:
            Color(self.color[0], self.color[1], self.color[2], 0.13)
            Ellipse(pos=(c.center_x - r, c.center_y - r), size=(2 * r, 2 * r))
        self.icon.center = c.center


# ------------------------------------------------------------------ κάρτα / chip / ενότητα
class CardBox(BoxLayout):
    """Λευκή κάρτα με στρογγυλές γωνίες και απαλή σκιά. Μεγαλώνει με το περιεχόμενό της."""

    def __init__(self, pad=14, **kw):
        kw.setdefault("orientation", "vertical")
        super().__init__(size_hint_y=None, padding=(dp(pad), dp(pad - 2)), spacing=dp(6), **kw)
        self.bind(minimum_height=self.setter("height"))
        self.bind(pos=self._d, size=self._d)

    def _d(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*C["shadow"])
            RoundedRectangle(pos=(self.x + dp(1), self.y - dp(2)), size=self.size, radius=[dp(16)])
            Color(*C["card"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])


class Chip(Label):
    """Μικρή χρωματιστή «ετικέτα»."""

    def __init__(self, text, rgba, **kw):
        super().__init__(text=text, markup=True, bold=True, color=(1, 1, 1, 1), font_size=sp(12),
                         size_hint=(None, None), height=dp(28), padding=(dp(10), 0), **kw)
        self.rgba = rgba
        self.bind(texture_size=lambda w, t: setattr(w, "width", t[0] + dp(20)))
        self.bind(pos=self._d, size=self._d)

    def _d(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.rgba)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])


class Section(BoxLayout):
    """Ενότητα-κάρτα με τίτλο που ανοιγοκλείνει, για να μη «φορτώνεται» η οθόνη."""
    opened = BooleanProperty(False)

    def __init__(self, title, opened=False, builder=None, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, **kw)
        self.card = CardBox(pad=12)
        self.add_widget(self.card)
        self.bind(minimum_height=self.setter("height"))
        self.head = Label(text=f"[b]{title}[/b]", markup=True, color=C["ink"], font_size=sp(16), halign="left",
                          valign="middle", size_hint_y=None, height=dp(34))
        self.head.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.arrow = Label(text="+", color=PRIMARY, bold=True, font_size=sp(22), size_hint=(None, None),
                           size=(dp(30), dp(34)))
        hb = _Tap(orientation="horizontal", size_hint_y=None, height=dp(34))
        hb.add_widget(self.head)
        hb.add_widget(self.arrow)
        hb.bind(on_release=lambda *a: self.toggle())
        self.card.add_widget(hb)
        self.body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.body.bind(minimum_height=self.setter_body)
        self.builder = builder
        self.built = False
        if opened:
            self.toggle()

    def setter_body(self, w, h):
        if self.opened:
            w.height = h

    def toggle(self):
        self.opened = not self.opened
        self.arrow.text = "-" if self.opened else "+"
        if self.opened:
            if not self.built and self.builder:
                self.builder(self.body)
                self.built = True
            if self.body.parent is None:
                self.card.add_widget(self.body)
            self.body.height = self.body.minimum_height
        elif self.body.parent is not None:
            self.card.remove_widget(self.body)


class _Tap(ButtonBehavior, BoxLayout):
    pass


def text(t, size=14, color=None, bold=False, h=None, halign="left"):
    """Label που αναδιπλώνεται και παίρνει ακριβώς το ύψος του κειμένου (0 όταν είναι κενό)."""
    lb = Label(text=t, markup=True, color=color or C["ink"], font_size=sp(size), bold=bold, halign=halign,
               valign="top", size_hint_y=None, height=0 if not t else dp(size * 1.6))

    def fit(*a):
        if h is not None:
            lb.height = h
        elif not lb.text:
            lb.height = 0
        else:
            lb.height = lb.texture_size[1] + dp(4)
    lb.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
    lb.bind(texture_size=fit, text=fit)
    return lb
