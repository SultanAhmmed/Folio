import certifi, os
os.environ['SSL_CERT_FILE'] = certifi.where()

import os
import json
import ssl
import threading
import urllib.parse
import urllib.request

# explicit SSL context using certifi's cert bundle — on some Android
# python-for-android builds, the SSL_CERT_FILE env var alone is not
# picked up by the bundled openssl, causing silent SSLCertVerificationError
# on every network call while the same code works fine on PC.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDIconButton, MDFlatButton
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.textfield import MDTextField
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.behaviors import RectangularElevationBehavior
from kivymd.uix.list import OneLineIconListItem, IconLeftWidget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.metrics import dp
from kivy.clock import mainthread
from kivy.animation import Animation
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window

Window.softinput_mode = "below_target"

try:
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    File = autoclass("java.io.File")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    StrictMode = autoclass("android.os.StrictMode")
    ANDROID = True
except ImportError:
    ANDROID = False

# ---------------------------------------------------------------------------
# Palette — modern slate + blue theme
# ---------------------------------------------------------------------------
COLOR_BG = (0.071, 0.078, 0.094, 1)
COLOR_SURFACE = (0.106, 0.114, 0.137, 1)
COLOR_SURFACE_2 = (0.145, 0.157, 0.184, 1)
COLOR_CARD = (0.965, 0.969, 0.976, 1)
COLOR_GOLD = (0.286, 0.635, 0.988, 1)
COLOR_GOLD_SOFT = (0.286, 0.635, 0.988, 0.16)
COLOR_GOLD_DIM = (0.463, 0.502, 0.573, 1)
COLOR_INK = (0.114, 0.129, 0.161, 1)
COLOR_INK_SOFT = (0.408, 0.443, 0.494, 1)
COLOR_DOWNLOADED = (0.129, 0.694, 0.463, 1)
COLOR_DANGER = (0.937, 0.325, 0.314, 1)
COLOR_TEXT_ON_DARK = (0.882, 0.898, 0.918, 1)
COLOR_WHITE = (1, 1, 1, 1)

SPINE_PALETTE = [
    (0.937, 0.325, 0.314, 1),
    (0.129, 0.694, 0.463, 1),
    (0.286, 0.635, 0.988, 1),
    (0.949, 0.678, 0.157, 1),
    (0.608, 0.349, 0.988, 1),
    (0.086, 0.702, 0.694, 1),
    (0.984, 0.514, 0.290, 1),
]

APP_NAME = "Folio"


# ---------------------------------------------------------------------------
# Small reusable widgets
# ---------------------------------------------------------------------------
class RoundBoxLayout(MDBoxLayout):
    """BoxLayout that paints a rounded background using md_bg_color + radius."""

    def __init__(self, radius=None, bg=(0, 0, 0, 0), **kwargs):
        super().__init__(**kwargs)
        self._radius = radius or [dp(0)]
        with self.canvas.before:
            self._color = Color(*bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self._radius)
        self.bind(pos=self._update, size=self._update)

    def _update(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_bg(self, rgba):
        self._color.rgba = rgba


class MenuIconItem(OneLineIconListItem):
    """Dropdown menu row with a left-aligned icon (used for the 3-dot card menu)."""

    def __init__(self, icon="dots-horizontal", **kwargs):
        super().__init__(**kwargs)
        self._icon_widget = IconLeftWidget(
            icon=icon, theme_text_color="Custom", text_color=COLOR_INK_SOFT,
        )
        self.add_widget(self._icon_widget)


class TabChip(RoundBoxLayout):
    """Pill-shaped selectable tab with icon + label, centered as one tight cluster."""

    def __init__(self, text, icon, on_press, **kwargs):
        super().__init__(
            orientation="horizontal",
            radius=[dp(22)],
            bg=COLOR_SURFACE_2,
            size_hint=(1, None),
            height=dp(44),
            padding=0,
            spacing=0,
            **kwargs,
        )
        self.active = False

        self.icon_widget = MDIcon(
            icon=icon, theme_text_color="Custom", text_color=COLOR_GOLD_DIM,
            font_size=dp(18), size_hint=(None, None), size=(dp(20), dp(20)),
            halign="center", valign="middle",
        )
        self.icon_widget.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self.label_widget = MDLabel(
            text=text, theme_text_color="Custom", text_color=COLOR_GOLD_DIM,
            font_style="Body2", bold=True, halign="left", valign="middle",
            shorten=True, shorten_from="right", max_lines=1,
            size_hint_x=None,
        )

        # icon + label form one tight, content-sized cluster …
        cluster = MDBoxLayout(
            orientation="horizontal", spacing=dp(6), adaptive_size=True,
        )
        cluster.add_widget(self.icon_widget)
        cluster.add_widget(self.label_widget)

        # … dropped into an AnchorLayout, which centers it in the pill and
        # re-centers automatically whenever the cluster's size changes
        # (no manual bind/setter timing to get wrong).
        centerer = AnchorLayout(anchor_x="center", anchor_y="center")
        centerer.add_widget(cluster)
        self.add_widget(centerer)

        self._cluster = cluster
        # keep label from overflowing the pill on narrow phones (320-360dp
        # wide Android devices) — shrink/ellipsize to fit instead of
        # bleeding text past the rounded edge.
        self.bind(width=self._sync_label_width)
        self._sync_label_width(self, self.width)

        self._on_press = on_press
        self.bind(on_touch_up=self._touch)

    def _sync_label_width(self, inst, width):
        avail = max(dp(4), width - self.icon_widget.width - dp(6) - dp(16))
        self.label_widget.text_size = (avail, None)
        self.label_widget.texture_update()
        self.label_widget.width = min(self.label_widget.texture_size[0], avail)

    def _touch(self, inst, touch):
        if self.collide_point(*touch.pos) and touch.grab_current is None:
            self._on_press()
            return True
        return False

    def set_active(self, active):
        self.active = active
        if active:
            self.set_bg(COLOR_GOLD)
            self.icon_widget.text_color = COLOR_INK
            self.label_widget.text_color = COLOR_INK
        else:
            self.set_bg(COLOR_SURFACE_2)
            self.icon_widget.text_color = COLOR_GOLD_DIM
            self.label_widget.text_color = COLOR_GOLD_DIM


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
class DynamicPdfApp(MDApp):
    json_url = "https://raw.githubusercontent.com/SultanAhmmed/Folio/main/books.json"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.all_books_data = []
        self.favorites = []
        self.current_tab = "All"
        self.search_text = ""
        self.favorites_file = None
        self.search_visible = False
        self.stats_label = None
        self.menu = None
        self.tab_chips = {}
        self.fab = None

    # -- helpers -----------------------------------------------------------
    def get_safe_filename(self, url):
        return urllib.parse.unquote(url.split("/")[-1]).replace(" ", "_")

    def ensure_dir_exists(self, path):
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

    def spine_color(self, title):
        return SPINE_PALETTE[hash(title) % len(SPINE_PALETTE)]

    def toast(self, text, error=False):
        Snackbar(
            text=text,
            snackbar_x=dp(16),
            snackbar_y=dp(16),
            size_hint_x=None,
            width=min(Window.width - dp(32), dp(420)),
            bg_color=COLOR_DANGER if error else COLOR_SURFACE_2,
            md_bg_color=COLOR_DANGER if error else COLOR_SURFACE_2,
        ).open()

    # -- responsive helpers ---------------------------------------------------
    def _responsive_side_pad(self):
        # phones: snug 16dp margins. tablets/large screens: cap content at
        # ~680dp and center it instead of stretching cards edge-to-edge.
        w = Window.width
        max_content = dp(680)
        if w > max_content:
            return (w - max_content) / 2
        return dp(16)

    def _apply_responsive_layout(self, *args):
        side = self._responsive_side_pad()
        self.tab_box.padding = [side, dp(6), side, dp(12)]
        self._search_outer.padding = [side, 0, side, dp(8)]
        self.books_list.padding = [side, dp(8), side, dp(90)]

    # -- build ---------------------------------------------------------------
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Dark"
        Window.clearcolor = COLOR_BG

        if ANDROID:
            try:
                StrictMode.setVmPolicy(StrictMode.VmPolicy.LAX)
            except Exception:
                pass

        self.favorites_file = os.path.join(self.user_data_dir, "favorites.json")
        self.ensure_dir_exists(self.favorites_file)
        self.load_favorites()

        root = MDBoxLayout(orientation="vertical", md_bg_color=COLOR_BG)

        # -- Toolbar --
        self.toolbar = MDTopAppBar(
            title=f"  {APP_NAME}",
            mode="center",
            md_bg_color=COLOR_SURFACE,
            specific_text_color=COLOR_GOLD,
            elevation=8,
        )
        self.toolbar.right_action_items = [["magnify", lambda x: self.toggle_search()]]
        root.add_widget(self.toolbar)

        # -- Stats strip --
        self.stats_label = MDLabel(
            text="",
            halign="center",
            theme_text_color="Custom",
            text_color=COLOR_GOLD_DIM,
            font_style="Caption",
            size_hint_y=None,
            height=dp(24),
        )
        stats_wrap = MDBoxLayout(
            size_hint_y=None, height=dp(24), md_bg_color=COLOR_SURFACE,
        )
        stats_wrap.add_widget(self.stats_label)
        root.add_widget(stats_wrap)

        # -- Tabs (pill chips) --
        tab_box = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
            padding=[dp(16), dp(6), dp(16), dp(12)],
            spacing=dp(10),
            md_bg_color=COLOR_SURFACE,
        )
        self.tab_box = tab_box
        self.tab_chips["All"] = TabChip("All", "bookshelf", lambda: self.switch_tab("All"))
        self.tab_chips["Downloaded"] = TabChip("Downloaded", "book-arrow-down-outline", lambda: self.switch_tab("Downloaded"))
        self.tab_chips["Favorites"] = TabChip("Favorites", "heart", lambda: self.switch_tab("Favorites"))
        for chip in self.tab_chips.values():
            tab_box.add_widget(chip)
        root.add_widget(tab_box)

        # -- Search bar (collapsible) --
        self.search_box = RoundBoxLayout(
            radius=[dp(14)], bg=COLOR_SURFACE_2,
            size_hint_y=None, height=0, opacity=0,
            padding=[dp(12), dp(4), dp(12), dp(4)],
        )
        search_outer = MDBoxLayout(
            size_hint_y=None, height=0, padding=[dp(16), 0, dp(16), dp(8)],
            md_bg_color=COLOR_SURFACE,
        )
        self._search_outer = search_outer
        self.search_field = MDTextField(
            hint_text="Search title or description…",
            icon_left="magnify",
            icon_right="close",
            on_right_icon_press=lambda x: self.clear_search(),
            multiline=False,
            line_color_normal=COLOR_GOLD_DIM,
            line_color_focus=COLOR_GOLD,
            hint_text_color_normal=COLOR_GOLD_DIM,
        )
        self.search_field.bind(text=self.on_search_text)
        self.search_box.add_widget(self.search_field)
        search_outer.add_widget(self.search_box)
        root.add_widget(search_outer)

        # -- Book list --
        self.scroll_view = MDScrollView(bar_width=dp(3), bar_color=COLOR_GOLD_DIM, size_hint_y=1)
        self.scroll_view.bind(scroll_y=self._on_scroll)
        self.books_list = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(16), dp(8), dp(16), dp(90)],
            spacing=dp(16),
        )
        self.books_list.bind(minimum_height=self.books_list.setter("height"))
        self.scroll_view.add_widget(self.books_list)

        # -- Floating action button (scroll to top) sits over scroll view --
        body = MDBoxLayout()
        body.add_widget(self.scroll_view)
        root.add_widget(body)

        self.fab = MDIconButton(
            icon="arrow-up-bold",
            theme_text_color="Custom",
            text_color=COLOR_INK,
            md_bg_color=COLOR_GOLD,
            icon_size=dp(24),
            pos_hint={"right": 0.96, "y": 0.04},
            size_hint=(None, None),
            size=(dp(48), dp(48)),
            opacity=0,
            disabled=True,
        )
        self.fab.bind(on_release=lambda x: self._scroll_top())
        root.add_widget_index = None
        self.root = root
        from kivy.uix.floatlayout import FloatLayout
        wrapper = FloatLayout()
        wrapper.add_widget(root)
        self.fab.pos_hint = {"right": 0.97, "y": 0.06}
        wrapper.add_widget(self.fab)

        self.switch_tab("All")
        threading.Thread(target=self.fetch_books, daemon=True).start()

        # Android hardware back button: close search / dismiss menu first,
        # only exit the app if neither is open.
        Window.bind(on_keyboard=self._on_back_button)
        # Rotation / split-screen / foldable resize → recompute side padding.
        Window.bind(size=self._apply_responsive_layout)
        self._apply_responsive_layout()

        return wrapper

    def _on_back_button(self, window, key, *args):
        if key != 27:
            return False
        if self.menu:
            self.menu.dismiss()
            self.menu = None
            return True
        if self.search_visible:
            self.clear_search()
            return True
        return False  # let Android handle normal exit

    def _scroll_top(self):
        Animation(scroll_y=1, d=0.35, t="out_cubic").start(self.scroll_view)

    def _on_scroll(self, inst, value):
        show = value < 0.92 and len(self.books_list.children) > 2
        target_opacity = 1 if show else 0
        if abs(self.fab.opacity - target_opacity) > 0.01:
            self.fab.disabled = not show
            Animation(opacity=target_opacity, d=0.2).start(self.fab)

    # -- tabs ----------------------------------------------------------------
    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        for name, chip in self.tab_chips.items():
            chip.set_active(name == tab_name)
        self.scroll_view.scroll_y = 1
        self.filter_and_display()

    # -- favorites -------------------------------------------------------------
    def load_favorites(self):
        try:
            if os.path.exists(self.favorites_file):
                with open(self.favorites_file, "r") as f:
                    self.favorites = json.load(f)
            else:
                self.favorites = []
        except Exception:
            self.favorites = []

    def save_favorites(self):
        try:
            self.ensure_dir_exists(self.favorites_file)
            with open(self.favorites_file, "w") as f:
                json.dump(self.favorites, f)
        except Exception as e:
            print(f"[ERROR] Saving favorites failed: {e}")

    def toggle_favorite(self, title):
        if title in self.favorites:
            self.favorites.remove(title)
            self.toast(f"Removed \"{title}\" from favorites")
        else:
            self.favorites.append(title)
            self.toast(f"Added \"{title}\" to favorites")
        self.save_favorites()
        self.filter_and_display()

    def is_favorite(self, title):
        return title in self.favorites

    # -- search ----------------------------------------------------------------
    def toggle_search(self):
        self.search_visible = not self.search_visible
        if self.search_visible:
            self._search_outer.height = dp(60)
            self.search_box.height = dp(48)
            self.search_box.opacity = 1
            self.search_field.focus = True
        else:
            self._search_outer.height = 0
            self.search_box.height = 0
            self.search_box.opacity = 0
            self.search_field.text = ""
            self.search_text = ""
            self.filter_and_display()

    def clear_search(self):
        self.search_field.text = ""
        self.toggle_search()

    def on_search_text(self, instance, text):
        self.search_text = text.lower()
        self.filter_and_display()

    # -- data ----------------------------------------------------------------
    def fetch_books(self):
        try:
            req = urllib.request.Request(self.json_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as response:
                data = json.loads(response.read().decode())
            self.populate_books(data)
        except Exception as e:
            print(f"[ERROR] Fetch books failed: {e}")
            self.show_error(str(e))

    @mainthread
    def populate_books(self, books_data):
        self.all_books_data = books_data
        self.filter_and_display()

    def _is_downloaded(self, url):
        return os.path.exists(os.path.join(self.user_data_dir, self.get_safe_filename(url)))

    @mainthread
    def filter_and_display(self):
        self.books_list.clear_widgets()

        if not self.all_books_data:
            self.show_loading()
            return

        filtered = []
        for book in self.all_books_data:
            title = book.get("title", "")
            desc = book.get("desc", "")
            url = book.get("url", "")

            is_downloaded = self._is_downloaded(url)
            is_fav = self.is_favorite(title)

            if self.current_tab == "Downloaded" and not is_downloaded:
                continue
            if self.current_tab == "Favorites" and not is_fav:
                continue
            if self.search_text and self.search_text not in title.lower() and self.search_text not in desc.lower():
                continue

            filtered.append(book)

        total = len(self.all_books_data)
        downloaded_count = sum(1 for b in self.all_books_data if self._is_downloaded(b.get("url", "")))
        fav_count = len(self.favorites)
        self.stats_label.text = f"{total} books  ·  {downloaded_count} offline  ·  {fav_count} favorites"

        if not filtered:
            self._show_empty_state()
            return

        for book in filtered:
            self.add_book_card(book)

    def _show_empty_state(self):
        empty_msg, empty_icon = "No books found.\nTry a different search.", "book-search-outline"
        if self.current_tab == "Downloaded":
            empty_msg = "No downloaded books yet.\nTap DOWNLOAD on a book to save it offline."
            empty_icon = "book-arrow-down-outline"
        elif self.current_tab == "Favorites":
            empty_msg = "No favorites yet.\nTap the star icon on a book to add it here."
            empty_icon = "heart-outline"

        empty_box = MDBoxLayout(
            orientation="vertical", spacing=dp(18), size_hint_y=None,
            height=dp(240), padding=[dp(24), dp(48), dp(24), dp(0)],
        )
        empty_box.add_widget(
            MDIcon(icon=empty_icon, halign="center", font_size=dp(60),
                   theme_text_color="Custom", text_color=COLOR_GOLD_DIM)
        )
        empty_box.add_widget(
            MDLabel(text=empty_msg, halign="center", theme_text_color="Custom",
                    text_color=COLOR_TEXT_ON_DARK, font_style="Body1",
                    size_hint_y=None, height=dp(70))
        )
        self.books_list.add_widget(empty_box)

    # -- cards -----------------------------------------------------------------
    def add_book_card(self, book):
        title = book.get("title", "Unknown Title")
        desc = book.get("desc", "No description")
        url = book.get("url", "")
        filename = self.get_safe_filename(url)
        is_downloaded = self._is_downloaded(url)
        is_fav = self.is_favorite(title)
        spine = self.spine_color(title)

        outer = MDBoxLayout(orientation="horizontal", size_hint_y=None, height=dp(198))

        # spine strip with icon, rounded on outer-left corners
        spine_strip = RoundBoxLayout(
            radius=[dp(14), 0, 0, dp(14)], bg=spine,
            size_hint_x=None, width=dp(14),
        )
        outer.add_widget(spine_strip)

        card = MDCard(
            orientation="vertical", padding=0, size_hint_y=1,
            elevation=3, radius=[0, dp(14), dp(14), 0], md_bg_color=COLOR_CARD,
        )

        title_row = MDBoxLayout(
            orientation="horizontal", spacing=dp(2),
            padding=[dp(16), dp(12), dp(4), dp(0)],
            size_hint_y=None, height=dp(44),
        )
        title_label = MDLabel(
            text=title, font_style="H6", bold=True,
            theme_text_color="Custom", text_color=COLOR_INK,
            max_lines=1, shorten=True, shorten_from="right", halign="left",
        )
        star_btn = MDIconButton(
            icon="star" if is_fav else "star-outline",
            theme_text_color="Custom",
            text_color=COLOR_GOLD if is_fav else COLOR_INK_SOFT,
            icon_size=dp(24),
        )
        star_btn.bind(on_release=lambda x, t=title, b=star_btn: self._on_star(t, b))
        menu_btn = MDIconButton(
            icon="dots-vertical", theme_text_color="Custom",
            text_color=COLOR_INK_SOFT, icon_size=dp(20),
        )
        menu_btn.bind(on_release=lambda x, b=book, btn=menu_btn: self.show_card_menu(b, btn))
        title_row.add_widget(title_label)
        title_row.add_widget(star_btn)
        title_row.add_widget(menu_btn)

        desc_label = MDLabel(
            text=desc, theme_text_color="Custom", text_color=COLOR_INK_SOFT,
            font_style="Body2", max_lines=3, shorten=True, shorten_from="right",
            padding=[dp(16), 0], size_hint_y=None, height=dp(56),
        )

        meta_row = MDBoxLayout(
            padding=[dp(16), 0], size_hint_y=None, height=dp(20), spacing=dp(6),
        )
        meta_row.add_widget(
            MDIcon(icon="file-pdf-box", font_size=dp(14), theme_text_color="Custom",
                   text_color=COLOR_INK_SOFT, size_hint_x=None, width=dp(18))
        )
        meta_row.add_widget(
            MDLabel(text="PDF Document" + ("  ·  saved offline" if is_downloaded else ""),
                    font_style="Caption", theme_text_color="Custom",
                    text_color=COLOR_DOWNLOADED if is_downloaded else COLOR_INK_SOFT,
                    halign="left")
        )

        divider = MDBoxLayout(
            size_hint_y=None, height=dp(1), md_bg_color=(0.78, 0.71, 0.58, 1),
        )
        divider_wrap = MDBoxLayout(padding=[dp(16), dp(8), dp(16), 0], size_hint_y=None, height=dp(9))
        divider_wrap.add_widget(divider)

        # progress bar, hidden until download starts
        progress = MDProgressBar(value=0, max=100, size_hint_y=None, height=dp(4))
        progress.opacity = 0
        progress_wrap = MDBoxLayout(padding=[dp(16), 0], size_hint_y=None, height=dp(4))
        progress_wrap.add_widget(progress)

        btn_layout = MDBoxLayout(padding=[dp(16), dp(8), dp(16), dp(12)], size_hint_y=None, height=dp(50), spacing=dp(8))
        action_btn = MDRaisedButton(
            text="READ OFFLINE" if is_downloaded else "DOWNLOAD",
            icon="book-open-variant" if is_downloaded else "cloud-download-outline",
            theme_text_color="Custom",
            md_bg_color=COLOR_DOWNLOADED if is_downloaded else COLOR_GOLD,
            text_color=COLOR_WHITE,
            size_hint_x=1, font_style="Button", rounded_button=True,
        )
        action_btn.bind(
            on_release=lambda x, u=url, f=filename, b=action_btn, p=progress: self.handle_download(u, f, b, p)
        )
        btn_layout.add_widget(action_btn)

        card.add_widget(title_row)
        card.add_widget(desc_label)
        card.add_widget(meta_row)
        card.add_widget(divider_wrap)
        card.add_widget(progress_wrap)
        card.add_widget(btn_layout)

        outer.add_widget(card)
        self.books_list.add_widget(outer)

    def _on_star(self, title, btn):
        self.toggle_favorite(title)

    def show_card_menu(self, book, caller):
        url = book.get("url", "")
        filename = self.get_safe_filename(url)
        is_downloaded = self._is_downloaded(url)

        menu_items = []
        if is_downloaded:
            menu_items.append({
                "viewclass": "MenuIconItem",
                "text": "Delete Download",
                "icon": "trash-can-outline",
                "height": dp(48),
                "on_release": lambda *args: self._delete_and_close(filename),
            })
        menu_items.append({
            "viewclass": "MenuIconItem",
            "text": "Share Link",
            "icon": "share-variant-outline",
            "height": dp(48),
            "on_release": lambda *args: self._share_and_close(url),
        })

        self.menu = MDDropdownMenu(caller=caller, items=menu_items, width_mult=4)
        self.menu.open()

    def _delete_and_close(self, filename):
        if self.menu:
            self.menu.dismiss()
        self.delete_book(filename)

    def _share_and_close(self, url):
        if self.menu:
            self.menu.dismiss()
        self.share_book(url)

    def delete_book(self, filename):
        try:
            file_path = os.path.join(self.user_data_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                self.toast("Download deleted")
                self.filter_and_display()
        except Exception as e:
            print(f"[ERROR] Delete failed: {e}")
            self.toast("Could not delete file", error=True)

    def share_book(self, url):
        if ANDROID:
            try:
                intent = Intent()
                intent.setAction(Intent.ACTION_SEND)
                intent.putExtra(Intent.EXTRA_TEXT, url)
                intent.setType("text/plain")
                PythonActivity.mActivity.startActivity(Intent.createChooser(intent, "Share via"))
            except Exception as e:
                print(f"[ERROR] Share failed: {e}")
        else:
            self.toast("Sharing only available on Android")

    # -- downloads ---------------------------------------------------------------
    def handle_download(self, url, filename, button, progress_bar):
        file_path = os.path.join(self.user_data_dir, filename)
        if os.path.exists(file_path):
            self.open_pdf(file_path)
        else:
            button.text = "DOWNLOADING…"
            button.icon = "loading"
            button.disabled = True
            progress_bar.opacity = 1
            progress_bar.value = 0
            threading.Thread(
                target=self.download_file, args=(url, file_path, button, progress_bar), daemon=True
            ).start()

    def download_file(self, url, file_path, button, progress_bar):
        tmp_path = file_path + ".part"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
                total = response.getheader("Content-Length")
                total = int(total) if total else 0
                written = 0
                chunk_size = 65536
                with open(tmp_path, "wb") as out_file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        written += len(chunk)
                        if total:
                            self.update_progress(progress_bar, min(100, written * 100 / total))
            os.replace(tmp_path, file_path)
            self.update_button_after_download(button, progress_bar)
            self.filter_and_display()
        except Exception as e:
            print(f"[ERROR] Download failed: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            self.reset_button(button, progress_bar)

    @mainthread
    def update_progress(self, progress_bar, value):
        progress_bar.value = value

    @mainthread
    def update_button_after_download(self, button, progress_bar):
        button.text = "READ OFFLINE"
        button.icon = "book-open-variant"
        button.md_bg_color = COLOR_DOWNLOADED
        button.disabled = False
        progress_bar.opacity = 0
        self.toast("Download complete")

    @mainthread
    def reset_button(self, button, progress_bar):
        button.text = "RETRY DOWNLOAD"
        button.icon = "cloud-download-outline"
        button.md_bg_color = COLOR_GOLD
        button.disabled = False
        progress_bar.opacity = 0
        self.toast("Download failed — check connection", error=True)

    def open_pdf(self, file_path):
        if ANDROID:
            try:
                from jnius import autoclass
                File = autoclass('java.io.File')
                
                # Try AndroidX FileProvider first, fallback to older Support library
                try:
                    FileProvider = autoclass('androidx.core.content.FileProvider')
                except Exception:
                    FileProvider = autoclass('android.support.v4.content.FileProvider')
                    
                context = PythonActivity.mActivity.getApplicationContext()
                # The authority matches the default FileProvider in python-for-android's manifest
                authority = context.getPackageName() + ".fileprovider"
                
                java_file = File(file_path)
                # Generate a secure content:// URI for the private file
                uri = FileProvider.getUriForFile(context, authority, java_file)
                
                intent = Intent(Intent.ACTION_VIEW)
                intent.setDataAndType(uri, "application/pdf")
                # Grant the PDF viewer temporary permission to read this specific file
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                
                PythonActivity.mActivity.startActivity(intent)
                
            except Exception as e:
                print(f"[ERROR] Open PDF failed: {e}")
                import traceback
                traceback.print_exc()
                self.toast("Could not open PDF. Ensure AndroidX is enabled in buildozer.spec.", error=True)
        else:
            print(f"PC Test: Would open {file_path}")
            self.toast(f"Would open: {os.path.basename(file_path)}")
            
    # -- states ---------------------------------------------------------------
    @mainthread
    def show_loading(self):
        self.books_list.clear_widgets()
        loading_box = MDBoxLayout(orientation="vertical", spacing=dp(20), size_hint_y=None, height=dp(260))
        loading_box.add_widget(
            MDSpinner(size_hint=(None, None), size=(dp(56), dp(56)), pos_hint={"center_x": 0.5},
                      color=COLOR_GOLD)
        )
        loading_box.add_widget(
            MDLabel(text="Opening your library…", halign="center",
                    theme_text_color="Custom", text_color=COLOR_TEXT_ON_DARK, font_style="Subtitle1")
        )
        self.books_list.add_widget(loading_box)

    @mainthread
    def show_error(self, detail=""):
        self.books_list.clear_widgets()
        error_box = MDBoxLayout(orientation="vertical", spacing=dp(24), size_hint_y=None, height=dp(320))
        error_box.add_widget(
            MDIcon(icon="wifi-off", halign="center", font_size=dp(64), theme_text_color="Custom", text_color=COLOR_GOLD_DIM)
        )
        error_box.add_widget(
            MDLabel(text="Failed to load books.\nPlease check your internet.", halign="center",
                    theme_text_color="Custom", text_color=COLOR_TEXT_ON_DARK, font_style="Subtitle1")
        )
        if detail:
            error_box.add_widget(
                MDLabel(text=detail, halign="center", theme_text_color="Custom",
                        text_color=COLOR_GOLD_DIM, font_style="Caption")
            )
        retry_btn = MDRaisedButton(
            text="RETRY", icon="refresh", theme_text_color="Custom",
            md_bg_color=COLOR_GOLD, text_color=COLOR_WHITE, rounded_button=True,
            size_hint=(None, None), size=(dp(160), dp(48)), pos_hint={"center_x": 0.5},
        )
        retry_btn.bind(on_release=lambda x: threading.Thread(target=self.fetch_books, daemon=True).start())
        error_box.add_widget(retry_btn)
        self.books_list.add_widget(error_box)


if __name__ == "__main__":
    DynamicPdfApp().run()