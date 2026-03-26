# South Asian Culinary RAG — Coursework

A Retrieval-Augmented Generation (RAG) pipeline for South Asian recipe recommendations, built with LangGraph, FAISS, and local Hugging Face models.

---

## Pipeline Overview

```
web_scrape.py → enrich_metadata.py → recipe_creator.py → vectorisedata.py → assistant_core.py
                                                                                    ↓
                                                          input_payload_creator.py → evaluate.py
                                                                                    ↓
                                                                               app.py (UI)
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

### 2. Enrich Metadata — `enrich_metadata.py`

Uses `Qwen/Qwen2.5-3B-Instruct` (4-bit quantized) to tag each recipe with structured metadata.

- Classifies `diet` (veg / non-veg), `prep_time` (quick / slow), and `dish_type` (curry / rice / bread / snack / dessert / beverage / pickle-condiment)
- Uses few-shot prompting to enforce strict JSON output
- Saves checkpoints every 25 recipes
- Input: `south_asian_corpus_raw.json`
- Outputs: `south_asian_corpus_enriched.json`

> **Note:** Designed to run on Kaggle GPU. Update `input_file` and `output_file` paths if running locally.

```bash
python enrich_metadata.py
```

---

### 3. Structure Recipes — `recipe_creator.py`

Uses a local LLM (via Ollama) to parse raw recipe text into structured JSON.

- Extracts `intro`, `ingredients`, and `instructions` fields per dish
- Input: `south_asian_corpus_enriched.json`
- Outputs: `vector_ready_corpus.json`

```bash
python recipe_creator.py
```

---

### 4. Vectorise Data — `vectorisedata.py`

Embeds the structured corpus into a FAISS vector database using `BAAI/bge-large-en-v1.5`.

- Packages each recipe as a LangChain `Document` with metadata (diet, prep_time, dish_type)
- Input: `vector_ready_corpus.json`
- Outputs: `faiss_index/`

```bash
python vectorisedata.py
```

---

### 5. Create Input Payload — `input_payload_creator.py`

Generates a benchmark dataset of 500 queries for evaluation.

- Includes hardcoded edge cases (non-South-Asian, vague, ingredients-only)
- Dynamically generates recipe queries from every dish in the corpus using multiple templates
- Generates random metadata-based queries (diet, speed, flavor combinations)
- Input: `vector_ready_corpus.json`
- Outputs: `input_payload.json`

```bash
python input_payload_creator.py
```

---

### 6. Evaluate — `evaluate.py`

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

### 7. Run the Assistant — `app.py`

Streamlit chat interface powered by the LangGraph pipeline in `assistant_core.py`.

- Loads FAISS index and local Qwen models on startup
- Supports multi-turn conversation with memory
- Handles recipe requests, vague queries, ingredient-only inputs, and out-of-domain requests

```bash
streamlit run app.py
```

---

## Models Used

| Role | Model |
|---|---|
| Metadata Enrichment | `NousResearch/Meta-Llama-3-8B-Instruct` |
| Embeddings | `BAAI/bge-large-en-v1.5` |
| Intent Classifier | `Qwen/Qwen2.5-3B` |
| Recipe Generator | `Qwen/Qwen2.5-0.5B-Instruct` |

---

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.10+ and minimum 4GB RAM for local model inference.
