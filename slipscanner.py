import tkinter as tk
from tkinter import filedialog, messagebox
import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"
from PIL import Image
import pandas as pd
import re
import os
import string

def clean_description(text):
    # Remove leading non-alphabetic characters (like $ § S Z etc.)
    text = re.sub(r'^[^a-zA-Z]+', '', text)

    # Normalize spaces
    text = re.sub(r'\s+', ' ', text)

    # Fix common OCR character misreads generically
    ocr_corrections = {
        '0': 'O',  # zero to capital O
        '1': 'l',  # one to lowercase L
        '5': 'S',  # five to S
        '|': 'l',
    }

    for wrong, right in ocr_corrections.items():
        text = text.replace(wrong, right)

    # Remove any trailing non-printable characters
    text = ''.join([c for c in text if c in string.printable])

    # Strip spaces and title case
    text = text.strip().title()

    return text

def extract_items(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)

        items = []
        for line in text.split('\n'):
            match = re.search(r'(.+?)\s+(\d{1,3}\.\d{2})$', line.strip())
            if match:
                desc = match.group(1).strip()
                desc = clean_description(desc)
                price = float(match.group(2))
                items.append([desc, '', '', price])
        return items
    except Exception as e:
        messagebox.showerror("Error", f"Failed to process image:\n{e}")
        return []

def select_image():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
    if not file_path:
        return

    items = extract_items(file_path)
    if not items:
        return

    save_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV files", "*.csv")],
                                             initialfile="receipt_output.csv")
    if not save_path:
        return

    df = pd.DataFrame(items, columns=["description", "category", "units", "price"])
    df.to_csv(save_path, index=False)
    messagebox.showinfo("Success", f"CSV saved:\n{save_path}")

# GUI Setup
app = tk.Tk()
app.title("Receipt to CSV")
app.geometry("300x150")

label = tk.Label(app, text="Convert receipt photo to Notion-ready CSV", wraplength=280)
label.pack(pady=20)

button = tk.Button(app, text="Select Receipt Image", command=select_image)
button.pack()

app.mainloop()