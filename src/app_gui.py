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

        # Initialize movie selection tracking
        self.selected_rank = None
        self.selected_title = None

        # Initialize other necessary objects
        self.last_generated_dialogue = {}
        self.top_movies = []
        self.poster_images = {}  # Dictionary to store poster images

        # --- Font Configuration ---
        self.default_font = tkFont.nametofont("TkDefaultFont")
        self.default_font.configure(size=10)
        self.header_font = tkFont.Font(family="Segoe UI", size=12, weight="bold")
        self.title_font = tkFont.Font(family="Segoe UI", size=11, weight="bold")

        # Set up the UI components
        self.setup_styles()
        self.create_ui_layout()

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
        """Creates the widgets for the left frame (movie list with posters)."""
        ttk.Label(self.left_frame, text="Top IMDb Movies", style="Header.TLabel").pack(pady=(0, 10))

        # Create a frame for canvas and scrollbar
        list_frame = ttk.Frame(self.left_frame, style="Dark.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Create canvas
        self.movies_canvas = tk.Canvas(
            list_frame,
            bg=DARK_BG,
            highlightthickness=0,
            bd=0
        )
        self.movies_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL,
            command=self.movies_canvas.yview,
            style='Vertical.TScrollbar'
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.movies_canvas.configure(yscrollcommand=scrollbar.set)

        # Create a frame inside the canvas to hold movie items
        self.movie_items_frame = ttk.Frame(self.movies_canvas, style="Dark.TFrame")

        self.movie_items_frame_id = self.movies_canvas.create_window(
            (0, 0), window=self.movie_items_frame, anchor="nw"
        )

        # Bind to configure scrollregion
        def on_frame_configure(event):
            self.movies_canvas.configure(scrollregion=self.movies_canvas.bbox("all"))

        self.movie_items_frame.bind("<Configure>", on_frame_configure)

        # Fix inner frame width on canvas resize
        def on_canvas_configure(event):
            canvas_width = event.width
            self.movies_canvas.itemconfig(self.movie_items_frame_id, width=canvas_width)

        self.movies_canvas.bind("<Configure>", on_canvas_configure)


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

    def create_ui_layout(self):
        """Create the main UI layout with frames."""
        # Create main frames
        self.left_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=10)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        self.right_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=10)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create the content for each frame
        self.create_left_frame()
        self.create_right_frame()

    def populate_movie_list(self):
        """Fetches and displays the IMDb top 10 movies with posters."""
        # Clear existing movie items
        for widget in self.movie_items_frame.winfo_children():
            widget.destroy()

        # Show loading message
        loading_label = ttk.Label(self.movie_items_frame, text="Loading IMDb top 10...", style="TLabel")
        loading_label.pack(pady=10, padx=5, fill=tk.X)
        self.movies_canvas.update()

        try:
            # Fetch movie data using MovieManager
            movies = self.movie_manager.fetch_top_movies(limit=10)
            self.movie_manager.fetch_all_details()  # This will fetch details including poster URLs

            # Clear loading message
            loading_label.destroy()
            self.top_movies = []

            # For each movie, create a frame with poster and title
            for rank, movie in sorted(movies.items()):
                title = movie['title']
                self.top_movies.append((rank, title))

                # Create frame for movie item
                movie_frame = ttk.Frame(self.movie_items_frame, style="Dark.TFrame", padding=5)
                movie_frame.pack(fill=tk.X, pady=2)

                # Add poster image if available
                poster_url = self.movie_manager.movies[rank].get('poster_url')
                poster_label = ttk.Label(movie_frame, background=DARK_LISTBOX_BG)

                if poster_url:
                    try:
                        # Download and display poster
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

                # Add title label
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

                # Bind click event to select movie
                def make_select_handler(idx):
                    return lambda e: self.select_movie(idx)

                movie_frame.bind("<Button-1>", make_select_handler(rank - 1))  # Adjust for 0-based index
                title_label.bind("<Button-1>", make_select_handler(rank - 1))
                poster_label.bind("<Button-1>", make_select_handler(rank - 1))

        except Exception as e:
            # Handle error if movie fetch fails
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

    def on_movie_select(self, event=None, index=None, rank=None, movie_title=None):
        """Handle movie selection, either from listbox event or direct selection."""
        if event is not None:  # Called from old listbox - this branch can be removed when you've fully switched
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
        elif index is None or rank is None or movie_title is None:
            return

        # Show loading placeholders in GUI
        self.set_text_widget_content(self.description_text, "Loading movie details...")
        self.set_text_widget_content(self.storyline_text, "Loading storyline...")
        self.generate_dialogue_button.config(state=tk.DISABLED)
        self.generate_image_button.config(state=tk.DISABLED)
        self.root.update()

        # Fetch movie details
        try:
            # Use the rank to get the movie details
            movie_data = self.movie_manager.fetch_movie_details_by_rank(rank)

            # Update the details in the UI
            self.title_label.config(text=f"{movie_data.get('title', 'Unknown')} ({movie_data.get('year', 'N/A')})")

            # Set URL and make it clickable
            url = movie_data.get('url', '')
            self.url_label.config(text=url)
            if url:
                self.url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

            # Update description and storyline
            self.set_text_widget_content(self.description_text,
                                         movie_data.get('description', 'No description available.'))
            self.set_text_widget_content(self.storyline_text, movie_data.get('storyline', 'No storyline available.'))

            # Enable AI generation buttons
            self.generate_dialogue_button.config(state=tk.NORMAL)
            self.generate_image_button.config(state=tk.NORMAL)

            # Switch to the details tab
            self.notebook.select(0)  # Select the Movie Details tab

        except Exception as e:
            self.clear_details()
            messagebox.showerror("Movie Details Error", f"Failed to load movie details: {str(e)}")
            print(f"Error loading movie details: {e}")

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
        """Generate a dialogue based on the selected movie."""
        if not hasattr(self, 'selected_rank') or not self.selected_rank:
            self.set_text_widget_content(self.dialogue_output_text, "Error: Please select a movie first.")
            return

        movie_data = self.movie_manager.fetch_movie_details_by_rank(self.selected_rank)
        storyline = movie_data.get('storyline', '')
        num_chars = self.char_count_var.get()
        max_words = self.max_words_var.get()

        self.set_text_widget_content(self.dialogue_output_text, "Generating dialogue, please wait...")
        self.notebook.select(1)  # Switch to dialogue tab

        def worker():
            try:
                dialogue = get_dialogue(storyline, num_chars, max_words)
                self.last_generated_dialogue[self.selected_title] = dialogue
                self.root.after(0, lambda: self.set_text_widget_content(self.dialogue_output_text, dialogue))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Dialogue Error",
                                                                f"Failed to generate dialogue: {str(e)}"))

        threading.Thread(target=worker, daemon=True).start()

    def generate_image(self):
        """Generate an image based on the selected movie."""
        if not hasattr(self, 'selected_rank') or not self.selected_rank:
            self.image_label.config(text="Error: Please select a movie first.")
            return

        location = self.location_var.get().strip() or "Unknown location"
        style = self.style_var.get() or "Futuristic"

        self.image_label.config(image="", text="Generating image, please wait...")
        self.notebook.select(2)  # Switch to image tab

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

            # Resize poster to appropriate dimensions
            img = img.resize((80, 120), Image.LANCZOS)

            # Convert to PhotoImage for Tkinter
            tk_img = ImageTk.PhotoImage(img)

            # Store reference to prevent garbage collection
            self.poster_images[rank] = tk_img

            # Update label with image
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

        # Update selection state for movie frames
        for i, child in enumerate(self.movie_items_frame.winfo_children()):
            # For ttk widgets, we need to use style instead of direct background
            for widget in child.winfo_children():
                if i == index:
                    if isinstance(widget, ttk.Label):
                        widget.configure(background=ACCENT_COLOR)
                else:
                    if isinstance(widget, ttk.Label):
                        widget.configure(background=DARK_LISTBOX_BG)

        # Get rank and title
        rank, movie_title = self.top_movies[index]

        # Store the currently selected movie for AI features
        self.selected_rank = rank
        self.selected_title = movie_title

        # Show loading placeholders
        self.set_text_widget_content(self.description_text, "Loading movie details...")
        self.set_text_widget_content(self.storyline_text, "Loading storyline...")
        self.root.update()

        try:
            # Fetch movie details
            movie_data = self.movie_manager.fetch_movie_details_by_rank(rank)

            # Update the UI with movie details
            self.title_label.config(text=f"{movie_data.get('title', 'Unknown')} ({movie_data.get('year', 'N/A')})")

            # Set URL and make it clickable
            url = movie_data.get('url', '')
            self.url_label.config(text=url)
            if url:
                self.url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

            # Update description and storyline
            self.set_text_widget_content(self.description_text,
                                         movie_data.get('description', 'No description available.'))
            self.set_text_widget_content(self.storyline_text,
                                         movie_data.get('storyline', 'No storyline available.'))

            # Enable AI generation buttons
            self.generate_dialogue_button.config(state=tk.NORMAL)
            self.generate_image_button.config(state=tk.NORMAL)

            # Store the currently selected movie for AI features
            self.selected_rank = rank
            self.selected_title = movie_title

            # Switch to the details tab
            self.notebook.select(0)  # Select the Movie Details tab

        except Exception as e:
            self.clear_details()
            messagebox.showerror("Movie Details Error", f"Failed to load movie details: {str(e)}")
            print(f"Error loading movie details: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = IMDbApp(root)
    root.mainloop()
