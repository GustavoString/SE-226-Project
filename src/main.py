import tkinter as tk
from tkinter import messagebox
from fetch_movies import MovieManager
from app_gui import IMDbApp


def main():
    try:
        # Initialize and load movie data first to avoid fetching delays
        movie_manager = MovieManager()

        # Try to load existing data from file or fetch from IMDb
        try:
            movie_manager.load_from_file()
            if not movie_manager.movies:  # If file was empty or didn't exist
                movie_manager.fetch_top_movies(limit=10)
                movie_manager.fetch_all_details()
                movie_manager.save_to_file()
        except Exception as e:
            messagebox.showwarning(
                "Data Loading Warning",
                f"Could not load movie data: {str(e)}\nWill fetch fresh data from IMDb."
            )
            movie_manager.fetch_top_movies(limit=10)
            movie_manager.fetch_all_details()
            movie_manager.save_to_file()

        # Start the GUI with preloaded data
        root = tk.Tk()
        app = IMDbApp(root)
        app.movie_manager = movie_manager
        app.populate_movie_list()
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Application Error", f"An error occurred: {str(e)}")
        raise


if __name__ == "__main__":
    main()
