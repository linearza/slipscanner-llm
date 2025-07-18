import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pytesseract
from PIL import Image
import pandas as pd
import json
import re
import requests
import threading

# --- Tesseract config ---
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"

# --- Prompt Templates ---
PROMPT_TEMPLATES = {
    "Default (Receipt Parser)": """
You are a receipt parser. The input text is from pytesseract OCR scanner.
The receipt likely contains logos and shop information which you can ignore, isolate the line item section first.
Cleanup and extract line items from the text below.
Each item should have: description, price (as float).
There could be multiple items with the same values, don't try to merge them.
Ensure that the final line item count matches the original count.
Where possible, complete truncated words, such as "tyaki" to "Teriyaki" and "Chick" to "Chicken"
Be mindful of secondary lines which output auxillary information like weights and variants - I am only concerned with the description and price.
Output ONLY a valid JSON array of objects, e.g.:

[
  {"description": "item 1", "price": 9.99},
  {"description": "item 2", "price": 5.50}
]

Do NOT output any extra text, comments, or markdown formatting.

Text:
{text}

Output:
"""
}

selected_template_name = "Default (Receipt Parser)"
ocr_text_global = ""
last_ocr_text = None
generated_df = None

def generate_csv_workflow():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
    if not file_path:
        chat_log.insert(tk.END, "[System] No image selected.\n", "system")
        return

    chat_log.insert(tk.END, "[System] Running OCR...\n", "system")
    global last_ocr_text
    last_ocr_text = extract_text_from_image(file_path)
    text = last_ocr_text

    # OCR Window
    ocr_window = tk.Toplevel(app)
    ocr_window.title("OCR Result")
    ocr_window.geometry("600x400")
    ocr_text_widget = tk.Text(ocr_window, wrap=tk.WORD)
    ocr_text_widget.pack(expand=True, fill=tk.BOTH)
    ocr_text_widget.insert(tk.END, text)
    ocr_text_widget.config(state=tk.DISABLED)
    tk.Button(ocr_window, text="Close", command=ocr_window.destroy).pack(pady=5)

    prompt = PROMPT_TEMPLATES[selected_template_name].replace("{text}", text)

    # Prompt Window
    prompt_window = tk.Toplevel(app)
    prompt_window.title("Prompt Sent to LLM")
    prompt_window.geometry("600x400")
    prompt_text_widget = tk.Text(prompt_window, wrap=tk.WORD)
    prompt_text_widget.pack(expand=True, fill=tk.BOTH)
    prompt_text_widget.insert(tk.END, prompt)
    prompt_text_widget.config(state=tk.DISABLED)
    tk.Button(prompt_window, text="Close", command=prompt_window.destroy).pack(pady=5)

    def threaded_call():
        try:
            response = call_ollama(prompt)
            chat_log.insert(tk.END, f"[LLM]:\n{response}\n", "llm")
            parsed = safe_json_parse(response)
            if not parsed:
                return

            global generated_df
            generated_df = pd.DataFrame([[item.get("description", ""), "", "", item.get("price", 0)] for item in parsed],
                                        columns=["description", "category", "units", "price"])

            csv_preview = generated_df.to_csv(index=False)
            chat_log.insert(tk.END, f"[CSV Preview]:\n{csv_preview}\n", "llm")
            export_button.config(state=tk.NORMAL)

        finally:
            set_ui_state(False)

    set_ui_state(True)
    threading.Thread(target=threaded_call, daemon=True).start()


# --- OCR Extraction ---
def extract_text_from_image(image_path):
    try:
        img = Image.open(image_path)
        return pytesseract.image_to_string(img)
    except Exception as e:
        messagebox.showerror("OCR Error", f"Failed to extract text from image:\n{e}")
        return ""

# --- JSON Parse ---
def safe_json_parse(response):
    try:
        match = re.search(r'(\[\s*{.*?}\s*\])', response, re.DOTALL)
        if not match:
            raise ValueError("No JSON array found.")
        json_part = match.group(1)
        cleaned = re.sub(r',\s*([\]}])', r'\1', json_part.strip())
        cleaned = re.sub(r'"\s*,\s*"', '", "', cleaned)
        return json.loads(cleaned)
    except Exception as e:
        messagebox.showerror("Parse Error", f"Could not decode LLM output:\n{e}\n\nRaw output:\n{response}")
        return []

# --- LLM Interaction ---
SYSTEM_PROMPT = """You are an assistant for parsing receipts. If the user says things like 'generate the CSV', respond with __COMMAND__:generate_csv. Otherwise, answer naturally."""

def call_ollama(prompt, model="mistral"):
    try:
        prompt = SYSTEM_PROMPT + "\n\nUser: " + prompt
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        messagebox.showerror("Ollama Error", "Ollama is not running.\nStart it by running: `ollama serve`.")
        return ""
    except Exception as e:
        messagebox.showerror("LLM Error", f"Failed to call Ollama:\n{e}")
        return ""

def set_ui_state(disabled=True):
    state = tk.DISABLED if disabled else tk.NORMAL
    for child in button_frame.winfo_children():
        child.config(state=state)

def send_prompt():
    prompt = prompt_entry.get("1.0", tk.END).strip()
    if not prompt:
        return

    chat_log.insert(tk.END, f"\n[You]:\n{prompt}\n\n", "user")
    chat_log.insert(tk.END, "[System] Sending to LLM...\n", "system")
    chat_log.see(tk.END)
    set_ui_state(True)

    def run_llm():
        try:
            response = call_ollama(prompt)
            chat_log.insert(tk.END, f"[LLM]:\n{response}\n", "llm")
        except Exception as e:
            chat_log.insert(tk.END, f"[Error]: {e}\n", "error")
        finally:
            set_ui_state(False)
            chat_log.see(tk.END)

    threading.Thread(target=run_llm, daemon=True).start()

def export_generated_csv():
    global generated_df
    if generated_df is None:
        messagebox.showwarning("Export Error", "No CSV data available to export.")
        return

    save_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV files", "*.csv")],
                                             initialfile="receipt_output.csv")
    if not save_path:
        return

    try:
        generated_df.to_csv(save_path, index=False)
        messagebox.showinfo("Success", f"CSV saved:\n{save_path}")
        chat_log.insert(tk.END, f"[System] CSV exported to:\n{save_path}\n", "system")
    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to save CSV:\n{e}")

# --- GUI Layout ---
app = tk.Tk()
app.title("LLM Receipt Chat Interface")
app.geometry("700x600")

chat_log = scrolledtext.ScrolledText(app, wrap=tk.WORD, height=20)
chat_log.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
chat_log.tag_config("user", foreground="lightblue")
chat_log.tag_config("llm", foreground="lightgreen")
chat_log.tag_config("system", foreground="gray")
chat_log.tag_config("error", foreground="red")

prompt_entry = scrolledtext.ScrolledText(app, height=6)
prompt_entry.pack(padx=10, pady=(0, 10), fill=tk.X)

def handle_cmd_enter(event):
    send_prompt()
    return "break"

prompt_entry.bind("<Command-Return>", handle_cmd_enter)

button_frame = tk.Frame(app)
button_frame.pack(pady=5)

tk.Button(button_frame, text="Generate CSV", command=generate_csv_workflow).pack(side=tk.LEFT, padx=5)

export_button = tk.Button(button_frame, text="Export CSV", command=export_generated_csv)
export_button.pack(side=tk.LEFT, padx=5)
export_button.config(state=tk.DISABLED)

app.mainloop()
