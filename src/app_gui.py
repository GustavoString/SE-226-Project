import tkinter as tk
import threading
from tkinter import ttk
from tkinter import font as tkFont
from tkinter import scrolledtext, messagebox # Use scrolledtext for easier text areas
import webbrowser
from fetch_movies import MovieManager
from ai_api import get_dialogue, get_image
from PIL import Image, ImageTk
import io
import requests



# --- Constants ---
DARK_BG = "#2e2e2e"
DARK_FG = "#cccccc"
DARK_LISTBOX_BG = "#3c3c3c"
DARK_TEXT_BG = "#3c3c3c"
DARK_BUTTON_BG = "#555555"
DARK_BUTTON_FG = "#ffffff"
ACCENT_COLOR = "#4a90e2" # A slightly brighter color for highlights/buttons

# --- Main Application Class ---
class IMDbApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced IMDb Movie Explorer")
        self.root.geometry("1000x700")
        self.root.configure(bg=DARK_BG)

        self.movie_manager = MovieManager()

        # --- Font Configuration ---
        self.default_font = tkFont.nametofont("TkDefaultFont")
        self.default_font.configure(size=10)
        self.header_font = tkFont.Font(family="Segoe UI", size=12, weight="bold")
        self.title_font = tkFont.Font(family="Segoe UI", size=11, weight="bold")

        # --- Style Configuration ---
        self.setup_styles()

        # --- Main Layout Frames ---
        self.paned_window = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.left_frame = ttk.Frame(self.paned_window, style="Dark.TFrame", padding=10)
        self.right_frame = ttk.Frame(self.paned_window, style="Dark.TFrame", padding=10)

        self.paned_window.add(self.left_frame, weight=1)
        self.paned_window.add(self.right_frame, weight=3)

        # --- Populate Frames ---
        self.create_left_frame()
        self.create_right_frame()

        # --- Store the movies data ---
        self.last_generated_dialogue = {}
        self.top_movies = []

        # --- Fetch IMDb Data ---
        self.populate_movie_list()

    def setup_styles(self):
        """Configures ttk styles for a dark theme."""
        style = ttk.Style(self.root)
        style.theme_use('clam') # Use a theme that allows more customization

        # General widget styles
        style.configure('.', background=DARK_BG, foreground=DARK_FG, font=self.default_font)
        style.configure('TFrame', background=DARK_BG)
        style.configure('Dark.TFrame', background=DARK_BG) # Specific style for our frames
        style.configure('TLabel', background=DARK_BG, foreground=DARK_FG, padding=(5, 2))
        style.configure('Header.TLabel', font=self.header_font, foreground=ACCENT_COLOR)
        style.configure('Title.TLabel', font=self.title_font)

        # Button styles
        style.configure('TButton', background=DARK_BUTTON_BG, foreground=DARK_BUTTON_FG, padding=5)
        style.map('TButton',
                  background=[('active', ACCENT_COLOR), ('pressed', ACCENT_COLOR)],
                  foreground=[('active', DARK_BUTTON_FG)])

        # Entry and Spinbox styles
        style.configure('TEntry', fieldbackground=DARK_LISTBOX_BG, foreground=DARK_FG, insertcolor=DARK_FG)
        style.configure('TSpinbox', fieldbackground=DARK_LISTBOX_BG, foreground=DARK_FG, arrowcolor=DARK_FG, insertcolor=DARK_FG)
        style.map('TSpinbox', background=[('active', DARK_LISTBOX_BG)]) # Keep bg consistent

        # Combobox style
        style.map('TCombobox', fieldbackground=[('readonly', DARK_LISTBOX_BG)],
                                selectbackground=[('readonly', DARK_LISTBOX_BG)], # Prevent selection color change
                                selectforeground=[('readonly', DARK_FG)],
                                foreground=[('readonly', DARK_FG)])
        # Remove the arrow highlight on hover for readonly combobox
        style.map('TCombobox.field', highlightcolor=[('readonly', 'hover', DARK_LISTBOX_BG)])


        # Notebook (Tabs) styles
        style.configure('TNotebook', background=DARK_BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=DARK_BG, foreground=DARK_FG, padding=[10, 5], font=self.default_font)
        style.map('TNotebook.Tab',
                  background=[('selected', DARK_LISTBOX_BG), ('active', DARK_BUTTON_BG)],
                  foreground=[('selected', ACCENT_COLOR)])

        # Scrollbar style
        style.configure('Vertical.TScrollbar', background=DARK_BG, troughcolor=DARK_LISTBOX_BG, bordercolor=DARK_BG, arrowcolor=DARK_FG)
        style.map('Vertical.TScrollbar', background=[('active', DARK_BUTTON_BG)])


    def create_left_frame(self):
        """Creates the widgets for the left frame (movie list)."""
        ttk.Label(self.left_frame, text="Top IMDb Movies", style="Header.TLabel").pack(pady=(0, 10))

        list_frame = ttk.Frame(self.left_frame, style="Dark.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, style='Vertical.TScrollbar')
        self.movie_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg=DARK_LISTBOX_BG,
            fg=DARK_FG,
            borderwidth=0,
            highlightthickness=0, # Remove focus border
            selectbackground=ACCENT_COLOR, # Highlight color for selected item
            selectforeground=DARK_BUTTON_FG,
            activestyle='none', # Remove dotted line on active item
            exportselection=False # Keep selection visible when focus moves
        )
        scrollbar.config(command=self.movie_listbox.yview)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.movie_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.movie_listbox.bind('<<ListboxSelect>>', self.on_movie_select)

    def create_right_frame(self):
        """Creates the widgets for the right frame (details and AI)."""
        # --- AI Controls Frame ---
        ai_controls_frame = ttk.Frame(self.right_frame, style="Dark.TFrame")
        ai_controls_frame.pack(fill=tk.X, pady=(0, 15))
        ai_controls_frame.columnconfigure((1, 3, 5), weight=1) # Allow input fields to expand slightly

        # Dialogue Generation Controls
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
            increment=50, # Step value
            textvariable=self.max_words_var,
            width=7,
            wrap=True
        )
        self.max_words_spinbox.grid(row=0, column=4, padx=(0, 10), pady=5, sticky="w")

        self.generate_dialogue_button = ttk.Button(
            ai_controls_frame,
            text="Generate Dialogue",
            command=self.generate_dialogue,
            state=tk.DISABLED # Disabled until a movie is selected
        )
        self.generate_dialogue_button.grid(row=0, column=5, padx=5, pady=5, sticky="ew")


        # Image Generation Controls
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
            state="readonly", # Prevent user typing custom values
            width=12
        )
        self.style_combobox.grid(row=1, column=4, padx=(0, 10), pady=5, sticky="ew")
        self.style_combobox.set("Futuristic") # Default value

        self.generate_image_button = ttk.Button(
            ai_controls_frame,
            text="Generate Image",
            command=self.generate_image,
            state=tk.DISABLED # Disabled until a movie is selected
        )
        self.generate_image_button.grid(row=1, column=5, padx=5, pady=5, sticky="ew")

        # --- Details Display Area (using Notebook/Tabs) ---
        self.notebook = ttk.Notebook(self.right_frame, style='TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Movie Details
        details_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=10)
        self.notebook.add(details_tab, text=' Movie Details ') # Added spaces for padding

        details_tab.columnconfigure(1, weight=1) # Allow text fields to expand

        ttk.Label(details_tab, text="Title:", style="Title.TLabel").grid(row=0, column=0, sticky="nw", padx=5, pady=2)
        self.title_label = ttk.Label(details_tab, text="", wraplength=600) # Wrap long titles
        self.title_label.grid(row=0, column=1, sticky="nw", padx=5, pady=2)

        ttk.Label(details_tab, text="IMDb URL:", style="Title.TLabel").grid(row=1, column=0, sticky="nw", padx=5, pady=2)
        self.url_label = ttk.Label(details_tab, text="", foreground=ACCENT_COLOR, cursor="hand2") # Make it look clickable
        self.url_label.grid(row=1, column=1, sticky="nw", padx=5, pady=2)
        # Add binding to open URL later if needed
        # self.url_label.bind("<Button-1>", lambda e: self.open_url(self.url_label.cget("text")))

        ttk.Label(details_tab, text="Description:", style="Title.TLabel").grid(row=2, column=0, sticky="nw", padx=5, pady=(10, 2))
        self.description_text = scrolledtext.ScrolledText(
            details_tab, wrap=tk.WORD, height=5, bg=DARK_TEXT_BG, fg=DARK_FG,
            borderwidth=1, relief=tk.SUNKEN, padx=5, pady=5,
            font=self.default_font, state=tk.DISABLED # Read-only initially
        )
        self.description_text.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=2)

        ttk.Label(details_tab, text="Storyline:", style="Title.TLabel").grid(row=4, column=0, sticky="nw", padx=5, pady=(10, 2))
        self.storyline_text = scrolledtext.ScrolledText(
            details_tab, wrap=tk.WORD, height=8, bg=DARK_TEXT_BG, fg=DARK_FG,
            borderwidth=1, relief=tk.SUNKEN, padx=5, pady=5,
            font=self.default_font, state=tk.DISABLED # Read-only initially
        )
        self.storyline_text.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=5, pady=2)
        details_tab.rowconfigure(5, weight=1) # Allow storyline to expand vertically


        # Tab 2: Generated Dialogue
        dialogue_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=10)
        self.notebook.add(dialogue_tab, text=' Generated Dialogue ')

        self.dialogue_output_text = scrolledtext.ScrolledText(
            dialogue_tab, wrap=tk.WORD, bg=DARK_TEXT_BG, fg=DARK_FG,
            borderwidth=1, relief=tk.SUNKEN, padx=5, pady=5,
            font=self.default_font, state=tk.DISABLED # Read-only
        )
        self.dialogue_output_text.pack(fill=tk.BOTH, expand=True)

        # Tab 3: Generated Image
        image_tab = ttk.Frame(self.notebook, style="Dark.TFrame", padding=10)
        self.notebook.add(image_tab, text=' Generated Image ')

        self.image_label = ttk.Label(
            image_tab,
            text="Image will appear here",
            anchor=tk.CENTER,
            # relief=tk.SUNKEN, # Optional: add border
            # borderwidth=1,
            background=DARK_LISTBOX_BG # Slightly different background for emphasis
        )
        # Use pack or grid to center the label/image area
        image_tab.rowconfigure(0, weight=1)
        image_tab.columnconfigure(0, weight=1)
        self.image_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        # You will need PIL/Pillow to actually display images:
        # from PIL import Image, ImageTk
        # Then load and assign image like:
        # tk_image = ImageTk.PhotoImage(pil_image)
        # self.image_label.config(image=tk_image, text="") # Remove text when image loads
        # self.image_label.image = tk_image # Keep reference

    def populate_movie_list(self):
        """Fetches and displays the IMDb top 10 movies."""
        # Show loading message
        self.movie_listbox.delete(0, tk.END)
        self.movie_listbox.insert(tk.END, "Loading IMDb top 10...")
        self.movie_listbox.update()

        try:
            # Fetch movie data using MovieManager
            movies = self.movie_manager.fetch_top_movies(limit=10)

            # Clear loading message and add movies
            self.movie_listbox.delete(0, tk.END)
            self.top_movies = []

            for rank, movie in sorted(movies.items()):
                title = movie['title']
                self.top_movies.append((rank, title))
                self.movie_listbox.insert(tk.END, title)

        except Exception as e:
            # Handle error if movie fetch fails
            self.movie_listbox.delete(0, tk.END)
            self.movie_listbox.insert(tk.END, "Error fetching movies")
            messagebox.showerror("Fetch Error", f"Failed to fetch movies: {str(e)}")
            print(f"Error fetching top movies: {e}")

    def set_text_widget_content(self, text_widget, content):
        """Helper to safely update content in a disabled Text widget."""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)
        text_widget.insert('1.0', content)
        text_widget.config(state=tk.DISABLED)

    def on_movie_select(self, event=None):
        selected_indices = self.movie_listbox.curselection()
        if not selected_indices:
            self.clear_details()
            self.generate_dialogue_button.config(state=tk.DISABLED)
            self.generate_image_button.config(state=tk.DISABLED)
            return

        selected_index = selected_indices[0]
        if selected_index >= len(self.top_movies):
            messagebox.showerror("Selection Error", "Invalid movie selection")
            return

        rank, movie_title = self.top_movies[selected_index]

        # Show loading placeholders in GUI
        self.set_text_widget_content(self.description_text, "Loading movie details...")
        self.set_text_widget_content(self.storyline_text, "Loading storyline...")
        self.generate_dialogue_button.config(state=tk.DISABLED)
        self.generate_image_button.config(state=tk.DISABLED)
        self.root.update()

        def worker():
            try:
                movie_data = self.movie_manager.fetch_movie_details_by_rank(rank)

                title = f"{movie_data.get('title', 'N/A')} ({movie_data.get('year', 'N/A')})"
                imdb_id = movie_data.get('imdb_id', '')
                url = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else f"https://www.imdb.com/find?q={movie_title.replace(' ', '+')}"
                description = (
                    f"Rating: {movie_data.get('rating', 'N/A')}\n"
                    f"Synopsis: {movie_data.get('storyline', 'No synopsis available.').split('.')[0]}."
                )
                storyline = movie_data.get('storyline', 'No storyline available.')

                def update_gui():
                    self.title_label.config(text=title)
                    self.url_label.config(text=url)
                    self.url_label.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
                    self.set_text_widget_content(self.description_text, description)
                    self.set_text_widget_content(self.storyline_text, storyline)
                    self.set_text_widget_content(self.dialogue_output_text, "")
                    self.image_label.config(image="", text="Image will appear here")
                    self.generate_dialogue_button.config(state=tk.NORMAL)
                    self.generate_image_button.config(state=tk.NORMAL)
                    self.notebook.select(0)

                self.root.after(0, update_gui)

            except Exception as e:
                def handle_error():
                    self.set_text_widget_content(self.description_text, f"Failed to fetch movie details: {str(e)}")
                    self.set_text_widget_content(self.storyline_text, "")
                    messagebox.showerror("Fetch Error", f"Failed to fetch movie details: {str(e)}")

                self.root.after(0, handle_error)

        threading.Thread(target=worker, daemon=True).start()

    def clear_details(self):
        """Clears the details and AI output areas."""
        self.title_label.config(text="")
        self.url_label.config(text="")
        self.set_text_widget_content(self.description_text, "")
        self.set_text_widget_content(self.storyline_text, "")
        self.set_text_widget_content(self.dialogue_output_text, "")
        self.image_label.config(image="", text="Select a movie")
        # self.image_label.image = None # Clear image reference if using PIL

    def generate_dialogue(self):
        selected_indices = self.movie_listbox.curselection()
        if not selected_indices:
            self.set_text_widget_content(self.dialogue_output_text, "Error: Please select a movie first.")
            return

        rank, movie_title = self.top_movies[selected_indices[0]]
        movie_data = self.movie_manager.fetch_movie_details_by_rank(rank)
        storyline = movie_data.get('storyline', '')
        num_chars = self.char_count_var.get()
        max_words = self.max_words_var.get()

        self.set_text_widget_content(self.dialogue_output_text, "Generating dialogue, please wait...")
        self.notebook.select(1)

        def worker():
            try:
                dialogue = get_dialogue(storyline, num_chars, max_words)
                self.last_generated_dialogue[movie_title] = dialogue
                self.root.after(0, lambda: self.set_text_widget_content(self.dialogue_output_text, dialogue))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Dialogue Error",
                                                                f"Failed to generate dialogue: {str(e)}"))

        threading.Thread(target=worker, daemon=True).start()

    def generate_image(self):
        selected_indices = self.movie_listbox.curselection()
        if not selected_indices:
            self.image_label.config(text="Error: Please select a movie first.")
            return

        rank, movie_title = self.top_movies[selected_indices[0]]
        location = self.location_var.get().strip() or "Unknown location"
        style = self.style_var.get() or "Futuristic"

        self.image_label.config(image="", text="Generating image, please wait...")
        self.notebook.select(2)

        def worker():
            if movie_title in self.last_generated_dialogue:
                dialogue = self.last_generated_dialogue[movie_title]
            else:
                try:
                    movie_data = self.movie_manager.fetch_movie_details_by_rank(rank)
                    storyline = movie_data.get('storyline', 'No storyline available.')
                    num_chars = self.char_count_var.get()
                    max_words = self.max_words_var.get()
                    dialogue = get_dialogue(storyline, num_chars, max_words)
                    self.last_generated_dialogue[movie_title] = dialogue
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
                    pil_image = pil_image.resize((512, 512))  # Resize if needed
                    tk_image = ImageTk.PhotoImage(pil_image)

                    def update_gui_with_image():
                        self.image_label.config(image=tk_image, text="")
                        self.image_label.image = tk_image  # Keep reference

                    self.root.after(0, update_gui_with_image)

                except Exception as e:
                    self.root.after(0, lambda: self.image_label.config(text=f"Failed to load image: {e}"))


            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Image Error", f"Failed to generate image: {str(e)}"))

        threading.Thread(target=worker, daemon=True).start()


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = IMDbApp(root)
    root.mainloop()