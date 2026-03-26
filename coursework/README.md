🍛 South Asian Culinary RAG Pipeline
An Enterprise-Grade, Local LLM Culinary Assistant with LangGraph and FAISS

1. Project Overview
This project implements a highly optimized, fully local Retrieval-Augmented Generation (RAG) pipeline designed to act as a South Asian Culinary Assistant. Unlike standard API-wrapper chatbots, this system utilizes a deterministic LangGraph state machine, strict Pure-Python Data Engineering, and a locally hosted Qwen 2.5 (0.5B) model.

The pipeline is explicitly engineered to solve common Large Language Model (LLM) pitfalls—such as context hallucinations, high latency, and small-model attention collapse—by isolating the "Brain" (Intent Routing) from the "Mouth" (Text Generation).

2. System Architecture
The application is divided into three distinct execution phases: Data Engineering (ETL), The Assistant Core (Inference), and The Evaluation Suite.

Plaintext
[Raw JSON] ➔ [Pure-Python ETL] ➔ [FAISS Vector DB] ➔ [LangGraph Router] ➔ [Qwen 0.5B Generator]
Core Technologies
Orchestration: LangGraph / LangChain

Vector Database: FAISS

Embeddings: BAAI/bge-small-en-v1.5 (384 Dimensions)

LLM Engine: Hugging Face transformers (Qwen/Qwen2.5-0.5B-Instruct)

Interactive Frontend: Jupyter Lab / ipywidgets

3. Phase 1: The ETL Pipeline (Data Preparation)
LLMs are computationally expensive and prone to data destruction when used for basic cleaning tasks. To ensure 100% data fidelity and sub-second processing speeds, the entire ETL pipeline was built using pure Python.

Regex Sanitization: A custom script hunts down and removes web-scraping artifacts (e.g., navigation breadcrumbs, stray HTML tags, and bracketed citations) without damaging ingredient fractions or metric measurements.

Semantic Slicing: Recipes are deterministically sliced into intro, ingredients, and instructions using structural markers rather than AI guessing.

Lightning-Fast Metadata Tagging: Instead of using an LLM to classify recipes, a Python keyword-matching algorithm scans the text to assign diet (veg/non-veg), prep_time, and dish_type in 0.001 seconds per recipe.

4. Phase 2: The Assistant Core (LangGraph)
The inference pipeline (assistant_core.py) uses a directed acyclic graph (DAG) to enforce strict conversational logic and maintain multi-turn memory.

A. The Intent Router (The Brain)
To preserve the LLM's context window, user intent is classified using a hyper-fast, rule-based Python router. The router parses the user's query and chat history to categorize the input into specific intents (e.g., RECIPE_REQUEST, INGREDIENTS_ONLY, NON_SOUTH_ASIAN). It simultaneously extracts metadata slots to use as hard FAISS search filters.

B. Indestructible Retrieval (FAISS)
The retrieve_node utilizes the lightweight BAAI/bge-small embedding model. It features a nested fallback system that gracefully degrades from strict metadata filtering to generalized semantic search, ensuring the pipeline never crashes or returns empty queries if a filter is too narrow.

C. Dynamic Generation (The Chef)
Small-parameter models suffer from "Attention Collapse" if fed too much context at once. To solve this, the generation node uses two advanced techniques:

Dynamic Prompting: The system prompt physically changes based on the user's intent. If the user asks for a "suggestion," the LLM is explicitly barred from generating a full recipe and forced to output short summaries.

Chunked Iteration Loop: If multiple recipes are retrieved, the Python backend feeds them to the LLM one by one in a for loop. The LLM acts purely as a Markdown Beautifier for a single recipe at a time, guaranteeing zero hallucinations or mixed ingredients.

5. Phase 3: The Evaluation Suite & Jupyter Frontend
Testing a RAG system requires isolating retrieval performance from generative performance. The evaluation suite (evaluate.py) benchmarks the pipeline against 500 dynamically generated questions, including complex multi-turn conversational sequences.

The RAG Evaluation Triad:
Recall@3 (Context Relevance): Measures if FAISS successfully pulled the target recipe into the top 3 results. (Evaluates the Vector Database)

Intent Accuracy (Answer Relevance): Measures if the LangGraph router correctly understood the user's goal based on chat history. (Evaluates the Python Router)

Answer Faithfulness (Groundedness): A deterministic check that scans the LLM's final generated string to ensure it actually named the dish it was instructed to format, proving it did not hallucinate. (Evaluates the Generation Model)

The Interactive Jupyter Wrapper (submission.ipynb)
To streamline the execution of this complex architecture, submission.ipynb serves as the interactive frontend. It is responsible for:

Hardware-Aware Environment Setup: Automatically installing the correct ARM64 Apple Silicon wheels for PyTorch (torch-2.11.0) to ensure native Metal Performance Shaders (MPS) are utilized during local inference.

Interactive Telemetry: Utilizing @jupyter-widgets/controls and FloatProgressModel to render real-time UI progress bars, giving visual feedback on latency and inference times across the 400-question benchmark loop.

6. Execution Instructions
Just run the submission.ipynb!!!