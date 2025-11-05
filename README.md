# LangGraph E-commerce Analysis Agent (Opsfleet Assignment)

## Overview
This project implements a **CLI-based LangGraph agent** that analyzes the public e-commerce dataset **`bigquery-public-data.thelook_ecommerce`** and returns **business-grade insights**.  
The agent turns a free-form question like:

> “which countries bought the most last month?”

into a deterministic pipeline:

1. understand the intent (geo / product / trend / segment),
2. pick a safe SQL template,
3. run the query on BigQuery,
4. do light Python post-processing,
5. ask Gemini to turn numbers into insights/actions/follow-ups,
6. print a clean CLI response.

The goal is to show *agentic structure* (LangGraph), *safe data access* (template SQL), and *business output* (insight bullets) — exactly as the assignment asks.

---

## Features
- ✅ **LangGraph-based flow**: explicit nodes and edges, no black-box agent
- ✅ **BigQuery integration** with the required tables: `orders`, `order_items`, `products`, `users`
- ✅ **4 analysis families**:
  - Product performance (top revenue products)
  - Geographic sales (by country)
  - Customer/market segments
  - Sales trends / seasonality
- ✅ **Gemini integration** (intent + plan + insights)
- ✅ **CLI runner** for interactive testing
- ✅ **Tests** for schema, templates, and nodes (PyTest)

---

## Architecture (high level)
The agent is built as a **deterministic LangGraph**:

```mermaid
flowchart TD
    A[CLI / User Query] --> B[intent_node]
    B --> C[plan_node]
    C --> D[sqlgen_node]
    D --> E[exec_node (BigQuery)]
    E --> F[results_node]
    F --> G[insight_node (Gemini)]
    G --> H[respond_node]
```

**Node roles:**

- **intent_node** – classify the question into one of: `product`, `geo`, `trend`, `segment`
- **plan_node** – choose the right SQL template + time window + dimensions (e.g. last 30 days, country level)
- **sqlgen_node** – fill the selected template with parameters (no free-form SQL)
- **exec_node** – run against BigQuery and return a preview + rowcount
- **results_node** – compute lightweight aggregates in Python (top-k, shares, totals)
- **insight_node** – ask Gemini to turn raw numbers into business insights, recommended actions, and follow-up questions
- **respond_node** – format a CLI-friendly answer (< 2000 chars)

---

## Dataset
We use the dataset required in the assignment:

- **Project / dataset**: `bigquery-public-data.thelook_ecommerce`
- **Tables used**:
  - `orders` – customer order information
  - `order_items` – items per order
  - `products` – product catalog
  - `users` – customer demographics

A small **schema registry** is hardcoded in `src/schema.py` to describe these tables, how they join, and which columns are safe to select. This keeps SQL generation predictable.

---

## Repository Structure

```text
.
├── README.md
├── requirements.txt
├── docs/
│   └── architecture.md
├── src/
│   ├── main.py
│   ├── config.py
│   ├── bq.py
│   ├── schema.py
│   ├── sql_templates.py
│   ├── state.py
│   ├── graph.py
│   └── nodes/
│       ├── intent.py
│       ├── plan.py
│       ├── sqlgen.py
│       ├── exec.py
│       ├── results.py
│       ├── insight.py
│       └── respond.py
└── tests/
    ├── test_schema.py
    ├── test_sql_templates.py
    ├── test_nodes.py
    └── ...
```

---

## Prerequisites

1. **Python**: 3.10+ recommended  
2. **GCP auth** (for BigQuery):
   ```bash
   gcloud auth application-default login
   ```
   This sets up **ADC (Application Default Credentials)** which the BigQuery client in `src/bq.py` will use.
3. **Gemini API key** (used in intent / plan / insight nodes):
   ```bash
   export GEMINI_API_KEY="YOUR_KEY_HERE"
   ```
   or on Windows:
   ```powershell
   setx GEMINI_API_KEY "YOUR_KEY_HERE"
   ```

---

## Installation

```bash
git clone <your-repo-url>
cd <your-repo>
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running the Agent (CLI)

Run:

```bash
python -m src.main
```

Then type one of these:

- `show me the top revenue products from the last 30 days`
- `which countries bought the most last month?`
- `find high value customers and tell me what they are buying`
- `show sales trend for outerwear and coats over the past 90 days`

The agent will print:

- **Insights**
- **Recommended actions**
- **Follow-up questions**

---
## Running predefined scenarios

Besides the interactive CLI, you can run a small script that feeds the agent with ready-made queries (the same ones we used for benchmark runs).

```bash
python -m src.dev_scenarios
```

## How It Works (Detailed Flow)

1. **User input** → new `AgentState` is created.
2. **intent_node** → Gemini classifies into 4 intents.
3. **plan_node** → selects SQL template + params.
4. **sqlgen_node** → renders SQL safely.
5. **exec_node** → runs BigQuery and returns preview.
6. **results_node** → computes aggregates (totals, shares).
7. **insight_node** → Gemini transforms data into insights/actions/follow-ups.
8. **respond_node** → prints CLI text.

---

## Tests

To run the unit tests:

```bash
pytest -v
```

To include coverage details:

```bash
pytest --cov=src --cov-report=term-missing -v
```

Typical tests:
- schema coverage for 4 tables
- SQL template rendering
- node execution path correctness
- safe defaults and validation

---

## Error Handling & Fallbacks

- **BigQuery errors** → handled with try/except to avoid crashes and print friendly messages.
- **LLM failures** → partial data can still flow to response node.
- **SQL guardrails** → queries are built from templates, not arbitrary text.

---

## Performance Notes

From benchmark runs (~40s per full scenario):
- ~80% time in LLM calls (plan + insight)
- BigQuery queries are lightweight due to date filters & LIMIT
- Architecture prioritizes correctness and explainability

---

## Design Decisions / Highlights

- Template-first SQL design for safety and determinism.
- Deterministic LangGraph instead of prebuilt agents (explicit nodes).
- Lightweight results node to keep latency low.
- No chart generation (not required by task).
- Benchmarks validate 7 scenarios successfully.

---

## Next Improvements

1. Expand intent classification beyond 4 basic types.
2. Add smarter parameter extraction from user text (e.g. "last quarter", "US vs Canada").
3. Merge plan + insight for trivial queries to reduce cost/time.
4. Add more templates for RFM & cohort analysis.
5. Standardize `state.error` and CLI display for graceful failures.
6. Add `src/sanity.py` to check credentials and env automatically.

---

## License / Submission
This repository includes source code, documentation (README + architecture diagram), and benchmark validation for submission to Opsfleet.

