import os
import json
import threading
import urllib.parse
import urllib.request
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.spinner import MDSpinner
from kivy.metrics import dp
from kivy.clock import mainthread

# Android specific imports
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


class DynamicPdfApp(MDApp):
    json_url = "https://raw.githubusercontent.com/SultanAhmmed/Folio/main/books.json"

    def build(self):
        self.theme_cls.primary_palette = "Indigo"
        self.theme_cls.theme_style = "Light"

        if ANDROID:
            StrictMode.setVmPolicy(StrictMode.VmPolicy.LAX)

        root = MDBoxLayout(
            orientation="vertical",
            md_bg_color=(0.97, 0.97, 0.99, 1)
        )

        toolbar = MDTopAppBar(
            title="Folio",
            mode="center",
            md_bg_color=self.theme_cls.primary_color,
            specific_text_color=(1, 1, 1, 1),
            elevation=4,
            left_action_items=[["menu", lambda x: None]]
        )
        root.add_widget(toolbar)

        self.scroll_view = MDScrollView(bar_width=0)
        self.books_list = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(20), dp(16)],
            spacing=dp(16)
        )
        self.books_list.bind(minimum_height=self.books_list.setter("height"))
        self.scroll_view.add_widget(self.books_list)
        root.add_widget(self.scroll_view)

        loading_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(20),
            size_hint_y=None,
            height=dp(250)
        )
        loading_box.add_widget(
            MDSpinner(
                size_hint=(None, None),
                size=(dp(56), dp(56)),
                pos_hint={"center_x": 0.5}
            )
        )
        loading_box.add_widget(
            MDLabel(
                text="Loading your library...",
                halign="center",
                theme_text_color="Secondary",
                font_style="Subtitle1"
            )
        )
        self.books_list.add_widget(loading_box)

        threading.Thread(target=self.fetch_books).start()

        return root

    def fetch_books(self):
        try:
            req = urllib.request.Request(self.json_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
            self.populate_books(data)
        except Exception as e:
            print(f"Error fetching books: {e}")
            self.show_error()

    @mainthread
    def populate_books(self, books_data):
        self.books_list.clear_widgets()
        if not books_data:
            self.books_list.add_widget(
                MDLabel(
                    text="No books found.",
                    halign="center",
                    theme_text_color="Secondary",
                    font_style="Subtitle1"
                )
            )
            return

        for book in books_data:
            self.add_book_card(book)

    def add_book_card(self, book):
        title = book.get("title", "Unknown Title")
        desc = book.get("desc", "No description")
        url = book.get("url", "")
        filename = url.split("/")[-1].replace(" ", "_")

        card = MDCard(
            orientation="vertical",
            padding=0,
            size_hint_y=None,
            height=dp(200),
            elevation=3,
            radius=[dp(20)],
            md_bg_color=(1, 1, 1, 1)
        )

        top_layout = MDBoxLayout(
            orientation="horizontal",
            padding=[dp(20), dp(16), dp(16), dp(8)],
            spacing=dp(16)
        )

        icon_container = MDBoxLayout(
            size_hint=(None, None),
            size=(dp(60), dp(80)),
            radius=[dp(12)],
            md_bg_color=(0.9, 0.85, 0.95, 1)
        )

        letter_label = MDLabel(
            text=title[0].upper() if title else "?",
            halign="center",
            valign="center",
            font_style="H4",
            theme_text_color="Custom",
            text_color=(0.3, 0.2, 0.5, 1)
        )
        icon_container.add_widget(letter_label)

        text_layout = MDBoxLayout(orientation="vertical", spacing=dp(4))

        title_label = MDLabel(
            text=title,
            font_style="H6",
            theme_text_color="Primary",
            max_lines=2,
            shorten=True,
            shorten_from="right"
        )

        desc_label = MDLabel(
            text=desc,
            theme_text_color="Secondary",
            font_style="Body2",
            max_lines=2,
            shorten=True,
            text_size=(dp(240), None)
        )

        text_layout.add_widget(title_label)
        text_layout.add_widget(desc_label)

        top_layout.add_widget(icon_container)
        top_layout.add_widget(text_layout)

        divider = MDBoxLayout(
            size_hint_y=None,
            height=dp(1),
            md_bg_color=(0.93, 0.93, 0.95, 1)
        )

        btn_layout = MDBoxLayout(
            padding=[dp(20), dp(8), dp(20), dp(12)],
            size_hint_y=None,
            height=dp(60)
        )

        file_path = os.path.join(self.user_data_dir, filename)
        is_downloaded = os.path.exists(file_path)

        btn_text = "READ OFFLINE" if is_downloaded else "DOWNLOAD"
        btn_icon = "book-open-variant" if is_downloaded else "cloud-download-outline"
        btn_color = (0.2, 0.8, 0.4, 1) if is_downloaded else self.theme_cls.primary_color

        btn = MDRaisedButton(
            text=btn_text,
            icon=btn_icon,
            md_bg_color=btn_color,
            text_color=(1, 1, 1, 1),
            size_hint_x=1,
            font_style="Button",
            rounded_button=True
        )
        btn.bind(on_press=lambda x, u=url, f=filename, b=btn: self.handle_download(u, f, b))

        btn_layout.add_widget(btn)

        card.add_widget(top_layout)
        card.add_widget(divider)
        card.add_widget(btn_layout)

        self.books_list.add_widget(card)

    def handle_download(self, url, filename, button):
        file_path = os.path.join(self.user_data_dir, filename)

        if os.path.exists(file_path):
            self.open_pdf(file_path)
        else:
            button.text = "DOWNLOADING..."
            button.icon = "loading"
            button.disabled = True
            threading.Thread(target=self.download_file, args=(url, file_path, button)).start()

    def download_file(self, url, file_path, button):
        try:
            safe_url = urllib.parse.quote(url, safe=":/")
            req = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                with open(file_path, "wb") as out_file:
                    out_file.write(response.read())

            self.update_button_after_download(button)
        except Exception as e:
            print(f"Download error: {e}")
            self.reset_button(button, "FAILED")

    @mainthread
    def update_button_after_download(self, button):
        button.text = "READ OFFLINE"
        button.icon = "book-open-variant"
        button.md_bg_color = (0.2, 0.8, 0.4, 1)
        button.disabled = False

    @mainthread
    def reset_button(self, button, text):
        button.text = text
        button.icon = "cloud-download-outline"
        button.md_bg_color = self.theme_cls.primary_color
        button.disabled = False

    def open_pdf(self, file_path):
        if ANDROID:
            file = File(file_path)
            uri = Uri.fromFile(file)
            intent = Intent()
            intent.setAction(Intent.ACTION_VIEW)
            intent.setDataAndType(uri, "application/pdf")
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            PythonActivity.mActivity.startActivity(intent)
        else:
            print(f"PC Test: Would open {file_path}")

    @mainthread
    def show_error(self):
        self.books_list.clear_widgets()
        error_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(24),
            size_hint_y=None,
            height=dp(280)
        )
        error_box.add_widget(
            MDIcon(
                icon="wifi-off",
                halign="center",
                font_size=dp(64),
                theme_text_color="Secondary"
            )
        )
        error_box.add_widget(
            MDLabel(
                text="Failed to load books.\nPlease check your internet connection.",
                halign="center",
                theme_text_color="Secondary",
                font_style="Subtitle1"
            )
        )
        retry_btn = MDRaisedButton(
            text="RETRY",
            icon="refresh",
            md_bg_color=self.theme_cls.primary_color,
            text_color=(1, 1, 1, 1),
            rounded_button=True,
            size_hint=(None, None),
            size=(dp(160), dp(48)),
            pos_hint={"center_x": 0.5},
            on_press=lambda x: threading.Thread(target=self.fetch_books).start()
        )
        error_box.add_widget(retry_btn)
        self.books_list.add_widget(error_box)


if __name__ == "__main__":
    DynamicPdfApp().run()