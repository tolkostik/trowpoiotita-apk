"""
Ποιότητα – σκανάρεις, συγκρίνεις, διαλέγεις καλύτερα.
Νέα εμφάνιση: 4 καρτέλες (Αρχική, Αναζήτηση, Λίστα, Εγώ), σαρωτής barcode της Google.
"""
import threading
import time
import webbrowser

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.screenmanager import NoTransition, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform

import food as F
import health as H
import lists as L
import products as P
import scanner as SC
import ui_extra as UX
import ui_widgets as UW

IS_ANDROID = platform == "android"
TABS = ("home", "search", "list", "me")
TITLES = {"home": "Ποιότητα", "search": "Αναζήτηση", "list": "Λίστα αγορών", "me": "Εγώ", "product": "Προϊόν",
          "compare": "Σύγκριση", "prices": "Τιμές ανά κατάστημα", "history": "Ιστορικό", "profile": "Προφίλ υγείας",
          "add": "Νέο προϊόν", "guide": "Οδηγός"}

KV = """
#:import dp kivy.metrics.dp

<NavItem>:
    orientation: 'vertical'
    padding: 0, dp(6)
    spacing: dp(2)

<Root>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: app.c_bg
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        size_hint_y: None
        height: dp(58)
        padding: dp(8), dp(6)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            Rectangle:
                pos: self.pos
                size: self.size
                texture: app.grad
        Button:
            text: '<'
            bold: True
            font_size: '24sp'
            size_hint_x: None
            width: dp(46) if app.can_back else 0
            opacity: 1 if app.can_back else 0
            disabled: not app.can_back
            background_normal: ''
            background_color: 1, 1, 1, 0.15
            on_release: app.back()
        Label:
            text: app.title_text
            bold: True
            font_size: '20sp'
            halign: 'left'
            valign: 'middle'
            text_size: self.size
            shorten: True
    ScreenManager:
        id: sm
    BoxLayout:
        id: undo_bar
        size_hint_y: None
        height: 0
        opacity: 0
        padding: dp(8), dp(4)
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: 0.15, 0.17, 0.24, 1
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            id: undo_lbl
            halign: 'left'
            valign: 'middle'
            text_size: self.size
        Button:
            id: undo_btn
            text: 'ΑΝΑΙΡΕΣΗ'
            bold: True
            size_hint_x: None
            width: dp(120)
            background_normal: ''
            background_color: 0.96, 0.62, 0.0, 1
    BoxLayout:
        id: nav
        size_hint_y: None
        height: dp(64)
        canvas.before:
            Color:
                rgba: app.c_card
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: app.c_line
            Rectangle:
                pos: self.x, self.top - dp(1)
                size: self.width, dp(1)
"""


class NavItem(ButtonBehavior, BoxLayout):
    pass


class Root(BoxLayout):
    pass


class Tap(ButtonBehavior, BoxLayout):
    pass


# ------------------------------------------------------------------ προστασία από κλεισίματα
from kivy.base import ExceptionHandler, ExceptionManager  # noqa: E402


class _Guard(ExceptionHandler):
    def handle_exception(self, inst):
        try:
            import traceback
            F.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(F.DATA_DIR / "errors.log", "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%d/%m %H:%M ") + "".join(
                    traceback.format_exception(type(inst), inst, inst.__traceback__))[-1500:] + "\n")
        except Exception:  # noqa: BLE001
            pass
        return ExceptionManager.PASS


ExceptionManager.add_handler(_Guard())


def esc(t):
    return str(t).replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def gr(x):
    t = f"{x:.1f}".replace(".", ",")
    return t[:-2] if t.endswith(",0") else t


def euro(x):
    return f"{x:.2f}".replace(".", ",") + " €"


class PoiotitaApp(App):
    title = "Poiotita"
    c_bg = ListProperty([0.949, 0.957, 0.973, 1])
    c_card = ListProperty([1, 1, 1, 1])
    c_line = ListProperty([0.88, 0.9, 0.93, 1])
    grad = ObjectProperty(None, allownone=True)
    can_back = BooleanProperty(False)
    title_text = StringProperty("Ποιότητα")

    # ================================================================== εκκίνηση
    def build(self):
        F.set_dir(self.user_data_dir)
        u = UX.ui_settings()
        UX.apply_ui("")                                   # μέγεθος γραμμάτων
        UW.set_theme(u["theme"])
        self.c_bg, self.c_card, self.c_line = list(UW.C["bg"]), list(UW.C["card"]), list(UW.C["line"])
        Window.clearcolor = UW.C["bg"]
        self.grad = UW.gradient(UW.PRIMARY, UW.PRIMARY2)
        Builder.load_string(KV)
        self.root_w = Root()
        self.sm = self.root_w.ids.sm
        self.sm.transition = NoTransition()
        self.pages = {}
        for name in TITLES:
            scr = Screen(name=name)
            sv = ScrollView(do_scroll_x=False, bar_width=dp(4))
            box = BoxLayout(orientation="vertical", size_hint_y=None, padding=(dp(12), dp(12)), spacing=dp(12))
            box.bind(minimum_height=box.setter("height"))
            sv.add_widget(box)
            scr.add_widget(sv)
            self.sm.add_widget(scr)
            self.pages[name] = (sv, box)
        self.nav_items = {}
        for key, icon, label in (("home", "home", "Αρχική"), ("search", "search", "Αναζήτηση"),
                                 ("list", "list", "Λίστα"), ("me", "user", "Εγώ")):
            it = NavItem()
            ic = UW.Icon(kind=icon, size_hint_y=None, height=dp(26))
            lb = Label(text=label, font_size=sp(12), size_hint_y=None, height=dp(18))
            it.add_widget(ic)
            it.add_widget(lb)
            it.icon, it.lab = ic, lb
            it.bind(on_release=lambda w, k=key: self.tab(k))
            self.root_w.ids.nav.add_widget(it)
            self.nav_items[key] = it
        ids = self.root_w.ids
        self.undo = UX.Undo(ids.undo_bar, ids.undo_lbl, ids.undo_btn)
        self.busy = False
        self.search_busy = False
        self._token = 0
        self._price_msgs = []
        self.current = None
        self.stack = []
        Window.bind(on_keyboard=self._key)
        self.tab("home")
        if not u.get("guide_seen"):
            Clock.schedule_once(lambda dt: self.show_guide(0), 0.4)
        return self.root_w

    def on_pause(self):
        return True

    # ================================================================== πλοήγηση
    def page(self, name):
        sv, box = self.pages[name]
        box.clear_widgets()
        sv.scroll_y = 1
        return box

    def show(self, name, push=True):
        if push and self.sm.current != name:
            self.stack.append(self.sm.current)
        self.sm.current = name
        self.title_text = TITLES.get(name, "Ποιότητα")
        self.can_back = name not in TABS
        tab = name if name in TABS else (self.stack[0] if self.stack and self.stack[0] in TABS else "home")
        for k, it in self.nav_items.items():
            on = k == tab
            col = UW.PRIMARY if on else UW.C["muted"]
            it.icon.rgba = list(col)
            it.lab.color = col
            it.lab.bold = on

    def tab(self, name):
        self.stack = []
        getattr(self, "build_" + name)()
        self.show(name, push=False)

    def back(self):
        if not self.stack:
            return False
        prev = self.stack.pop()
        if prev in TABS:
            getattr(self, "build_" + prev)()
        self.show(prev, push=False)
        return True

    def _key(self, win, key, *a):
        if key == 27:
            return self.back()
        return False

    # ================================================================== κοινά στοιχεία
    def card(self, box, pad=14):
        c = UW.CardBox(pad=pad)
        box.add_widget(c)
        return c

    def btn(self, parent, text, cb, color=UW.PRIMARY, fg=(1, 1, 1, 1), h=52):
        b = Button(text=text, bold=True, size_hint_y=None, height=dp(h), background_normal="",
                   background_color=color, color=fg, font_size=sp(15))
        b.bind(on_release=lambda *a: cb())
        parent.add_widget(b)
        return b

    def ghost(self, parent, text, cb, h=48):
        return self.btn(parent, text, cb, color=UW.C["line"], fg=UW.C["ink"], h=h)

    def product_row(self, parent, p, score, sub, on_tap):
        r = Tap(orientation="horizontal", size_hint_y=None, height=dp(78), spacing=dp(12), padding=(dp(10), dp(8)))

        def bg(*a):
            r.canvas.before.clear()
            with r.canvas.before:
                Color(*UW.C["card"])
                RoundedRectangle(pos=r.pos, size=r.size, radius=[dp(14)])
        r.bind(pos=bg, size=bg)
        ring = UW.ScoreRing(size_hint=(None, None), size=(dp(60), dp(60)), thickness=dp(5), text_size_sp=15)
        ring.set_score(score, animate=False)
        r.add_widget(ring)
        col = BoxLayout(orientation="vertical")
        t = Label(text=f"[b]{esc(F.name_of(p) if isinstance(p, dict) else p)}[/b]", markup=True, color=UW.C["ink"],
                  halign="left", valign="bottom", shorten=True, font_size=sp(15))
        t.bind(size=lambda w, s: setattr(w, "text_size", s))
        s2 = Label(text=sub, markup=True, color=UW.C["muted"], halign="left", valign="top", font_size=sp(12),
                   shorten=True)
        s2.bind(size=lambda w, s: setattr(w, "text_size", s))
        col.add_widget(t)
        col.add_widget(s2)
        r.add_widget(col)
        r.bind(on_release=lambda *a: on_tap())
        parent.add_widget(r)
        return r

    def message(self, box, text, rgba=UW.PRIMARY):
        c = UW.CardBox(pad=12)
        c.add_widget(UW.text(text, color=rgba))
        box.add_widget(c)
        return c

    def share(self, text):
        if not IS_ANDROID:
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(text)
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            from jnius import autoclass, cast
            Intent = autoclass("android.content.Intent")
            String = autoclass("java.lang.String")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            i = Intent(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(Intent.EXTRA_TEXT, cast("java.lang.CharSequence", String(text)))
            act.startActivity(Intent.createChooser(i, cast("java.lang.CharSequence", String("Κοινοποίηση"))))
        except Exception:  # noqa: BLE001
            pass

    def vibrate(self):
        if not IS_ANDROID:
            return
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            Context = autoclass("android.content.Context")
            act.getSystemService(Context.VIBRATOR_SERVICE).vibrate(400)
        except Exception:  # noqa: BLE001
            pass

    # ================================================================== Αρχική
    def build_home(self):
        box = self.page("home")
        hero = BoxLayout(orientation="vertical", size_hint_y=None, padding=(dp(16), dp(16)), spacing=dp(6))
        hero.bind(minimum_height=hero.setter("height"))

        def hbg(*a):
            hero.canvas.before.clear()
            with hero.canvas.before:
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=hero.pos, size=hero.size, radius=[dp(22)], texture=self.grad)
        hero.bind(pos=hbg, size=hbg)
        hero.add_widget(UW.text("[b]Τι αγοράζεις σήμερα;[/b]", size=20, color=(1, 1, 1, 1)))
        hero.add_widget(UW.text("Σκάναρε το barcode για βαθμό ποιότητας, τιμές και καλύτερες επιλογές.", size=13,
                                color=(1, 1, 1, 0.88)))
        from kivy.uix.anchorlayout import AnchorLayout
        holder = AnchorLayout(size_hint_y=None, height=dp(170))
        scan = Tap(size_hint=(None, None), size=(dp(136), dp(136)), orientation="vertical", padding=(0, dp(28)))

        def sbg(*a):
            scan.canvas.before.clear()
            with scan.canvas.before:
                Color(1, 1, 1, 0.2)
                Ellipse(pos=(scan.x - dp(9), scan.y - dp(9)), size=(scan.width + dp(18), scan.height + dp(18)))
                Color(1, 1, 1, 1)
                Ellipse(pos=scan.pos, size=scan.size)
        ic = UW.Icon(kind="barcode", rgba=list(UW.PRIMARY), size_hint_y=None, height=dp(46))
        scan.add_widget(ic)
        lbl = Label(text="[b]ΣΚΑΝΑΡΙΣΜΑ[/b]", markup=True, color=UW.PRIMARY, font_size=sp(14), size_hint_y=None,
                    height=dp(24))
        scan.add_widget(lbl)
        scan.bind(pos=sbg, size=sbg, on_release=lambda *a: self.start_scan())
        holder.add_widget(scan)
        hero.add_widget(holder)
        box.add_widget(hero)

        c = self.card(box, pad=12)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        ti = TextInput(hint_text="ή γράψε τον κωδικό barcode", input_filter="int", multiline=False, font_size=sp(16),
                       padding=(dp(10), dp(12)))
        go = Button(text="Έλεγχος", bold=True, size_hint_x=None, width=dp(100), background_normal="",
                    background_color=UW.PRIMARY)
        go.bind(on_release=lambda *a: self.lookup(ti.text))
        ti.bind(on_text_validate=lambda *a: self.lookup(ti.text))
        row.add_widget(ti)
        row.add_widget(go)
        c.add_widget(row)
        self.home_status = UW.text("", size=13, color=UW.C["muted"])
        c.add_widget(self.home_status)

        tiles = BoxLayout(size_hint_y=None, height=dp(86), spacing=dp(8))
        for icon, label, cb in (("compare", "Σύγκριση", lambda: self.open_compare()),
                                ("list", "Τιμές", lambda: self.open_prices()),
                                ("search", "Ιστορικό", lambda: self.open_history())):
            ib = UW.IconButton(icon, label)
            ib.bind(on_release=lambda w, c_=cb: c_())
            t = BoxLayout(padding=(dp(4), dp(4)))

            def tbg(w, *a):
                w.canvas.before.clear()
                with w.canvas.before:
                    Color(*UW.C["card"])
                    RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(16)])
            t.bind(pos=tbg, size=tbg)
            t.add_widget(ib)
            tiles.add_widget(t)
        box.add_widget(tiles)

        sm = L.shop_summary()
        if sm["items"]:
            c2 = self.card(box)
            c2.add_widget(UW.text(f"[b]Λίστα αγορών:[/b] {sm['items']} προϊόντα"
                                  + (f" · περίπου {euro(sm['best_total'])}" if sm["priced"] else "")))
            self.ghost(c2, "Άνοιγμα λίστας", lambda: self.tab("list"), h=42)

        hist = F.load_history()[:12]
        if hist:
            box.add_widget(UW.text("[b]Πρόσφατα[/b]", size=16))
            sv = ScrollView(do_scroll_y=False, size_hint_y=None, height=dp(150), bar_width=0)
            strip = BoxLayout(size_hint_x=None, spacing=dp(10), padding=(0, dp(4)))
            strip.bind(minimum_width=strip.setter("width"))
            for it in hist:
                cardw = Tap(orientation="vertical", size_hint_x=None, width=dp(118), padding=(dp(8), dp(8)),
                            spacing=dp(4))

                def cbg(w, *a):
                    w.canvas.before.clear()
                    with w.canvas.before:
                        Color(*UW.C["card"])
                        RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(16)])
                cardw.bind(pos=cbg, size=cbg)
                from kivy.uix.anchorlayout import AnchorLayout
                ra = AnchorLayout(size_hint_y=None, height=dp(66))
                ring = UW.ScoreRing(size_hint=(None, None), size=(dp(64), dp(64)), thickness=dp(6), text_size_sp=17)
                ring.set_score(it.get("score"), animate=False)
                ra.add_widget(ring)
                cardw.add_widget(ra)
                nm = Label(text=str(it["name"]), color=UW.C["ink"], font_size=sp(12), halign="center",
                           valign="top", max_lines=3)
                nm.bind(size=lambda w, s: setattr(w, "text_size", s))
                cardw.add_widget(nm)
                cardw.bind(on_release=lambda w, code=it.get("code"): self.lookup(code))
                strip.add_widget(cardw)
            sv.add_widget(strip)
            box.add_widget(sv)

    # ================================================================== σάρωση
    def _log(self, msg):
        try:
            F.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(F.DATA_DIR / "errors.log", "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%d/%m %H:%M ") + msg[:600] + "\n")
        except Exception:  # noqa: BLE001
            pass

    def start_scan(self):
        if not SC.available():
            self.home_status.text = "Ο σαρωτής λειτουργεί στο κινητό. Γράψε τον κωδικό στο πεδίο."
            return
        self.home_status.text = "Άνοιγμα σαρωτή…"
        try:
            SC.start()
        except Exception as e:  # noqa: BLE001
            self._log(f"Σαρωτής: {e}")
            self.home_status.text = (f"[color={UW.hexc(UW.BAD)}]Ο σαρωτής δεν άνοιξε.[/color] Αιτία: {esc(str(e)[:300])}"
                                     "\nΓράψε προσωρινά τον κωδικό στο πεδίο.")
            return
        self._scan_started = time.time()
        Clock.schedule_interval(self._scan_poll, 0.25)

    def _scan_poll(self, dt):
        try:
            busy, res, err = SC.poll()
        except Exception as e:  # noqa: BLE001
            self._log(f"Σαρωτής (poll): {e}")
            return False
        if busy and time.time() - self._scan_started < 180:
            ph = SC.phase() if hasattr(SC, "phase") else None
            if ph == "install":
                self.home_status.text = "Προετοιμασία του σαρωτή Google (μόνο την πρώτη φορά, θέλει internet)…"
            elif ph == "installed":
                self.home_status.text = "Ο σαρωτής εγκαταστάθηκε. Ανοίγει…"
            elif ph == "scan":
                self.home_status.text = ""
            return None
        if res:
            self.home_status.text = ""
            self.lookup(res)
        elif err == "cancel":
            self.home_status.text = ""
        elif err:
            self._log(f"Σαρωτής: {err}")
            self.home_status.text = (f"[color={UW.hexc(UW.BAD)}]Ο σαρωτής απέτυχε.[/color] Αιτία: {esc(str(err)[:300])}"
                                     "\nΑν είναι η πρώτη φορά, περίμενε ένα λεπτό (η Google κατεβάζει τον σαρωτή) "
                                     "και ξαναπάτα. Βεβαιώσου ότι το Google Play Services είναι ενημερωμένο.")
        return False

    # ================================================================== αναζήτηση barcode
    def lookup(self, code):
        code = F.clean_code(code or "")
        st = getattr(self, "home_status", None)
        if len(code) < 6:
            if st:
                st.text = "Γράψε ολόκληρο τον κωδικό (8 ή 13 ψηφία)."
            return
        if self.busy:
            return
        self.busy = True
        self._token += 1
        token = self._token
        if st:
            st.text = f"Αναζήτηση {code} σε 6 πηγές…"

        def watchdog(dt):
            if self.busy and self._token == token:
                self._token += 1
                self.busy = False
                if st:
                    st.text = "Η αναζήτηση άργησε πολύ (αργή σύνδεση;). Δοκίμασε ξανά."
        Clock.schedule_once(watchdog, 25)

        def work():
            try:
                p, note = P.fetch(code)
                err = None if p else "NOTFOUND"
                if p and note:
                    p = dict(p, _note=note)
            except Exception as e:  # noqa: BLE001
                p, err = None, f"Δεν ήταν δυνατή η αναζήτηση ({str(e)[:80]})"
            Clock.schedule_once(lambda dt: self._got(p, err, code) if self._token == token else None)
        threading.Thread(target=work, daemon=True).start()

    def _got(self, p, err, code):
        self.busy = False
        st = getattr(self, "home_status", None)
        if err == "NOTFOUND":
            if st:
                st.text = ""
            return self.open_add_kind(code)
        if err:
            if st:
                st.text = err
            return
        if st:
            st.text = ""
        self.open_product(p)

    # ================================================================== σελίδα προϊόντος
    def open_product(self, p, record=True):
        d = P.score_any(p)
        s = d["score"]
        if record:
            F.add_history(p, s)
        self.current = p
        box = self.page("product")
        kind = P.KINDS.get(p.get("kind", "food"), "Προϊόν")

        # --- κεφαλή: φωτογραφία, όνομα, κύκλος βαθμού
        head = self.card(box)
        top = BoxLayout(size_hint_y=None, height=dp(150), spacing=dp(12))
        left = BoxLayout(orientation="vertical", spacing=dp(4))
        img = Image(size_hint_y=None, height=dp(0), fit_mode="contain")
        url = F.image_url(p)
        left.add_widget(UW.text(f"[size=12sp][color={UW.hexc(UW.PRIMARY)}][b]{esc(kind.upper())}[/b][/color][/size]"))
        left.add_widget(UW.text(f"[b]{esc(P.name_any(p))}[/b]", size=17))
        if p.get("brands"):
            left.add_widget(UW.text(esc(str(p["brands"]).split(",")[0]), size=13, color=UW.C["muted"]))
        top.add_widget(left)
        ring = UW.ScoreRing(size_hint=(None, None), size=(dp(130), dp(130)), thickness=dp(11), text_size_sp=32)
        top.add_widget(ring)
        head.add_widget(top)
        Clock.schedule_once(lambda dt: ring.set_score(s), 0.05)
        verdict = F.verdict(s) if s is not None else "Χωρίς αντικειμενικό βαθμό"
        chips = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
        chips.add_widget(UW.Chip(verdict, UW.score_rgba(s)))
        if P.greek_barcode(p.get("code", "")):
            chips.add_widget(UW.Chip("Ελληνικό barcode", UW.PRIMARY))
        if p.get("nova_group"):
            try:
                nv = int(p["nova_group"])
                chips.add_widget(UW.Chip(f"NOVA {nv}", (0.0, 0.6, 0.35, 1) if nv <= 2 else
                                         ((0.94, 0.55, 0.0, 1) if nv == 3 else (0.85, 0.2, 0.15, 1))))
            except (TypeError, ValueError):
                pass
        eco = F.eco_grade(p)
        if eco:
            chips.add_widget(UW.Chip(f"Eco {eco}", (0.1, 0.55, 0.45, 1)))
        chips.add_widget(Widget())
        head.add_widget(chips)
        if d.get("confidence"):
            head.add_widget(UW.text(f"Αξιοπιστία βαθμού: {d['confidence']}", size=12, color=UW.C["muted"]))
        grade = (p.get("nutriscore_grade") or "").lower()
        if grade in "abcde" and grade and p.get("kind", "food") == "food":
            head.add_widget(UW.text("[b]Nutri-Score[/b]", size=13))
            head.add_widget(UW.NutriStrip(grade=grade, size_hint_y=None, height=dp(44)))
        if url:
            head.add_widget(img)

            def load():
                try:
                    path = F.download_image(url, p.get("code"))
                except Exception:  # noqa: BLE001
                    path = None

                def put(dt):
                    if path:
                        img.source = path
                        img.height = dp(170)
                Clock.schedule_once(put)
            threading.Thread(target=load, daemon=True).start()
        if p.get("_note"):
            head.add_widget(UW.text(esc(p["_note"]), size=12, color=UW.WARN))

        # --- ειδοποιήσεις προφίλ
        alerts = H.check(p)
        lvl = H.worst(alerts)
        if lvl:
            col = UW.BAD if lvl == "red" else UW.WARN
            a = UW.CardBox(pad=12)
            a.add_widget(UW.text(f"[b]{'ΑΚΑΤΑΛΛΗΛΟ ΓΙΑ ΤΟ ΠΡΟΦΙΛ ΣΟΥ' if lvl == 'red' else 'ΠΡΟΣΟΧΗ'}[/b]",
                                 size=15, color=col))
            for _, m in alerts:
                a.add_widget(UW.text("• " + esc(m), size=14))
            box.add_widget(a)
            if lvl == "red" and record:
                self.vibrate()

        # --- γρήγορες ενέργειες
        acts = BoxLayout(size_hint_y=None, height=dp(84), spacing=dp(4))
        alt_section = {}

        def to_list():
            L.shop_add(p)
            lst_btn.lab.text = "Μπήκε!"

        def to_compare():
            lst = H.add_compare(p)
            if len(lst) >= 2:
                self.open_compare()
            else:
                cmp_btn.lab.text = "Διάλεξε 2ο"

        def to_alts():
            sec = alt_section.get("s")
            if sec and not sec.opened:
                sec.toggle()
            if sec:
                Clock.schedule_once(lambda dt: self.pages["product"][0].scroll_to(sec, padding=dp(20)), 0.1)
        lst_btn = UW.IconButton("plus", "Στη λίστα")
        cmp_btn = UW.IconButton("compare", "Σύγκριση")
        alt_btn = UW.IconButton("swap", "Εναλλακτικές", color=UW.GOOD)
        sh_btn = UW.IconButton("share", "Κοινοποίηση")
        lst_btn.bind(on_release=lambda *a: to_list())
        cmp_btn.bind(on_release=lambda *a: to_compare())
        alt_btn.bind(on_release=lambda *a: to_alts())
        sh_btn.bind(on_release=lambda *a: self.share(P.share_text(p, d)))
        for w in (lst_btn, cmp_btn, alt_btn, sh_btn):
            acts.add_widget(w)
        box.add_widget(acts)

        # --- ενότητες
        box.add_widget(UW.Section("Γιατί αυτός ο βαθμός", opened=True,
                                  builder=lambda b: self._sec_why(b, p, d)))
        if p.get("kind", "food") in ("food", "petfood") and F.nutrition_table(p):
            box.add_widget(UW.Section("Διατροφική αξία (ανά 100 g)", opened=True,
                                      builder=lambda b: self._sec_nutrition(b, p)))
        if F.ingredients_text(p) or F.allergens(p)[0] or F.allergens(p)[1] or F.labels(p):
            box.add_widget(UW.Section("Συστατικά & αλλεργιογόνα", builder=lambda b: self._sec_ingredients(b, p)))
        if F.additive_codes(p):
            box.add_widget(UW.Section(f"Πρόσθετα ({len(F.additive_codes(p))})",
                                      builder=lambda b: self._sec_additives(b, p)))
        box.add_widget(UW.Section("Τιμές & ιστορικό τιμών", opened=bool(self._price_msgs),
                                  builder=lambda b: self._sec_prices(b, p)))
        sec = UW.Section("Εναλλακτικές επιλογές", builder=lambda b: self._sec_alternatives(b, p))
        alt_section["s"] = sec
        box.add_widget(sec)
        if P.extra_facts(p):
            box.add_widget(UW.Section("Περισσότερες πληροφορίες", builder=lambda b: self._sec_facts(b, p)))
        box.add_widget(UW.Section("Η γνώμη μου", builder=lambda b: self._sec_opinion(b, p)))
        box.add_widget(UW.Section("Πηγές & έλεγχοι", builder=lambda b: self._sec_links(b, p)))
        if p.get("kind") == "medicine":
            self.message(box, P.MEDICINE_NOTE, UW.BAD)
        src = ", ".join(p.get("sources") or []) or ("δική σου καταχώριση" if p.get("local")
                                                    else P.SOURCE_NAMES.get(p.get("db"), "Open Food Facts"))
        box.add_widget(UW.text(f"Στοιχεία: {esc(src)} · κωδικός {esc(p.get('code', ''))}", size=11,
                               color=UW.C["muted"]))
        self.show("product")

    # ---------------------------------------------------------------- ενότητες προϊόντος
    def _sec_why(self, b, p, d):
        for w in d["why"]:
            b.add_widget(UW.text("• " + esc(w)))
        for name, found, reason in d.get("flags", []):
            b.add_widget(UW.text(f"[color={UW.hexc(UW.BAD)}][b]{esc(name)}[/b][/color]: {esc(', '.join(found))}\n"
                                 f"[size=12sp]{esc(reason)}[/size]"))
        b.add_widget(UW.text("Ο βαθμός αφορά τη διατροφική ποιότητα (ή τα συστατικά, στα καλλυντικά), όχι τη "
                             "γεύση ή τη φρεσκάδα.", size=11, color=UW.C["muted"]))

    def _sec_nutrition(self, b, p):
        lights = {lbl: lv for lbl, v, lv in F.nutrient_lights(p)}
        maxv = {"Λιπαρά": 40, "  κορεσμένα": 15, "  σάκχαρα": 45, "Αλάτι": 3, "Ενέργεια": 700, "Υδατάνθρακες": 90,
                "Φυτικές ίνες": 12, "Πρωτεΐνες": 35}
        keymap = {"  σάκχαρα": "Ζάχαρη", "Αλάτι": "Αλάτι", "  κορεσμένα": "Κορεσμένα λιπαρά", "Λιπαρά": "Λιπαρά"}
        for lbl, v, unit in F.nutrition_table(p):
            lv = lights.get(keymap.get(lbl, ""))
            val = f"{v:.0f}" if unit == "kcal" else gr(v)
            b.add_widget(UW.NutrientBar(lbl.strip().capitalize(), val, f" {unit}", lv, maxv.get(lbl, 50)))

    def _sec_ingredients(self, b, p):
        labels = F.labels(p)
        palm = F.palm_oil(p)
        if labels or palm:
            row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
            for lb in labels[:4]:
                row.add_widget(UW.Chip(esc(lb), UW.GOOD))
            if palm:
                row.add_widget(UW.Chip(palm, UW.BAD if "Περιέχει" in palm else UW.GOOD))
            row.add_widget(Widget())
            b.add_widget(row)
        al, tr = F.allergens(p)
        if al:
            b.add_widget(UW.text(f"[color={UW.hexc(UW.BAD)}][b]Περιέχει:[/b] {esc(', '.join(al))}[/color]"))
        if tr:
            b.add_widget(UW.text(f"[b]Ίχνη:[/b] {esc(', '.join(tr))}"))
        ingr = F.ingredients_text(p)
        if ingr:
            b.add_widget(UW.text(esc(ingr[:1200]), size=13))

    def _sec_additives(self, b, p):
        for code, name, bad in F.additives_named(p):
            t = f"[b]{code}[/b]" + (f" – {esc(name)}" if name else "")
            if bad:
                t = f"[color={UW.hexc(UW.BAD)}]{t} · καλύτερα να αποφεύγεται[/color]"
            b.add_widget(UW.text(t))

    def _sec_prices(self, b, p):
        msgs, self._price_msgs = self._price_msgs, []
        for kind, m in msgs:
            col = UW.BAD if kind == "up" else UW.GOOD
            head = {"up": "ΑΚΡΙΒΥΝΕ", "down": "ΦΘΗΝΥΝΕ", "best": "ΚΑΛΥΤΕΡΗ ΤΙΜΗ"}[kind]
            b.add_widget(UW.text(f"[color={UW.hexc(col)}][b]{head}[/b][/color]  {esc(m)}"))
        rows = F.prices_for(p.get("code"))
        if rows:
            best = rows[0]["price"]
            import health as _H
            for r in rows:
                pu = _H.per_unit(r["price"], p)
                unit = f" · {euro(pu[0])}/{'κιλό' if pu[1] == 'kg' else 'λίτρο'}" if pu else ""
                star = f"  [color={UW.hexc(UW.GOOD)}][b]φθηνότερο[/b][/color]" if r["price"] == best else ""
                b.add_widget(UW.text(f"{esc(r['store'])}{' – ' + esc(r['region']) if r.get('region') else ''}: "
                                     f"[b]{euro(r['price'])}[/b]{unit} [size=11sp]({r['date']})[/size]{star}"))
        else:
            b.add_widget(UW.text("Καμία τιμή ακόμα. Γράψε την τιμή που βλέπεις στο ράφι:", color=UW.C["muted"]))
        chart = UX.chart_block(p.get("code"))
        if chart is not None:
            b.add_widget(chart)
        r1 = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        store = Spinner(text=F.get_setting("store", F.STORES[0]), values=F.STORES)
        reg = TextInput(text=F.get_setting("region", ""), hint_text="Περιοχή", multiline=False)
        r1.add_widget(store)
        r1.add_widget(reg)
        b.add_widget(r1)
        r2 = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        price = TextInput(hint_text="Τιμή €", input_filter="float", multiline=False)
        save = Button(text="Αποθήκευση τιμής", bold=True, background_normal="", background_color=UW.GOOD)

        def do_save(*a):
            try:
                v = float(price.text.replace(",", "."))
            except ValueError:
                return
            F.set_setting("store", store.text)
            F.set_setting("region", reg.text.strip())
            self._price_msgs = F.add_price(p, store.text, reg.text.strip(), v)
            self.open_product(p, record=False)
        save.bind(on_release=do_save)
        r2.add_widget(price)
        r2.add_widget(save)
        b.add_widget(r2)
        e = Button(text="Δες τιμές στο e-katanalotis", size_hint_y=None, height=dp(42), background_normal="",
                   background_color=UW.C["line"], color=UW.C["ink"])

        def ek(*a):
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(F.name_of(p))
            except Exception:  # noqa: BLE001
                pass
            webbrowser.open(F.EKATANALOTIS)
        e.bind(on_release=ek)
        b.add_widget(e)

    def _sec_alternatives(self, b, p):
        info = UW.text("Αναζήτηση εναλλακτικών…", color=UW.C["muted"])
        b.add_widget(info)

        def work():
            try:
                res, title = P.alternatives_any(p)
            except Exception:  # noqa: BLE001
                res, title = [], ""
            Clock.schedule_once(lambda dt: done(res, title))

        def done(res, title):
            b.clear_widgets()
            if not res:
                b.add_widget(UW.text("Δεν βρέθηκαν εναλλακτικές στις βάσεις. Δες τις «Πηγές & έλεγχοι».",
                                     color=UW.C["muted"]))
                return
            b.add_widget(UW.text(f"[b]{esc(title)}[/b]", size=13, color=UW.C["muted"]))
            for sc, x in res:
                extra = f" · {esc(x['price_range'])}" if x.get("price_range") else ""
                sub = (F.verdict(sc) if sc is not None else P.KINDS.get(x.get("kind"), "")) + extra
                self.product_row(b, x, sc, sub, lambda xx=x: self.open_product(xx))
        threading.Thread(target=work, daemon=True).start()

    def _sec_facts(self, b, p):
        for k, v in P.extra_facts(p):
            b.add_widget(UW.text(f"[b]{esc(k)}:[/b] {esc(v)}"))

    def _sec_opinion(self, b, p):
        code = p.get("code", "")
        info = P.user_info(code)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        lab = Label(text=gr(info["rating"]) if info.get("rating") is not None else "–", bold=True, font_size=sp(20),
                    color=UW.C["ink"], size_hint_x=None, width=dp(54))
        sl = Slider(min=1, max=10, step=0.1, value=info.get("rating") or 5)
        sl.bind(value=lambda w, v: setattr(lab, "text", gr(round(v, 1))))
        sl.bind(on_touch_up=lambda w, t: P.set_user_info(code, rating=round(w.value, 1)) if w.collide_point(*t.pos)
                else None)
        row.add_widget(lab)
        row.add_widget(sl)
        b.add_widget(row)
        notes = TextInput(text=info.get("notes", ""), hint_text="Σημειώσεις", multiline=True, size_hint_y=None,
                          height=dp(76))
        notes.bind(focus=lambda w, f: P.set_user_info(code, notes=w.text) if not f else None)
        b.add_widget(notes)
        if p.get("kind") == "electronics":
            end = P.warranty_end(info)
            b.add_widget(UW.text("[b]Εγγύηση[/b]" + (f" έως [b]{end:%d/%m/%Y}[/b]" if end else "")))
            wr = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
            bought = TextInput(text=info.get("bought", ""), hint_text="Αγορά ηη/μμ/εεεε", multiline=False)
            months = TextInput(text=str(info.get("warranty_months", "")), hint_text="Μήνες", input_filter="int",
                               multiline=False)
            ok = Button(text="OK", size_hint_x=None, width=dp(60))
            ok.bind(on_release=lambda *a: P.set_user_info(code, bought=bought.text.strip(),
                                                          warranty_months=months.text.strip()))
            for w in (bought, months, ok):
                wr.add_widget(w)
            b.add_widget(wr)

    def _sec_links(self, b, p):
        links = []
        page = P.db_page(p)
        if page:
            links.append(("Η σελίδα του προϊόντος στη βάση", page))
        links += P.links_for(p)
        for t, u in links:
            bt = Button(text=t, size_hint_y=None, height=dp(42), background_normal="", background_color=UW.C["line"],
                        color=UW.C["ink"])
            bt.bind(on_release=lambda w, url=u: webbrowser.open(url))
            b.add_widget(bt)

    # ================================================================== Αναζήτηση
    def build_search(self, term="", results=None):
        box = self.page("search")
        c = self.card(box, pad=12)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        ti = TextInput(text=term, hint_text="π.χ. γάλα, γιαούρτι, σαμπουάν", multiline=False, font_size=sp(16),
                       padding=(dp(10), dp(12)))
        go = Button(text="Αναζήτηση", bold=True, size_hint_x=None, width=dp(116), background_normal="",
                    background_color=UW.PRIMARY)
        go.bind(on_release=lambda *a: self.do_search(ti.text))
        ti.bind(on_text_validate=lambda *a: self.do_search(ti.text))
        row.add_widget(ti)
        row.add_widget(go)
        c.add_widget(row)
        c.add_widget(UW.text("Ψάχνει σε τρόφιμα και καλλυντικά. Το καλύτερο εμφανίζεται πρώτο.", size=12,
                             color=UW.C["muted"]))
        self.search_info = UW.text("", size=13, color=UW.C["muted"])
        box.add_widget(self.search_info)
        if results:
            for sc, p in results[:40]:
                lv = H.worst(H.check(p))
                mark = (f"  [color={UW.hexc(UW.BAD)}][b]ακατάλληλο για σένα[/b][/color]" if lv == "red" else
                        (f"  [color={UW.hexc(UW.WARN)}][b]προσοχή[/b][/color]" if lv == "orange" else ""))
                kind = "" if p.get("kind") == "food" else f" · {P.KINDS.get(p.get('kind'), '')}"
                self.product_row(box, p, sc, f"{F.verdict(sc)}{kind}{mark}", lambda pp=p: self.open_product(pp))

    def do_search(self, term):
        term = term.strip()
        if not term or self.search_busy:
            return
        self.search_busy = True
        self.search_info.text = f"Αναζήτηση «{esc(term)}»… (έως 20 δευτερόλεπτα)"

        def work():
            try:
                res, err = P.search_all(term), None
            except Exception as e:  # noqa: BLE001
                res, err = [], str(e)[:100]
            Clock.schedule_once(lambda dt: done(res, err))

        def done(res, err):
            self.search_busy = False
            if err or not res:
                self.search_info.text = err or "Δεν βρέθηκε τίποτα. Δοκίμασε άλλη λέξη ή σκάναρε το barcode."
                return
            scored = sorted(((P.score_any(p)["score"], p) for p in res),
                            key=lambda sp_: -(sp_[0] if sp_[0] is not None else -1))
            self.build_search(term, scored)
            self.search_info.text = f"{len(scored)} αποτελέσματα"
        threading.Thread(target=work, daemon=True).start()

    # ================================================================== Λίστα αγορών
    def build_list(self):
        box = self.page("list")
        sm = L.shop_summary()
        if sm["items"]:
            c = self.card(box)
            c.add_widget(UW.text(f"[b]{sm['items']} {'προϊόν' if sm['items'] == 1 else 'προϊόντα'}[/b] · "
                                 f"{sm['qty']} τεμ.", size=16))
            if sm["priced"]:
                c.add_widget(UW.text(f"Κόστος (φθηνότερη τιμή του καθενός): [b]{euro(sm['best_total'])}[/b]"))
            if sm["avg_score"] is not None:
                c.add_widget(UW.text(f"Μέση ποιότητα καλαθιού: [b][color={UW.hexc(UW.score_rgba(sm['avg_score']))}]"
                                     f"{gr(round(sm['avg_score'], 1))}/10[/color][/b]"))
            for i, (st, v) in enumerate(sm["stores"][:4]):
                tag = (f"  [color={UW.hexc(UW.GOOD)}][b]φθηνότερο για όλο το καλάθι[/b][/color]"
                       if i == 0 and v["covered"] == sm["priced"] else "")
                c.add_widget(UW.text(f"{esc(st)}: {euro(v['total'])} ({v['covered']}/{sm['priced']}){tag}", size=13))
            if sm["missing"]:
                c.add_widget(UW.text(f"Χωρίς τιμή: {esc(', '.join(sm['missing'][:6]))}", size=12,
                                     color=UW.C["muted"]))
        c = self.card(box, pad=12)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        ti = TextInput(hint_text="Πρόσθεσε π.χ. ψωμί", multiline=False, padding=(dp(10), dp(11)))
        add = Button(text="+", bold=True, font_size=sp(22), size_hint_x=None, width=dp(56), background_normal="",
                     background_color=UW.PRIMARY)

        def do_add(*a):
            if ti.text.strip():
                L.shop_add(name=ti.text)
                self.build_list()
        add.bind(on_release=do_add)
        ti.bind(on_text_validate=do_add)
        row.add_widget(ti)
        row.add_widget(add)
        c.add_widget(row)
        items = L.shop_items()
        if not items:
            box.add_widget(UW.text("Η λίστα είναι άδεια. Στη σελίδα ενός προϊόντος πάτα «Στη λίστα».",
                                   color=UW.C["muted"]))
        for it in items:
            card = UW.CardBox(pad=8, orientation="horizontal")
            card.bind(minimum_height=card.setter("height"))
            r = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
            cb = CheckBox(active=it.get("done", False), size_hint_x=None, width=dp(40), color=UW.C["ink"])
            cb.bind(active=lambda w, v, iid=it["id"]: L.shop_update(iid, done=bool(v)))
            sc = f" · {gr(it['score'])}/10" if it.get("score") is not None else ""
            lab = Label(text=f"[b]{esc(it['name'])}[/b]\n[size=12sp]x{it.get('qty', 1)}{sc}[/size]", markup=True,
                        color=UW.C["muted"] if it.get("done") else UW.C["ink"], halign="left", valign="middle",
                        shorten=True)
            lab.bind(size=lambda w, s: setattr(w, "text_size", s))
            r.add_widget(cb)
            r.add_widget(lab)
            for t, fn in (("-", lambda i=it: (L.shop_update(i["id"], qty=i.get("qty", 1) - 1), self.build_list())),
                          ("+", lambda i=it: (L.shop_update(i["id"], qty=i.get("qty", 1) + 1), self.build_list())),
                          ("x", lambda i=it: self.undo.run(["shopping.json"], f"Αφαιρέθηκε: {i['name'][:28]}",
                                                           lambda: L.shop_remove(i["id"]), self.build_list))):
                bt = Button(text=t, size_hint_x=None, width=dp(40), background_normal="",
                            background_color=UW.C["line"], color=UW.C["ink"], font_size=sp(18))
                bt.bind(on_release=lambda w, f=fn: f())
                r.add_widget(bt)
            card.add_widget(r)
            box.add_widget(card)
        if items:
            self.ghost(box, "Αφαίρεση όσων αγόρασα", lambda: self.undo.run(
                ["shopping.json"], "Αφαιρέθηκαν όσα αγόρασες", L.shop_clear_done, self.build_list))
            self.btn(box, "Κοινοποίηση λίστας", lambda: self.share("Λίστα αγορών:\n" + "\n".join(
                f"- {x['name']} x{x.get('qty', 1)}" for x in L.shop_items() if not x.get("done"))))

    # ================================================================== Εγώ
    def build_me(self):
        box = self.page("me")
        prof = H.load_profile()
        c = self.card(box)
        n = len(prof.get("allergens", [])) + len(prof.get("diets", []))
        c.add_widget(UW.text("[b]Προφίλ υγείας[/b]", size=16))
        c.add_widget(UW.text(f"{n} επιλογές (αλλεργίες, διατροφή)" if n else
                             "Δήλωσε αλλεργίες και διατροφή, για να σε ειδοποιεί η εφαρμογή.", color=UW.C["muted"]))
        self.btn(c, "Ρύθμιση προφίλ", self.open_profile, h=46)
        c2 = self.card(box)
        c2.add_widget(UW.text("[b]Τα δεδομένα μου[/b]", size=16))
        for t, fn in (("Ιστορικό σκαναρισμάτων", self.open_history), ("Τιμές ανά κατάστημα", self.open_prices),
                      ("Σύγκριση δύο προϊόντων", self.open_compare)):
            self.ghost(c2, t, fn, h=44)
        c3 = self.card(box)
        c3.add_widget(UW.text("[b]Εμφάνιση[/b]", size=16))
        u = UX.ui_settings()
        r1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        r1.add_widget(Label(text="Γράμματα", color=UW.C["ink"], size_hint_x=0.4))
        fs = Spinner(text=u["font"], values=list(UX.FONT_SCALES))
        r1.add_widget(fs)
        c3.add_widget(r1)
        r2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        r2.add_widget(Label(text="Θέμα", color=UW.C["ink"], size_hint_x=0.4))
        th = Spinner(text="Σκοτεινό" if u["theme"] == "dark" else "Φωτεινό", values=["Φωτεινό", "Σκοτεινό"])
        r2.add_widget(th)
        c3.add_widget(r2)
        note = UW.text("", size=12, color=UW.WARN)
        c3.add_widget(note)

        def changed(*a):
            UX.save_ui(font=fs.text, theme="dark" if th.text == "Σκοτεινό" else "light")
            note.text = "Αποθηκεύτηκε. Εφαρμόζεται όταν ξανανοίξεις την εφαρμογή."
        fs.bind(text=changed)
        th.bind(text=changed)
        self.ghost(c3, "Κλείσιμο τώρα (για να εφαρμοστεί)", self.stop, h=42)
        c4 = self.card(box)
        c4.add_widget(UW.text("[b]Βοήθεια[/b]", size=16))
        self.ghost(c4, "Οδηγός χρήσης", lambda: self.show_guide(0), h=44)
        cl = self.ghost(c4, "Καθαρισμός αποθηκευμένων αναζητήσεων", lambda: (P.clear_cache(),
                                                                            setattr(cl, "text", "Έγινε")), h=44)
        c4.add_widget(UW.text("Πηγές: Open Food Facts, Open Beauty Facts, Open Pet Food Facts, Open Products Facts, "
                              "UPCitemdb, Wikidata. Σάρωση: Google ML Kit.", size=11, color=UW.C["muted"]))
        err = self._last_error()
        if err:
            c4.add_widget(UW.text(f"Τελευταίο σφάλμα που αποφεύχθηκε: {esc(err)}", size=10, color=UW.C["muted"]))

    def _last_error(self):
        try:
            txt = (F.DATA_DIR / "errors.log").read_text(encoding="utf-8").strip().splitlines()
            return txt[-1][:160] if txt else ""
        except Exception:  # noqa: BLE001
            return ""

    # ================================================================== προφίλ
    def open_profile(self):
        box = self.page("profile")
        prof = H.load_profile()
        checks = {}
        for title, items in (("Αλλεργίες", [(k, F.ALLERGENS.get(k, k)) for k in H.ALLERGEN_KEYS]),
                             ("Διατροφή και υγεία", H.DIETS)):
            c = self.card(box)
            c.add_widget(UW.text(f"[b]{title}[/b]", size=16))
            for k, label in items:
                r = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
                cb = CheckBox(active=k in prof.get("allergens", []) + prof.get("diets", []), size_hint_x=None,
                              width=dp(40), color=UW.C["ink"])
                lb = Label(text=label, color=UW.C["ink"], halign="left", valign="middle")
                lb.bind(size=lambda w, s: setattr(w, "text_size", s))
                r.add_widget(cb)
                r.add_widget(lb)
                c.add_widget(r)
                checks[k] = cb

        def save():
            H.save_profile({"allergens": [k for k in H.ALLERGEN_KEYS if checks[k].active],
                            "diets": [k for k, _ in H.DIETS if checks[k].active]})
            self.back()
        self.btn(box, "ΑΠΟΘΗΚΕΥΣΗ", save, color=UW.GOOD)
        box.add_widget(UW.text("Οι ειδοποιήσεις βασίζονται στα στοιχεία της βάσης και στα συστατικά. Για σοβαρή "
                               "αλλεργία διάβαζε πάντα και την ετικέτα. Τα όρια δεν αντικαθιστούν τον γιατρό σου.",
                               size=11, color=UW.C["muted"]))
        self.show("profile")

    # ================================================================== ιστορικό / τιμές / σύγκριση
    def open_history(self):
        box = self.page("history")
        h = F.load_history()
        if not h:
            box.add_widget(UW.text("Δεν έχεις σκανάρει ακόμα κάτι.", color=UW.C["muted"]))
        for it in h[:80]:
            self.product_row(box, it["name"], it.get("score"), f"{F.verdict(it.get('score'))} · {it['when']}",
                             lambda code=it.get("code"): self.lookup(code))
        self.show("history")

    def open_prices(self):
        box = self.page("prices")
        regs = ["Όλες"] + F.regions()
        sel = getattr(self, "_region", "Όλες")
        if sel not in regs:
            sel = "Όλες"
        sp_ = Spinner(text=sel, values=regs, size_hint_y=None, height=dp(44))
        sp_.bind(text=lambda w, v: (setattr(self, "_region", v), self.open_prices()))
        box.add_widget(sp_)
        data = F.cheapest_by_category(sel)
        if not data:
            box.add_widget(UW.text("Δεν έχεις καταγράψει ακόμα τιμές. Στη σελίδα ενός προϊόντος άνοιξε "
                                   "«Τιμές & ιστορικό τιμών».", color=UW.C["muted"]))
        for cat in F.CATEGORIES:
            if cat not in data:
                continue
            box.add_widget(UW.text(f"[b]{esc(cat)}[/b]", size=15))
            for rec, n in data[cat]:
                sub = (f"[color={UW.hexc(UW.GOOD)}][b]{euro(rec['price'])}[/b][/color] στο {esc(rec['store'])}"
                       f"{' – ' + esc(rec['region']) if rec.get('region') else ''} · {n} καταγραφές")
                self.product_row(box, rec["name"], rec.get("score"), sub, lambda c_=rec["code"]: self.lookup(c_))
        self.show("prices")

    def open_compare(self):
        box = self.page("compare")
        lst = H.load_compare()
        if len(lst) < 2:
            self.message(box, "Άνοιξε ένα προϊόν και πάτα «Σύγκριση». Μόλις διαλέξεις δύο, εμφανίζονται εδώ "
                              "δίπλα-δίπλα." + (f"\n\nΈχεις διαλέξει: {esc(F.name_of(lst[0]))}" if lst else ""))
            self.show("compare")
            return
        a, b = lst
        top = BoxLayout(size_hint_y=None, height=dp(170), spacing=dp(10))
        for tag, p in (("Α", a), ("Β", b)):
            c = UW.CardBox(pad=10)
            c.size_hint_y = None
            ring = UW.ScoreRing(size_hint_y=None, height=dp(96), thickness=dp(8), text_size_sp=22)
            c.add_widget(ring)
            Clock.schedule_once(lambda dt, r=ring, pp=p: r.set_score(P.score_any(pp)["score"]), 0.05)
            nm = Label(text=f"[b]{tag}[/b] {esc(F.name_of(p))}", markup=True, color=UW.C["ink"], font_size=sp(12),
                       halign="center", valign="top", size_hint_y=None, height=dp(44))
            nm.bind(size=lambda w, s: setattr(w, "text_size", s))
            c.add_widget(nm)
            top.add_widget(c)
        box.add_widget(top)
        v = H.verdict(a, b)
        if v:
            self.message(box, f"[b]{esc(v)}[/b]", UW.GOOD)
        c = self.card(box, pad=10)
        for label, ta, tb, win in H.compare_rows(a, b):
            r = BoxLayout(size_hint_y=None, height=dp(34))
            for txt_, w in ((label, None), (ta, "a"), (tb, "b")):
                good = win == w and w is not None
                lb = Label(text=("[b]" + esc(txt_) + "[/b]") if good else esc(txt_), markup=True,
                           color=UW.GOOD if good else UW.C["ink"], font_size=sp(13), halign="center" if w else "left",
                           valign="middle")
                lb.bind(size=lambda w_, s: setattr(w_, "text_size", s))
                r.add_widget(lb)
            c.add_widget(r)
        self.ghost(box, "Νέα σύγκριση", lambda: self.undo.run(["compare.json"], "Η σύγκριση καθαρίστηκε",
                                                               H.clear_compare, self.open_compare))
        self.show("compare")

    # ================================================================== νέο προϊόν (δεν βρέθηκε)
    def open_add_kind(self, code):
        box = self.page("add")
        self.message(box, f"[b]Το προϊόν δεν βρέθηκε[/b] (κωδικός {code}). Έψαξα σε 6 πηγές. Πρόσθεσέ το μία φορά "
                          "και θα το αναγνωρίζει πάντα. Τι είδος είναι;"
                     + (f"\n\n{esc(P.GREEK_NOTE)}" if P.greek_barcode(code) else ""))
        for k, label in P.KINDS.items():
            self.ghost(box, label, lambda kind=k: self.open_add_form(code, kind), h=50)
        self.show("add")

    def open_add_form(self, code, kind):
        box = self.page("add")
        c = self.card(box)
        c.add_widget(UW.text(f"[b]{esc(P.KINDS[kind])}[/b] · κωδικός {code}", size=15))
        f = {}

        def field(key, label, numeric=False, hint=""):
            c.add_widget(UW.text(label, size=12, color=UW.C["muted"]))
            ti = TextInput(multiline=False, hint_text=hint, size_hint_y=None, height=dp(44),
                           input_filter="float" if numeric else None)
            c.add_widget(ti)
            f[key] = ti
        field("name", "Όνομα")
        field("brand", "Μάρκα")
        field("qty", "Ποσότητα", hint="π.χ. 500 g")
        cat = bev = nova = None
        if kind == "food":
            c.add_widget(UW.text("Κατηγορία", size=12, color=UW.C["muted"]))
            cat = Spinner(text="Άλλο", values=F.CATEGORIES, size_hint_y=None, height=dp(44))
            c.add_widget(cat)
            bev = CheckBox(size_hint_x=None, width=dp(40), color=UW.C["ink"])
            rb = BoxLayout(size_hint_y=None, height=dp(40))
            rb.add_widget(bev)
            rb.add_widget(Label(text="Είναι ρόφημα", color=UW.C["ink"], halign="left"))
            c.add_widget(rb)
            c.add_widget(UW.text("[b]Διατροφικός πίνακας ανά 100 g/ml[/b]"))
            for key, label in (("kcal", "Ενέργεια (kcal)"), ("sugars", "Σάκχαρα (g)"), ("sat", "Κορεσμένα (g)"),
                               ("salt", "Αλάτι (g)"), ("fiber", "Φυτικές ίνες (g)"), ("protein", "Πρωτεΐνες (g)"),
                               ("fruit", "Φρούτα/λαχανικά (%)")):
                field(key, label, numeric=True)
            nv = ["1 – ανεπεξέργαστο", "2 – υλικό μαγειρικής", "3 – επεξεργασμένο", "4 – υπερεπεξεργασμένο"]
            c.add_widget(UW.text("Επεξεργασία", size=12, color=UW.C["muted"]))
            nova = Spinner(text=nv[2], values=nv, size_hint_y=None, height=dp(44))
            c.add_widget(nova)
            field("adds", "Πρόσθετα (E-κωδικοί)", hint="π.χ. E330, E250")
        elif kind in ("beauty", "petfood", "medicine"):
            c.add_widget(UW.text("Συστατικά (από τη συσκευασία)", size=12, color=UW.C["muted"]))
            ingr = TextInput(multiline=True, size_hint_y=None, height=dp(100))
            c.add_widget(ingr)
            f["ingr"] = ingr
        msg = UW.text("", color=UW.BAD)
        c.add_widget(msg)

        def num(k):
            try:
                return float(f[k].text.replace(",", ".") or 0)
            except ValueError:
                return 0.0

        def save():
            if not f["name"].text.strip():
                msg.text = "Γράψε τουλάχιστον το όνομα."
                return
            if kind == "food":
                if not f["kcal"].text.strip():
                    msg.text = "Γράψε τουλάχιστον την ενέργεια (kcal)."
                    return
                p = F.save_local_product(code, f["name"].text.strip(), f["brand"].text.strip(), f["qty"].text.strip(),
                                         cat.text, bev.active, num("kcal"), num("sugars"), num("sat"), num("salt"),
                                         num("fiber"), num("protein"), num("fruit"), int(nova.text[0]),
                                         f["adds"].text)
            else:
                p = P.save_local_generic(code, f["name"].text.strip(), f["brand"].text.strip(), kind,
                                         f["qty"].text.strip(), f["ingr"].text.strip() if "ingr" in f else "")
            self.stack = []
            self.open_product(p)
        self.btn(box, "ΑΠΟΘΗΚΕΥΣΗ", save, color=UW.GOOD)
        site = {"food": "openfoodfacts", "beauty": "openbeautyfacts", "petfood": "openpetfoodfacts",
                "general": "openproductsfacts"}.get(kind)
        if site:
            self.ghost(box, "Πρόσθεσέ το και στη δημόσια βάση (για όλους)",
                       lambda: webbrowser.open(f"https://world.{site}.org/cgi/product.pl?type=add&code={code}"))
        self.show("add")

    # ================================================================== οδηγός
    def show_guide(self, i):
        box = self.page("guide")
        title, body = UX.GUIDE[i]
        c = self.card(box, pad=20)
        c.add_widget(UW.text(f"[b]{esc(title)}[/b]", size=24, color=UW.PRIMARY))
        c.add_widget(UW.text(esc(body), size=17))
        c.add_widget(UW.text(f"{i + 1} / {len(UX.GUIDE)}", size=13, color=UW.C["muted"]))

        def finish():
            UX.save_ui(guide_seen=True)
            self.tab("home")
        row = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(10))
        sk = Button(text="Παράλειψη", background_normal="", background_color=UW.C["line"], color=UW.C["ink"])
        sk.bind(on_release=lambda *a: finish())
        nx = Button(text="Επόμενο" if i < len(UX.GUIDE) - 1 else "Ξεκινάμε!", bold=True, background_normal="",
                    background_color=UW.PRIMARY)
        nx.bind(on_release=lambda *a: self.show_guide(i + 1) if i < len(UX.GUIDE) - 1 else finish())
        row.add_widget(sk)
        row.add_widget(nx)
        box.add_widget(row)
        self.show("guide", push=False)


if __name__ == "__main__":
    PoiotitaApp().run()
