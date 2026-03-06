🍛 South Asian Culinary Assistant
Hybrid RAG Conversational AI for South Asian Recipes

An intelligent, context-aware conversational AI designed exclusively for South Asian cuisine.
This system uses a Hybrid Retrieval-Augmented Generation (RAG) architecture combining deterministic rule-based reasoning, semantic vector search, and a lightweight local LLM (Qwen2.5-0.5B) to deliver accurate, memory-aware recipe recommendations.

The assistant supports multi-turn conversations, understands ingredient-based queries, and strictly operates within the South Asian culinary domain.

✨ Key Features
🌏 Domain-Constrained AI

The assistant strictly operates within South Asian cuisine.

If users ask for non-South-Asian food, the assistant politely redirects them while suggesting similar South Asian alternatives.

Example:

User: How do I cook pasta?
Assistant: I specialize in South Asian cuisine. Would you like a similar South Asian dish?

🧠 Conversational Memory (Context Merging)

The system maintains short-term conversational memory by merging recent messages.

Example interaction:

User: Surprise me
Assistant: Vegetarian or non-vegetarian?

User: Vegetarian
Assistant: Spicy or mild?

User: Spicy and quick
Assistant: Suggests relevant dishes

This allows the assistant to behave like a natural cooking companion rather than a one-shot chatbot.

🧭 Deterministic Ontology Mapping

Foreign cuisine requests are mapped to South Asian equivalents.

Examples:

Foreign Request	Suggested South Asian Alternative
Pasta	Seviyan
Taco	Kathi Roll
Noodles	Idiyappam

This keeps the assistant domain-focused while still being helpful.

🧩 Smart Slot Extraction

Instead of relying on an LLM for simple tasks, the system extracts structured information using Python logic and regex.

Extracted attributes include:

Dietary preference (veg / non-veg)

Cooking time (quick / slow)

Flavor profile (spicy / sweet / mild)

Dish style (rice-based / curry / snack)

These slots are merged into a descriptive search query such as:

South Asian quick spicy vegetarian paneer recipe

This reduces latency and improves retrieval accuracy.

🧾 Skeleton Prompting

The LLM is guided using structured prompt templates to enforce consistent formatting.

Generated output follows this structure:

Introduction
Ingredients
Instructions

This ensures even a small 0.5B model produces clean and structured responses.

🧹 Custom Data Scraper & Metadata Tagger

A custom BeautifulSoup ingestion pipeline extracts recipe data from Wikibooks and other sources.

The scraper:

Cleans complex Wiki DOM structures

Extracts recipe sections

Tags metadata automatically

Example metadata:

veg / non-veg

quick / slow

spicy / sweet

dish type

This metadata improves FAISS retrieval accuracy.

🏗 System Architecture

The system is divided into three major layers.

Frontend

Angular 18 + Signals

Responsibilities:

Chat interface

Chat state management

Sends complete conversation history to backend

Supports New Chat memory reset

Backend API

Django + Django REST Framework

Responsibilities:

Receives chat payload

Separates latest message from conversation history

Passes structured input to the AI engine

Returns the generated recipe response

AI Engine

LangGraph + FAISS + Transformers

The AI engine acts as a state-machine pipeline responsible for:

intent routing

slot extraction

semantic retrieval

recipe generation

🧠 LangGraph Pipeline

Each user message flows through a structured pipeline.

1️⃣ classify_intent_node — The Gatekeeper

This node uses Python rule-based logic instead of an LLM to classify user intent.

Recognized intents include:

RECIPE_REQUEST

INGREDIENTS_ONLY

VAGUE_REQUEST

NON_SOUTH_ASIAN

ALTERNATIVE_REQUEST

It also merges recent messages to understand conversation continuity.

Example:

User: chicken rice
User: quick spicy

The system merges these into a single structured search query.

2️⃣ retrieve_node — Hybrid Retrieval

Queries the FAISS vector database using embeddings from:

BAAI/bge-small-en-v1.5

The retriever:

Builds a semantic search query

Retrieves top recipe chunks

Groups chunks by dish_name

Ensures the final context includes:

Introduction
Ingredients
Instructions

This guarantees the LLM receives complete recipe context.

3️⃣ generate_recipe_node — The LLM

Powered by:

Qwen/Qwen2.5-0.5B-Instruct

Responsibilities:

Uses retrieved FAISS context

Formats response using Skeleton Prompt

Generates structured Markdown recipe output

Safety rule:

If the requested information is not found in the retrieved context, the model refuses to hallucinate and politely apologizes.

4️⃣ Edge Case Nodes — UX Protection

Special nodes improve conversation flow.

clarify_ingredients_node

If the user enters only ingredients:

milk, sugar

The assistant asks how they want to use them.

clarify_vague_node

If the user gives vague input:

Surprise me

The assistant asks preference questions such as veg/non-veg or spicy/mild.

out_of_bounds_node

Handles non-South-Asian cuisine requests.

Example:

User: Mexican tacos
Assistant: I specialize in South Asian cuisine. Would you like a similar dish?

🚀 Setup & Installation
Prerequisites

Python 3.10+

Node.js

Angular CLI

Minimum 4GB RAM (for FAISS + local LLM)

1️⃣ Environment Setup

Clone the repository

git clone https://github.com/Mithil21/Culinary_RAG_Assistant.git

cd Culinary_RAG_Assistant

Create virtual environment

python -m venv venv
source venv/bin/activate

Windows users:

venv\Scripts\activate

Install dependencies

pip install -r requirements.txt

2️⃣ Build the Vector Database

Navigate to chatbot directory

cd chatbot

Run the ingestion pipeline

python vector_db_setup.py

This step:

Scrapes recipe data

Generates south_asian_corpus.json

Builds the FAISS index

Ensure the FAISS index saves successfully:

vector_store.save_local("./faiss_index")

3️⃣ Run the Backend

From the Django project directory:

python manage.py runserver --noreload

Using --noreload prevents Django from loading the LLM twice in development mode.

4️⃣ Run the Frontend

Open a new terminal:

cd culinary_ui
npm install
ng serve

Open the application in your browser:

http://localhost:4200

🛠 Future Improvements
Markdown Rendering

Integrate ngx-markdown in the Angular frontend to render structured recipes beautifully.

Advanced Metadata Retrieval

Upgrade the FAISS retriever to support metadata filtering using:

SelfQueryRetriever

Expanded Recipe Corpus

Expand the ingestion pipeline with additional recipe sources including:

regional datasets

culinary blogs

structured food datasets

📌 Project Vision

This project demonstrates how small local LLMs combined with structured retrieval, deterministic routing, and domain constraints can produce reliable conversational systems without relying on large cloud-based models.

The architecture highlights how hybrid AI systems combining rule-based logic with retrieval and lightweight LLMs can deliver accurate domain-specific assistants.
