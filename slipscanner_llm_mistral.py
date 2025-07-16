
import tkinter as tk
from tkinter import filedialog, messagebox
import pytesseract
from PIL import Image
import pandas as pd
import subprocess
import json
import re
import os
import requests

# Optional: Set Tesseract path if needed
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"  # macOS/Homebrew example

# def safe_json_parse(response):
#     try:
#         # Fix common LLM mistakes
#         cleaned = response.strip()

#         # Remove trailing commas inside objects or arrays
#         cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)

#         # Remove stray quotation-comma combinations
#         cleaned = re.sub(r'"\s*,\s*"', '", "', cleaned)

#         return json.loads(cleaned)
#     except Exception as e:
#         messagebox.showerror("Parse Error", f"Could not decode LLM output:\n{e}\n\nRaw output:\n{response}")
#         return []
def safe_json_parse(response):
    try:
        # Find JSON array using regex
        match = re.search(r'(\[\s*{.*?}\s*\])', response, re.DOTALL)
        if not match:
            raise ValueError("No JSON array found in response.")

        json_part = match.group(1)

        # Fix common LLM issues
        cleaned = json_part.strip()
        cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
        cleaned = re.sub(r'"\s*,\s*"', '", "', cleaned)

        return json.loads(cleaned)
    except Exception as e:
        messagebox.showerror("Parse Error", f"Could not decode LLM output:\n{e}\n\nRaw output:\n{response}")
        return []


# --- OCR + Cleaning ---
def extract_text_from_image(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        messagebox.showerror("OCR Error", f"Failed to extract text from image:\n{e}")
        return ""

# --- LLM Parsing ---
def call_ollama(prompt, model="mistral"):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False  # disables streaming
            },
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()

    except requests.exceptions.ConnectionError:
        messagebox.showerror("Ollama Error", "Ollama is not running.\nStart it by running: `ollama serve`.")
        return ""
    except Exception as e:
        messagebox.showerror("LLM Error", f"Failed to call Ollama:\n{e}")
        return ""

# --- Prompt Template ---
def generate_prompt(text):
    print(text)
    return f"""
You are a receipt parser. The input text is from pytesseract OCR scanner.
The receipt likely contains logos and shop information which you can ignore, isolate the line item section first.
Cleanup and extract line items from the text below. Output as JSON array.
Each item should have: description, price (as float).
There could be multiple items with the same values, dont try to merge them.
Ensure that the final line item count matches the original count.
Where possible, complete truncated words, such as "tyaki" to "Teriyaki" and "Chick" to "Chicken"

Text:
{text}

Output:
"""

# --- Main Workflow ---
def process_receipt(image_path):
    ocr_text = extract_text_from_image(image_path)
    if not ocr_text:
        return []

    prompt = generate_prompt(ocr_text)
    llm_response = call_ollama(prompt)

    try:
        parsed = safe_json_parse(llm_response)
        items = [[item.get("description", ""), "", "", item.get("price", 0)] for item in parsed]
        return items
    except Exception as e:
        messagebox.showerror("Parse Error", f"Could not decode LLM output:\n{e}\n\nRaw output:\n{llm_response}")
        return []

# --- GUI Setup ---
def select_image():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
    if not file_path:
        return

    items = process_receipt(file_path)
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

# --- GUI Window ---
app = tk.Tk()
app.title("Receipt to CSV (with LLM)")
app.geometry("320x160")

label = tk.Label(app, text="Convert a receipt image to structured CSV using LLM.", wraplength=280)
label.pack(pady=20)

button = tk.Button(app, text="Select Receipt Image", command=select_image)
button.pack()

app.mainloop()
