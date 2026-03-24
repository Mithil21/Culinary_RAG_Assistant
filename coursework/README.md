# South Asian Culinary RAG — Coursework

A Retrieval-Augmented Generation (RAG) pipeline for South Asian recipe recommendations, built with LangGraph, FAISS, and local Hugging Face models.

---

## Pipeline Overview

```
web_scrape.py → recipe_creator.py → vectorisedata.py → assistant_core.py
                                                              ↓
                                                         app.py (UI)
                                                         evaluate.py (benchmarking)
```

---

## Step-by-Step

### 1. Scrape Data — `web_scrape.py`

Scrapes South Asian recipe data from Wikibooks and Wikipedia using BeautifulSoup.

- Extracts introductions, ingredients, and instructions per dish
- Deduplicates content using fuzzy string matching
- Outputs: `south_asian_corpus_raw.json`

```bash
python web_scrape.py
```

---

### 2. Add Metadata — `recipe_creator.py`

Uses a local LLM (via Ollama) to parse raw recipe text into structured JSON and enrich metadata.

- Extracts `intro`, `ingredients`, and `instructions` fields
- Input: `south_asian_corpus_enriched.json`
- Outputs: `vector_ready_corpus.json`

```bash
python recipe_creator.py
```

---

### 3. Vectorise Data — `vectorisedata.py`

Embeds the structured corpus into a FAISS vector database using `BAAI/bge-large-en-v1.5`.

- Packages each recipe as a LangChain `Document` with metadata (diet, prep_time, dish_type)
- Input: `vector_ready_corpus.json`
- Outputs: `faiss_index/`

```bash
python vectorisedata.py
```

---

### 4. Run the Assistant — `app.py`

Streamlit chat interface powered by the LangGraph pipeline in `assistant_core.py`.

- Loads FAISS index and local Qwen models on startup
- Supports multi-turn conversation with memory
- Handles recipe requests, vague queries, ingredient-only inputs, and out-of-domain requests

```bash
streamlit run app.py
```

---

### 5. Evaluate — `evaluate.py`

Benchmarks the full RAG pipeline against `benchmark_dataset.json`.

Metrics computed:
- **Recall@3** — fraction of expected dishes found in top-3 retrieved results
- **Intent Accuracy** — whether predicted intent matches expected intent
- **Latency** — wall-clock time per query

Outputs: `output_payload_sample.json`

```bash
python evaluate.py
```

---

## Models Used

| Role | Model |
|---|---|
| Embeddings | `BAAI/bge-large-en-v1.5` |
| Intent Classifier | `Qwen/Qwen2.5-3B` |
| Recipe Generator | `Qwen/Qwen2.5-0.5B-Instruct` |

---

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.10+ and minimum 4GB RAM for local model inference.
