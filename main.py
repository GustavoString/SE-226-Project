import tkinter as tk
from tkinter import messagebox
from app_gui import IMDbApp

def main():
    try:
        root = tk.Tk()
        app = IMDbApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Application Error", f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()