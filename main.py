import os
import json
import threading
import urllib.request
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.scrollview import MDScrollView
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
    # REPLACE THIS with the Raw link to your books.json file on GitHub
    json_url = "https://raw.githubusercontent.com/SultanAhmmed/Folio/main/books.json"

    def build(self):
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.theme_style = "Light"

        # HACK: Allows opening files from private storage without Android Studio XML setup
        if ANDROID:
            StrictMode.setVmPolicy(StrictMode.VmPolicy.LAX)

        # Main Layout
        root = MDBoxLayout(orientation="vertical")

        # Modern Top Bar
        toolbar = MDTopAppBar(
            title="My Library",
            md_bg_color=self.theme_cls.primary_color,
            specific_text_color=self.theme_cls.primary_light,
        )
        root.add_widget(toolbar)

        # Scrollable List for Books
        self.scroll_view = MDScrollView()
        self.books_list = MDBoxLayout(
            orientation="vertical", size_hint_y=None, padding=dp(16), spacing=dp(16)
        )
        self.books_list.bind(minimum_height=self.books_list.setter("height"))
        self.scroll_view.add_widget(self.books_list)
        root.add_widget(self.scroll_view)

        # Loading state
        self.loading_label = MDLabel(
            text="Loading books...", halign="center", theme_text_color="Secondary"
        )
        self.books_list.add_widget(self.loading_label)

        # Fetch data in background thread so UI doesn't freeze
        threading.Thread(target=self.fetch_books).start()

        return root

    def fetch_books(self):
        try:
            # User-Agent is required so GitHub doesn't block the request
            req = urllib.request.Request(
                self.json_url, headers={"User-Agent": "Mozilla/5.0"}
            )
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
            self.books_list.add_widget(MDLabel(text="No books found.", halign="center"))
            return

        for book in books_data:
            self.add_book_card(book)

    def add_book_card(self, book):
        title = book.get("title", "Unknown Title")
        desc = book.get("desc", "No description")
        url = book.get("url", "")

        # Extract filename from URL (e.g., "gatsby.pdf")
        filename = url.split("/")[-1]

        # Modern Card Design
        card = MDCard(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(12),
            size_hint_y=None,
            height=dp(180),
            elevation=3,
            radius=[dp(12)] * 4,
        )

        card.add_widget(
            MDLabel(
                text=title, font_style="H6", theme_text_color="Primary", halign="left"
            )
        )

        # FIXED LINE: Removed wrap=True, added text_size for proper wrapping
        card.add_widget(
            MDLabel(
                text=desc,
                theme_text_color="Secondary",
                halign="left",
                text_size=(dp(250), None),
            )
        )

        # Check if already downloaded in private storage
        file_path = os.path.join(self.user_data_dir, filename)
        is_downloaded = os.path.exists(file_path)

        btn_text = "READ OFFLINE" if is_downloaded else "DOWNLOAD"
        btn_color = (
            self.theme_cls.primary_color
            if is_downloaded
            else self.theme_cls.accent_color
        )

        btn = MDRaisedButton(
            text=btn_text,
            md_bg_color=btn_color,
            pos_hint={"center_x": 0.5},
            size_hint_x=0.8,
        )
        btn.bind(
            on_press=lambda x, u=url, f=filename, b=btn: self.handle_download(u, f, b)
        )

        card.add_widget(btn)
        self.books_list.add_widget(card)

    def handle_download(self, url, filename, button):
        file_path = os.path.join(self.user_data_dir, filename)

        if os.path.exists(file_path):
            self.open_pdf(file_path)
        else:
            button.text = "DOWNLOADING..."
            button.disabled = True
            threading.Thread(
                target=self.download_file, args=(url, file_path, button)
            ).start()

    def download_file(self, url, file_path, button):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                with open(file_path, "wb") as out_file:
                    out_file.write(response.read())

            self.update_button_after_download(button)
        except Exception as e:
            print(f"Download error: {e}")
            self.reset_button(button, "DOWNLOAD FAILED")

    @mainthread
    def update_button_after_download(self, button):
        button.text = "READ OFFLINE"
        button.md_bg_color = self.theme_cls.primary_color
        button.disabled = False

    @mainthread
    def reset_button(self, button, text):
        button.text = text
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
        self.books_list.add_widget(
            MDLabel(
                text="Failed to load books. Check internet.",
                halign="center",
                theme_text_color="Error",
            )
        )


if __name__ == "__main__":
    DynamicPdfApp().run()
