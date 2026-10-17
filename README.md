# CaseWeaver Lite

**AI-Powered Crime Investigation Assistant**

CaseWeaver Lite is a hackathon prototype that analyzes fictional witness statements to help investigators organize evidence. It reconstructs event timelines, maps people and reported relationships, and highlights potential inconsistencies.

It is a decision-support tool, not a replacement for human investigation.

## Features

- **Timeline reconstruction:** Extract events, dates, times, locations, people, and source quotations.
- **Identity and relationship mapping:** Organize named individuals, reported roles, and explicitly supported relationships.
- **Potential inconsistencies:** Compare accounts and highlight claims requiring further verification.
- **Evidence traceability:** Link findings to original statements and quotations.
- **Local AI inference:** Use Google Gemma through Ollama.
- **Validation:** Validate input data and model outputs.
- **Development mode:** Support explicitly enabled, clearly labelled deterministic fixtures for testing.

## Technology

- Python 3.11+
- Streamlit
- Google Gemma through Ollama
- Pydantic v2
- Plotly
- Graphviz
- pytest

## Project structure

```text
CaseWeaver-Lite/
├── app.py
├── core/
│   ├── __init__.py
│   ├── schemas.py
│   ├── gemma_client.py
│   └── analysis.py
├── modules/
│   ├── __init__.py
│   ├── timeline.py
│   ├── identity.py
│   └── inconsistencies.py
├── data/
│   └── sample_case.json
├── tests/
│   ├── __init__.py
│   └── test_case.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Prerequisites

- Windows, macOS, or Linux
- Python 3.11 or newer
- Ollama for local AI inference
- Git (recommended)

Python 3.11–3.13 is recommended for predictable dependency compatibility during the hackathon.

## Setup: Windows PowerShell

Open a terminal in the project directory.

Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use the virtual environment's Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Setup: macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Install Ollama and Gemma

Install Ollama from https://ollama.com/.

Download the recommended starting model:

```bash
ollama pull gemma3:1b
```

Check installed models:

```bash
ollama list
```

Test inference:

```bash
ollama run gemma3:1b "Return only JSON: {\"status\":\"ok\"}"
```

Ollama must be running locally for real model inference. The application must report inference failures honestly and must not silently substitute mock results.

## Configuration

Default settings:

- `OLLAMA_HOST`: `http://localhost:11434`
- `OLLAMA_MODEL`: `gemma3:1b`
- Request timeout: 90 seconds by default

Windows PowerShell:

```powershell
$env:OLLAMA_HOST = "http://localhost:11434"
$env:OLLAMA_MODEL = "gemma3:1b"
```

macOS/Linux:

```bash
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="gemma3:1b"
```

These settings apply to the current terminal session unless configured otherwise.

## Run the application

After `app.py` has been implemented:

```bash
streamlit run app.py
```

Streamlit prints a local URL in the terminal. Open that URL in your browser.

## Run tests

```bash
python -m pytest -q
```

Check Python syntax:

```bash
python -m compileall -q core modules app.py tests
```

Live Ollama smoke tests should be opt-in. Ordinary unit tests must not require a running model or network access.

## Team ownership

- **Technical lead/integration:** shared schemas, Gemma client, validation, fixtures, tests, dependencies, documentation, and integration.
- **Timeline developer:** `modules/timeline.py`.
- **Identity/evidence developer:** `modules/identity.py` and `modules/inconsistencies.py`.
- **Frontend developer:** `app.py`.

## Shared module interfaces

```python
from core.gemma_client import ask_gemma
from modules.timeline import extract_events
from modules.identity import extract_identities
from modules.inconsistencies import detect_inconsistencies
```

Expected signatures:

```python
ask_gemma(prompt: str) -> str
extract_events(case_data: dict) -> list[dict]
extract_identities(case_data: dict) -> dict
detect_inconsistencies(case_data: dict) -> dict
```

All analysis functions accept the complete canonical case dictionary.

Shared validation and hypothetical-analysis helpers:

```python
from core.analysis import parse_model_json, apply_what_if
from core.schemas import HeatmapResult, HeatmapFinding
```

```python
parse_model_json(text: str) -> dict
apply_what_if(events: list[dict], time_overrides: dict[str, str]) -> dict
```

- `parse_model_json` accepts a JSON object (optional markdown fences). Malformed JSON or a non-object (array, string, number) raises a clear error. It never fabricates keys or wraps invalid output.
- `apply_what_if` deep-copies extracted events and applies hypothetical `Event.time` values keyed by `event_id`. It returns `{"events": [...], "changes": [{"event_id", "field": "time", "previous", "updated"}, ...]}`. Original events, case statements, and source quotations are never mutated. Statement or text overrides are not supported. Events without `event_id` cannot be overridden.

### HeatmapResult schema

`HeatmapResult` is the shared output contract for a statement-by-statement discrepancy heatmap:

- `statement_ids`: ordered unique statement IDs (matrix axis labels)
- `scores`: square `n x n` symmetric matrix of floats in `[0, 1]`, where `n = len(statement_ids)`
- `findings`: optional `HeatmapFinding` list (`statement_a_id`, `statement_b_id`, `score`, `summary`)

A statement compared with itself must have score `0` (`scores[i][i] == 0`). Scores are **potential discrepancy signals**, not proof of dishonesty and not credibility scores.

## Responsible use

- All demonstration cases and statements are fictional.
- A potential inconsistency is not proof that a person lied.
- An extraction confidence score is not a credibility score.
- Preserve original statements and source quotations.
- Missing information must remain unknown rather than being invented.
- Human review is required before drawing conclusions.
- The application must not automatically identify a culprit.

## Known limitations

- Small local language models can misinterpret statements and output malformed JSON.
- Extracted dates, times, identities, and relationships require verification.
- Similar names do not establish that two references identify the same person.
- Contradictions may have innocent explanations or reflect imprecise recollection.
- This prototype is not validated for real criminal investigations.

## Troubleshooting

**Ollama connection failure:** Ensure Ollama is installed and running, then check `ollama list`.

**Model unavailable:** Run `ollama pull gemma3:1b`.

**Missing Python packages:** Activate the environment or invoke `.venv\Scripts\python.exe` directly on Windows, then reinstall `requirements.txt`.

**Invalid model output:** Treat the analysis as failed or flag invalid findings. Never silently replace real inference with mock results.

**Graphviz rendering failure:** Install the Graphviz system application as well as the Python package.

**Invalid model output:** Treat the analysis as failed or flag invalid findings. Never silently replace real inference with mock results.

**Graphviz rendering failure:** Install the Graphviz system application as well as the Python package.
## License

Hackathon prototype. Add a project license before distributing the code publicly.
