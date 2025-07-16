# slipscanner-llm

A little AI assisted app to convert photos of purchase slips to csv.

# Requirements
- Ollama installed, and `mistral` running
- Alternatively `phi` downloaded and added to the `models` folder.

Run with `python3 slipscanner_llm_mistral.py` or `python3 slipscanner_llm_phi.py`
Build with `python3 -m pyinstaller --windowed --onefile slipscanner_llm_mistral.py`