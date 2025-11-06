# LangGraph E-commerce Analysis Agent

### TL;DR — Quick Start
1. `git clone <repo> && cd <repo>`  
2. Copy `.env.example` → `.env`, add `GEMINI_API_KEY="your_key_here"`  
3. `pip install -r requirements.txt`  
4. Run: `python -m src.main` *(interactive)* or `python -m src.dev_run_scenarios` *(batch)*  
5. In `src/config.py`, set model (e.g. `gemini-2.5-flash` or pro if api key usage permits) and `INTENT_MODE = "deterministic"` or `"dynamic"`  
6. 📘 **See full architecture:** [docs/architecture.md](docs/architecture.md)
**When to use each:**
- Use **deterministic mode** for standard analytic questions (“top products”, “sales by country”, “monthly trend”).
- Use **dynamic mode** for more open or composite requests that cross categories or logic (“show men’s outerwear sales in US and Canada”, “compare churn between new and returning users”).


## Overview
This project implements a **CLI-based LangGraph agent** that analyzes the public e-commerce dataset **`bigquery-public-data.thelook_ecommerce`** and returns **business-grade insights**.  
The agent turns a free-form question like:

> “which countries bought the most last month?”

into a structured LangGraph pipeline that can run in two modes:

- **Deterministic mode:** safe SQL templates with fixed parameters.  
- **Dynamic mode:** LLM-generated SQL (Gemini JSON plan with guardrails).


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

For a visual overview of the architecture, see [`docs/architecture.md`](docs/architecture.md)

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
### Planning modes (deterministic vs dynamic)

The agent now supports **two planning strategies**, controlled at runtime (e.g. via `INTENT_MODE` in `config.py`):

1. **Deterministic (template-based)**  
   - intent → known template (`q_top_products`, `q_geo_sales`, `q_sales_trend`, `q_customer_segments`)  
   - safe, bounded SQL rendered from `src/sql_templates.py`  
   - best for common reporting questions and for the original assignment requirements.

2. **Dynamic (LLM-generated SQL)**  
   - intent → `dynamic_plan(...)` → Gemini returns a JSON plan with `mode: "sql"` and a full SELECT
   - we run guardrails that detect malicious or injection-like SQL, blocking DML/DDL and unsafe constructs
   - if OK → we set `template_id="raw_sql"` and pass the SQL forward 
   - Additionally, the LLM is prompted with a strict table whitelist (orders, order_items, products, users) and predefined join paths, so even before validation, generation is restricted to the expected schema.
   - if NOT OK → we fall back to the deterministic trend template (`q_sales_trend`) and mark `locked_template=true`.

The rest of the graph (**sqlgen → exec → results → insight → respond**) stays the same in both modes. The only difference is **how** the SQL is decided in `plan_node`.

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
    
    → use the .env.example file with your Google API key and save as .env

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

Then type a question here are a few examples:

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

### At the bottom it prints all scenario outputs together
```bash
python -m src.dev_run_scenarios
```

## Configuration (models, env, BigQuery)

All runtime configuration is centralized in `src/config.py` so you don’t have to change the nodes.

Key things you can control:

1. **LLM model**
   - By default we use a Gemini model (e.g. `gemini-1.5-flash`) for intent, plan, and insights.
   - You can change the model name in `src/config.py` (or via env var if you prefer).
   - If you want to use a Pro / higher-tier model (e.g. `gemini-1.5-pro`), you must set an API key that actually has usage enabled.

2. **API key**
   - The agent expects:
     ```bash
     export GEMINI_API_KEY="YOUR_KEY_HERE"
     ```
   - If the variable is missing, `config.py` should raise/print a clear error so you know why LLM calls fail.

3. **BigQuery credentials**
   - We rely on Google’s Application Default Credentials (ADC):
     ```bash
     gcloud auth application-default login
     ```
   - `src/bq.py` reads those credentials automatically; no hardcoded keys are stored in the repo.

4. **Other tunables**
   - default date windows (30d, 60d, 90d, 365d)
   - default LIMIT for queries
   - these are set in the plan/templates so you can reduce BigQuery costs if needed
- 
## How It Works (Detailed Flow)

1. **User input** → new `AgentState` is created.
2. **intent_node** → Gemini classifies into 4 intents.
3. **plan_node** → either:
   - pick a deterministic SQL template + params, or
   - call the dynamic planner (Gemini) to get guarded raw SQL (with fallback to trend).
4. **sqlgen_node** → if we have a template, render it; if we already have `raw_sql`, just pass it through.
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
- **SQL guardrails** →
  - deterministic path: queries are built from templates;
  - dynamic path: LLM SQL is checked for obviously malicious patterns and otherwise we alert the user for suspicious query.

---

## Performance Notes
Users or tests can switch between deterministic and dynamic planning by setting `INTENT_MODE` in `src/config.py`.

It also:
- understands “last N days” and adjusts the date window,
- detects YOY / “last year” wording and switches trend to a longer window,
- can tag the “Outerwear & Coats” family if those words appear.

- Planning now has 2 costs:
  - deterministic plan is fast (pure Python rules);
  - dynamic plan calls Gemini once and adds ~10–15s in our runs.
- Dynamic is useful for “hard” queries (multi-filters, churnish logic), but we still keep a deterministic fallback (`q_sales_trend`) so the flow never breaks.
- Exec + results + insight timing stays the same for both modes.

---
### Security Considerations

This project runs in two planning modes:

- **Deterministic mode** → SQL is rendered from fixed, local templates → low risk by design.
- **Dynamic mode** → SQL is produced by an LLM → we treat that SQL as untrusted.

For dynamic mode we currently apply **lightweight regex-based guardrails**:

1. We block obviously destructive statements (`insert`, `update`, `delete`, `drop`, `alter`, etc.).
2. We detect multi-statement or suspicious payloads (e.g., `;--`, block comments, or multiple semicolons).
3. When a query looks unsafe, we **alert the user** in the final response instead of executing it.
4. We also constrain the model at the prompt level to only use the four allowed tables (orders, order_items, products, users) and their safe join paths. This ensures that even before validation, the LLM operates within known schema boundaries.
So: **dynamic ≠ free-for-all SQL**, but it’s a *light* guard, intended for this assignment.  
For a production setup, see “Next Improvements” below (server-side allowlist, AST-level validation, per-table limits).


## Design Decisions / Highlights

- Template-first SQL design for safety and determinism.
- Deterministic LangGraph instead of prebuilt agents (explicit nodes).
- Lightweight results node to keep latency low.
- No chart generation (not required by task).
- Benchmarks validate 7 scenarios successfully.
- Logs include Cost logged for each call it uses the LLM
---


## Next Improvements

1. Expand intent classification beyond 4 basic types.
2. Add smarter parameter extraction from user text (e.g. "last quarter", "US vs Canada").
3. Merge plan + insight for trivial queries to reduce cost/time.
4. Add more templates for Refine & cohort analysis.
5. use caching/memory to avoid repeated LLM calls across related queries.
6. Add more tools the agent cal call using functions not just SQL for complex predictions.
 ### And also:
7. Add more tests to improve coverage
8. Add component tests and optimize config keywords for more flexibility.

---

