"""Entry point for the Coordinate Format Converter application."""

import tkinter as tk
from gui import CoordConverterApp


def main():
    root = tk.Tk()
    _app = CoordConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
