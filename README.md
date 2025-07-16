# slipscanner-llm

A little AI assisted app to convert photos of purchase slips to csv.

## Requirements
- Ollama installed, and `mistral` running
- Alternatively `phi` (phi-2.Q4_K_M.gguf) downloaded and added to the `models` folder.

### Running
- `python3 slipscanner_llm_mistral.py` or
- `python3 slipscanner_llm_phi.py`

### Building
- `python3 -m pyinstaller --windowed --onefile slipscanner_llm_mistral.py` or
- `python3 -m pyinstaller --windowed --onefile slipscanner_llm_phi.py`

Executable can be found in the `dist` folder