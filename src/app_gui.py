import tkinter as tk
import threading
from tkinter import ttk
from tkinter import font as tkFont
from tkinter import scrolledtext, messagebox
import webbrowser
from fetch_movies import MovieManager
from ai_api import get_dialogue, get_image
from PIL import Image, ImageTk
import io
import requests


DARK_BG = "#2e2e2e"
DARK_FG = "#cccccc"
DARK_LISTBOX_BG = "#3c3c3c"
DARK_TEXT_BG = "#3c3c3c"
DARK_BUTTON_BG = "#555555"
DARK_BUTTON_FG = "#ffffff"
ACCENT_COLOR = "#4a90e2"


class IMDbApp:

    def __init__(self, root):

        self.root = root
        self.root.title("Enhanced IMDb Movie Explorer")
        self.root.geometry("1000x700")
        self.root.configure(bg=DARK_BG)

        self.movie_manager = MovieManager()

        self.selected_rank = None
        self.selected_title = None

        self.last_generated_dialogue = {}
        self.top_movies = []
        self.poster_images = {}

        self.default_font = tkFont.nametofont("TkDefaultFont")
        self.default_font.configure(size=10)
        self.header_font = tkFont.Font(family="Segoe UI", size=12, weight="bold")
        self.title_font = tkFont.Font(family="Segoe UI", size=11, weight="bold")

        self.setup_styles()
        self.create_ui_layout()

    def setup_styles(self):
        """Configures ttk styles for a dark theme."""
        style = ttk.Style(self.root)
        style.theme_use('clam')

        style.configure('.', background=DARK_BG, foreground=DARK_FG, font=self.default_font)
        style.configure('TFrame', background=DARK_BG)
        style.configure('Dark.TFrame', background=DARK_BG)
        style.configure('TLabel', background=DARK_BG, foreground=DARK_FG, padding=(5, 2))
        style.configure('Header.TLabel', font=self.header_font, foreground=ACCENT_COLOR)
        style.configure('Title.TLabel', font=self.title_font)

        style.configure('TButton', background=DARK_BUTTON_BG, foreground=DARK_BUTTON_FG, padding=5)
        style.map('TButton',
                  background=[('active', ACCENT_COLOR), ('pressed', ACCENT_COLOR)],
                  foreground=[('active', DARK_BUTTON_FG)])

        style.configure('TEntry', fieldbackground=DARK_LISTBOX_BG, foreground=DARK_FG, insertcolor=DARK_FG)
        style.configure('TSpinbox', fieldbackground=DARK_LISTBOX_BG, foreground=DARK_FG, arrowcolor=DARK_FG, insertcolor=DARK_FG)
        style.map('TSpinbox', background=[('active', DARK_LISTBOX_BG)])

        style.map('TCombobox', fieldbackground=[('readonly', DARK_LISTBOX_BG)],
                                selectbackground=[('readonly', DARK_LISTBOX_BG)],
                                selectforeground=[('readonly', DARK_FG)],
                                foreground=[('readonly', DARK_FG)])
        style.map('TCombobox.field', highlightcolor=[('readonly', 'hover', DARK_LISTBOX_BG)])


        style.configure('TNotebook', background=DARK_BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=DARK_BG, foreground=DARK_FG, padding=[10, 5], font=self.default_font)
        style.map('TNotebook.Tab',
                  background=[('selected', DARK_LISTBOX_BG), ('active', DARK_BUTTON_BG)],
                  foreground=[('selected', ACCENT_COLOR)])

        # Scrollbar style
        style.configure('Vertical.TScrollbar', background=DARK_BG, troughcolor=DARK_LISTBOX_BG, bordercolor=DARK_BG, arrowcolor=DARK_FG)
        style.map('Vertical.TScrollbar', background=[('active', DARK_BUTTON_BG)])

    def create_left_frame(self):
        """Creates the widgets for the left frame (movie list with posters)."""
        ttk.Label(self.left_frame, text="Top IMDb Movies", style="Header.TLabel").pack(pady=(0, 10))

        list_frame = ttk.Frame(self.left_frame, style="Dark.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.movies_canvas = tk.Canvas(
            list_frame,
            bg=DARK_BG,
            highlightthickness=0,
            bd=0
        )
        self.movies_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL,
            command=self.movies_canvas.yview,
            style='Vertical.TScrollbar'
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.movies_canvas.configure(yscrollcommand=scrollbar.set)

        self.movie_items_frame = ttk.Frame(self.movies_canvas, style="Dark.TFrame")

        self.movie_items_frame_id = self.movies_canvas.create_window(
            (0, 0), window=self.movie_items_frame, anchor="nw"
        )

        def on_frame_configure(event):
            self.movies_canvas.configure(scrollregion=self.movies_canvas.bbox("all"))

        self.movie_items_frame.bind("<Configure>", on_frame_configure)

        def on_canvas_configure(event):
            canvas_width = event.width
            self.movies_canvas.itemconfig(self.movie_items_frame_id, width=canvas_width)

        self.movies_canvas.bind("<Configure>", on_canvas_configure)


    def create_right_frame(self):
        """Creates the widgets for the right frame (details and AI)."""
        ai_controls_frame = ttk.Frame(self.right_frame, style="Dark.TFrame")
        ai_controls_frame.pack(fill=tk.X, pady=(0, 15))
        ai_controls_frame.columnconfigure((1, 3, 5), weight=1)

        ttk.Label(ai_controls_frame, text="Dialogue Gen:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(ai_controls_frame, text="Characters:").grid(row=0, column=1, padx=(10, 2), pady=5, sticky="e")
        self.char_count_var = tk.IntVar(value=3)
        self.char_count_spinbox = ttk.Spinbox(
            ai_controls_frame,
            from_=2,
            to=4,
            textvariable=self.char_count_var,
            width=5,
            wrap=True
        )
        self.char_count_spinbox.grid(row=0, column=2, padx=(0, 10), pady=5, sticky="w")

        ttk.Label(ai_controls_frame, text="Max Words:").grid(row=0, column=3, padx=(10, 2), pady=5, sticky="e")
        self.max_words_var = tk.IntVar(value=1000)
        self.max_words_spinbox = ttk.Spinbox(
            ai_controls_frame,
            from_=750,
            to=1500,
            increment=50,
            textvariable=self.max_words_var,
            width=7,
            wrap=True
        )
        self.max_words_spinbox.grid(row=0, column=4, padx=(0, 10), pady=5, sticky="w")

        self.generate_dialogue_button = ttk.Button(
            ai_controls_frame,
            text="Generate Dialogue",
            command=self.generate_dialogue,
            state=tk.DISABLED
        )
        self.generate_dialogue_button.grid(row=0, column=5, padx=5, pady=5, sticky="ew")

        ttk.Label(ai_controls_frame, text="Image Gen:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(ai_controls_frame, text="Location:").grid(row=1, column=1, padx=(10, 2), pady=5, sticky="e")
        self.location_var = tk.StringVar()
        self.location_entry = ttk.Entry(ai_controls_frame, textvariable=self.location_var, width=15)
        self.location_entry.grid(row=1, column=2, padx=(0, 10), pady=5, sticky="ew")

        ttk.Label(ai_controls_frame, text="Style:").grid(row=1, column=3, padx=(10, 2), pady=5, sticky="e")
        self.style_var = tk.StringVar()
        self.style_combobox = ttk.Combobox(
            ai_controls_frame,
            textvariable=self.style_var,
            values=["Marvel", "Futuristic", "Cartoon", "Realistic"],
            state="readonly",
            width=12
        )
        self.style_combobox.grid(row=1, column=4, padx=(0, 10), pady=5, sticky="ew")
        self.style_combobox.set("Futuristic")

        self.generate_image_button = ttk.Button(
            ai_controls_frame,
            text="Generate Image",
            command=self.generate_image,
            state=tk.DISABLED
        )
        self.generate_image_button.grid(row=1, column=5, padx=5, pady=5, sticky="ew")

        self.notebook = ttk.Notebook(self.right_frame, style='TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)

        details_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=10)
        self.notebook.add(details_tab, text=' Movie Details ')

        details_tab.columnconfigure(1, weight=1)

        ttk.Label(details_tab, text="Title:", style="Title.TLabel").grid(row=0, column=0, sticky="nw", padx=5, pady=2)
        self.title_label = ttk.Label(details_tab, text="", wraplength=600)
        self.title_label.grid(row=0, column=1, sticky="nw", padx=5, pady=2)

        ttk.Label(details_tab, text="IMDb URL:", style="Title.TLabel").grid(row=1, column=0, sticky="nw", padx=5, pady=2)
        self.url_label = ttk.Label(details_tab, text="", foreground=ACCENT_COLOR, cursor="hand2")
        self.url_label.grid(row=1, column=1, sticky="nw", padx=5, pady=2)

        ttk.Label(details_tab, text="Description:", style="Title.TLabel").grid(row=2, column=0, sticky="nw", padx=5, pady=(10, 2))
        self.description_text = scrolledtext.ScrolledText(
            details_tab, wrap=tk.WORD, height=5, bg=DARK_TEXT_BG, fg=DARK_FG,
            borderwidth=1, relief=tk.SUNKEN, padx=5, pady=5,
            font=self.default_font, state=tk.DISABLED
        )
        self.description_text.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Label(details_tab, text="Storyline:", style="Title.TLabel").grid(row=4, column=0, sticky="nw", padx=5, pady=(10, 2))
        self.storyline_text = scrolledtext.ScrolledText(
            details_tab, wrap=tk.WORD, height=8, bg=DARK_TEXT_BG, fg=DARK_FG,
            borderwidth=1, relief=tk.SUNKEN, padx=5, pady=5,
            font=self.default_font, state=tk.DISABLED
        )
        self.storyline_text.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=5, pady=2)
        details_tab.rowconfigure(5, weight=1)


        dialogue_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=10)
        save_frame = ttk.Frame(dialogue_tab, style="Dark.TFrame")
        save_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(save_frame, text="Filename:").pack(side=tk.LEFT, padx=(0, 5))

        self.dialogue_filename_var = tk.StringVar()
        self.dialogue_filename_entry = ttk.Entry(save_frame, textvariable=self.dialogue_filename_var, width=30)
        self.dialogue_filename_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.save_dialogue_button = ttk.Button(
            save_frame,
            text="Save Dialogue to File",
            command=self.save_dialogue_to_file
        )
        self.save_dialogue_button.pack(side=tk.LEFT)

        self.notebook.add(dialogue_tab, text=' Generated Dialogue ')

        self.dialogue_output_text = scrolledtext.ScrolledText(
            dialogue_tab, wrap=tk.WORD, bg=DARK_TEXT_BG, fg=DARK_FG,
            borderwidth=1, relief=tk.SUNKEN, padx=5, pady=5,
            font=self.default_font, state=tk.DISABLED
        )
        self.dialogue_output_text.pack(fill=tk.BOTH, expand=True)

        image_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=10)
        self.notebook.add(image_tab, text=' Generated Image ')

        self.image_label = ttk.Label(
            image_tab,
            text="Image will appear here",
            anchor=tk.CENTER,
            background=DARK_LISTBOX_BG
        )
        image_tab.rowconfigure(0, weight=1)
        image_tab.columnconfigure(0, weight=1)
        self.image_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def create_ui_layout(self):
        """Create the main UI layout with frames."""
        self.left_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=10)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        self.right_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=10)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.create_left_frame()
        self.create_right_frame()

    def populate_movie_list(self):
        """Fetches and displays the IMDb top 10 movies with posters."""
        for widget in self.movie_items_frame.winfo_children():
            widget.destroy()

        loading_label = ttk.Label(self.movie_items_frame, text="Loading IMDb top 10...", style="TLabel")
        loading_label.pack(pady=10, padx=5, fill=tk.X)
        self.movies_canvas.update()

        try:

            movies = self.movie_manager.fetch_top_movies(limit=10)
            self.movie_manager.fetch_all_details()

            loading_label.destroy()
            self.top_movies = []

            for rank, movie in sorted(movies.items()):
                title = movie['title']
                self.top_movies.append((rank, title))

                movie_frame = ttk.Frame(self.movie_items_frame, style="Dark.TFrame", padding=5)
                movie_frame.pack(fill=tk.X, pady=2)

                poster_url = self.movie_manager.movies[rank].get('poster_url')
                poster_label = ttk.Label(movie_frame, background=DARK_LISTBOX_BG)

                if poster_url:
                    try:
                        threading.Thread(
                            target=self.load_poster_image,
                            args=(poster_url, poster_label, rank),
                            daemon=True
                        ).start()
                    except Exception:
                        poster_label.config(text="No image")
                else:
                    poster_label.config(text="No image")

                poster_label.grid(row=0, column=0, padx=5, pady=2)

                title_label = ttk.Label(
                    movie_frame,
                    text=title,
                    wraplength=150,
                    anchor=tk.W,
                    background=DARK_LISTBOX_BG,
                    padding=(5, 10)
                )
                title_label.grid(row=0, column=1, sticky="nsew", padx=5, pady=2)
                movie_frame.columnconfigure(1, weight=1)

                def make_select_handler(idx):
                    return lambda e: self.select_movie(idx)

                movie_frame.bind("<Button-1>", make_select_handler(rank - 1))
                title_label.bind("<Button-1>", make_select_handler(rank - 1))
                poster_label.bind("<Button-1>", make_select_handler(rank - 1))

        except Exception as e:
            for widget in self.movie_items_frame.winfo_children():
                widget.destroy()

            error_label = ttk.Label(self.movie_items_frame, text=f"Error fetching movies: {str(e)}", style="TLabel")
            error_label.pack(pady=10, padx=5)
            messagebox.showerror("Fetch Error", f"Failed to fetch movies: {str(e)}")
            print(f"Error fetching top movies: {e}")

    def set_text_widget_content(self, text_widget, content):
        """Helper to safely update content in a disabled Text widget."""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)
        text_widget.insert('1.0', content)
        text_widget.config(state=tk.DISABLED)


    def clear_details(self):
        """Clears the details and AI output areas."""
        self.title_label.config(text="")
        self.url_label.config(text="")
        self.set_text_widget_content(self.description_text, "")
        self.set_text_widget_content(self.storyline_text, "")
        self.set_text_widget_content(self.dialogue_output_text, "")
        self.image_label.config(image="", text="Select a movie")

    def generate_dialogue(self):
        """Generate a dialogue based on the selected movie."""
        if not hasattr(self, 'selected_rank') or not self.selected_rank:
            self.set_text_widget_content(self.dialogue_output_text, "Error: Please select a movie first.")
            return

        movie_data = self.movie_manager.fetch_movie_details_by_rank(self.selected_rank)
        storyline = movie_data.get('storyline', '')
        num_chars = self.char_count_var.get()
        max_words = self.max_words_var.get()

        self.set_text_widget_content(self.dialogue_output_text, "Generating dialogue, please wait...")
        self.notebook.select(1)

        def worker():
            try:
                dialogue = get_dialogue(storyline, num_chars, max_words)
                self.last_generated_dialogue[self.selected_title] = dialogue
                self.root.after(0, lambda: self.set_text_widget_content(self.dialogue_output_text, dialogue))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Dialogue Error",
                                                                f"Failed to generate dialogue: {str(e)}"))

        threading.Thread(target=worker, daemon=True).start()

    def save_dialogue_to_file(self):
        """Save the current dialogue to a user-named text file."""
        filename = self.dialogue_filename_var.get().strip()
        if not filename:
            messagebox.showwarning("Filename Missing", "Please enter a filename.")
            return

        dialogue_text = self.dialogue_output_text.get("1.0", tk.END).strip()
        if not dialogue_text or dialogue_text.startswith("Generating dialogue"):
            messagebox.showwarning("No Dialogue", "No dialogue available to save.")
            return

        try:
            full_filename = f"{filename}.txt"
            with open(full_filename, "w", encoding="utf-8") as f:
                f.write(dialogue_text)
            messagebox.showinfo("Success", f"Dialogue saved as '{full_filename}'.")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save dialogue: {e}")

    def generate_image(self):
        """Generate an image based on the selected movie."""
        if not hasattr(self, 'selected_rank') or not self.selected_rank:
            self.image_label.config(text="Error: Please select a movie first.")
            return

        location = self.location_var.get().strip() or "Unknown location"
        style = self.style_var.get() or "Futuristic"

        self.image_label.config(image="", text="Generating image, please wait...")
        self.notebook.select(2)

        def worker():
            if self.selected_title in self.last_generated_dialogue:
                dialogue = self.last_generated_dialogue[self.selected_title]
            else:
                try:
                    movie_data = self.movie_manager.fetch_movie_details_by_rank(self.selected_rank)
                    storyline = movie_data.get('storyline', 'No storyline available.')
                    num_chars = self.char_count_var.get()
                    max_words = self.max_words_var.get()
                    dialogue = get_dialogue(storyline, num_chars, max_words)
                    self.last_generated_dialogue[self.selected_title] = dialogue
                    self.root.after(0, lambda: self.set_text_widget_content(self.dialogue_output_text, dialogue))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Dialogue Error",
                                                                    f"Failed to generate dialogue for image: {str(e)}"))
                    return

            try:
                image_url = get_image(location, style, dialogue)
                if not image_url:
                    self.root.after(0, lambda: self.image_label.config(text="Image generation failed."))
                    return

                try:
                    response = requests.get(image_url)
                    response.raise_for_status()
                    image_data = response.content

                    pil_image = Image.open(io.BytesIO(image_data))
                    pil_image = pil_image.resize((512, 512))
                    tk_image = ImageTk.PhotoImage(pil_image)

                    def update_gui_with_image():
                        self.image_label.config(image=tk_image, text="")
                        self.image_label.image = tk_image

                    self.root.after(0, update_gui_with_image)

                except Exception as e:
                    self.root.after(0, lambda: self.image_label.config(text=f"Failed to load image: {e}"))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Image Error", f"Failed to generate image: {str(e)}"))

        threading.Thread(target=worker, daemon=True).start()

    def load_poster_image(self, url, label, rank):
        """Load movie poster from URL and display in label."""
        try:
            response = requests.get(url)
            response.raise_for_status()

            img_data = response.content
            img = Image.open(io.BytesIO(img_data))

            img = img.resize((80, 120), Image.LANCZOS)

            tk_img = ImageTk.PhotoImage(img)

            self.poster_images[rank] = tk_img

            def update_label():
                label.config(image=tk_img)

            self.root.after(0, update_label)
        except Exception as e:
            def update_error():
                label.config(text="Image\nError")

            self.root.after(0, update_error)
            print(f"Error loading poster: {e}")

    def select_movie(self, index):
        """Handle selection of a movie from the list."""
        if index < 0 or index >= len(self.top_movies):
            return

        for i, child in enumerate(self.movie_items_frame.winfo_children()):
            for widget in child.winfo_children():
                if i == index:
                    if isinstance(widget, ttk.Label):
                        widget.configure(background=ACCENT_COLOR)
                else:
                    if isinstance(widget, ttk.Label):
                        widget.configure(background=DARK_LISTBOX_BG)

        rank, movie_title = self.top_movies[index]
        self.selected_rank = rank
        self.selected_title = movie_title

        self.set_text_widget_content(self.description_text, "Loading movie details...")
        self.set_text_widget_content(self.storyline_text, "Loading storyline...")
        self.root.update()

        try:
            movie_data = self.movie_manager.fetch_movie_details_by_rank(rank)
            self.title_label.config(text=f"{movie_data.get('title', 'Unknown')} ({movie_data.get('year', 'N/A')})")

            url = movie_data.get('url', '')
            self.url_label.config(text=url)
            if url:
                self.url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

            self.set_text_widget_content(self.description_text,
                                         movie_data.get('description', 'No description available.'))
            self.set_text_widget_content(self.storyline_text,
                                         movie_data.get('storyline', 'No storyline available.'))

            self.generate_dialogue_button.config(state=tk.NORMAL)
            self.generate_image_button.config(state=tk.NORMAL)

            self.selected_rank = rank
            self.selected_title = movie_title

            self.notebook.select(0)

        except Exception as e:
            self.clear_details()
            messagebox.showerror("Movie Details Error", f"Failed to load movie details: {str(e)}")
            print(f"Error loading movie details: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = IMDbApp(root)
    root.mainloop()
