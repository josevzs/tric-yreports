# TricountReport

A local webapp for generating expense reports from Tricount data, with AI-powered auto-categorization.

## Features

- **Load data** from a Tricount `.xlsx` export or directly from the Tricount API (just the registry ID)
- **AI auto-categorization** with Claude, OpenAI, or local Ollama
- **Manual review & correction** with confidence badges
- **Report generation** in Markdown and PDF with totals by category

## Prerequisites

- **Python 3.14** via the `tricount` conda environment (`conda env create -n tricount`)
- **Node.js 18+** and npm

## Setup

### Backend

```bash
# Activate the tricount conda environment
conda activate tricount

# Install dependencies
pip install -r backend/requirements.txt

# Start the API server
cd "TricountReport"
python -m uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

## Configuration

On first run, click the **⚙️ Settings** button in the top-right corner to configure your AI provider:

| Provider | What you need |
|----------|---------------|
| **Ollama (local)** | [Ollama](https://ollama.com) running + a model pulled (e.g. `ollama pull llama3.2`) |
| **Claude** | Anthropic API key from [console.anthropic.com](https://console.anthropic.com) |
| **OpenAI** | OpenAI API key from [platform.openai.com](https://platform.openai.com) |

Settings are saved in `settings.json` (gitignored).

## Usage

1. **Load Data** — Upload `data.xlsx` or enter a Tricount registry ID
2. **AI Categorize** — Click "Auto-categorize with AI" to get suggestions
3. **Review & Edit** — Correct any wrong categories in the table
4. **Generate Report** — Set a trip name and download as `.md` or `.pdf`

## Categories

| Category | Description |
|----------|-------------|
| Estancias | Hotels, Airbnb, accommodation |
| Alquiler de coches | Car rental |
| Comidas y cenas | Restaurants, dinners, lunches |
| Desayunos y cafés | Breakfast, coffee, bakeries |
| Entradas | Museums, tours, entrance fees |
| Gasolina | Fuel, gas stations |
| Peajes | Tolls, highway fees |
| Trenes | Trains |
| Autobuses | Buses, metro |
| Barcos y ferrys | Ferries, boats |
| Aviones | Flights |
| Gastos personales | Personal items, souvenirs |
| Supermercado | Supermarkets, groceries |
| Farmacia | Pharmacy |
| Parking | Car parks |
| Otros | Other / unclassified |

The AI can also propose additional categories when needed.
