import logging
import sys
import tkinter as tk

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        self.text_widget.after(0, append)

def setup_logger(text_widget):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    gui_handler = TextHandler(text_widget)
    gui_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s')) # Kürzeres Format
    logger.addHandler(gui_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(console_handler)
    return logger
