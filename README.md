🍛 South Asian Culinary Assistant (Hybrid RAG AI)
An intelligent, context-aware conversational AI designed exclusively for South Asian cuisine. Built using a Dual-Architecture Hybrid RAG (Retrieval-Augmented Generation) pipeline, this system combines deterministic rule-based routing with semantic vector search and a localized Large Language Model (Qwen2.5-0.5B) to deliver highly accurate, memory-aware recipe recommendations.

✨ Key Features
Domain-Specific Constraints: Strict out-of-bounds handling ensures the AI only discusses South Asian cuisine.

Conversational Memory (Context Merging): The backend merges recent chat history, allowing users to have multi-turn conversations (e.g., answering "Surprise me" -> "Vegetarian" -> "Spicy" -> "Quick").

Deterministic Ontology Mapping: Automatically translates foreign food requests (e.g., "pasta" or "taco") into South Asian equivalents (e.g., "seviyan" or "kathi roll") to keep the user engaged within the domain.

Smart Slot Extraction: Uses Python-native regex and logic to extract dietary preferences, cooking time, and flavor profiles, building highly descriptive search queries without the latency of an LLM.

Skeleton Prompting: Forces the 0.5B LLM to output beautifully formatted Markdown (Introduction, Ingredients, Instructions) by providing structural visual templates.

Custom Data Scraper & Tagger: A bespoke BeautifulSoup pipeline that bypasses complex Wiki DOM structures to extract clean recipe data, auto-tagging them with metadata (veg/non-veg, quick/slow, spicy/sweet) before indexing.

🏗️ System Architecture
The application is split into three main layers:

Frontend (Angular 18+ & Signals): Manages the user interface and chat state. It sends the entire chat history as an array to the backend for context and handles the "New Chat" memory flush.

Backend API (Django & Django REST Framework): Receives the payload, splits the latest question from the history, and passes the context into the AI pipeline.

AI Engine (LangGraph & Transformers): A state-machine-driven pipeline that routes, retrieves, and generates the final response.

🧠 The LangGraph Pipeline (Under the Hood)
The core "Brain" of the assistant is built using LangGraph. When a user sends a message, it flows through a strict state machine:

1. classify_intent_node (The Gatekeeper)
Instead of wasting LLM tokens on classification, this node uses lightning-fast Python logic to analyze the user's input and recent chat history.

Intent Recognition: Classifies the prompt as RECIPE_REQUEST, INGREDIENTS_ONLY, VAGUE_REQUEST, NON_SOUTH_ASIAN, or ALTERNATIVE_REQUEST.

Context Merging: Combines the last two user messages to understand conversational continuity.

Slot Extraction: Grabs keywords like "quick," "vegetarian," or "spicy" to attach to the search query.

2. retrieve_node (Hybrid Search)
If a recipe is needed, the system queries the FAISS Vector Database using the BAAI/bge-small-en-v1.5 embedding model.

It combines the user's question with the extracted slots (e.g., "South Asian quick spicy veg recipe using paneer").

It groups the retrieved chunks by dish_name to ensure the final prompt has a complete Introduction, Ingredients list, and Instructions set.

3. generate_recipe_node (The LLM)
Powered by Qwen/Qwen2.5-0.5B-Instruct.

It takes the perfectly formatted FAISS context and the user's question.

It uses a Skeleton Prompt to guarantee the output is formatted in clean Markdown.

It strictly adheres to the rule: If the answer is not in the context, apologize and refuse to hallucinate.

4. Edge Case Nodes (The UX Protectors)
clarify_ingredients_node: If the user just types "milk, sugar", it asks how they want to use them.

clarify_vague_node: If the user says "Surprise me", it asks them to narrow down their preferences (veg/non-veg, spicy/sweet).

out_of_bounds_node: Politely rejects requests for Mexican, Italian, or other non-South Asian cuisines, offering a local alternative instead.

🚀 Setup & Installation
Prerequisites
Python 3.10+

Node.js & Angular CLI

At least 4GB of RAM (for the 0.5B model + FAISS)

1. Environment Setup
# Clone the repository
git clone https://github.com/Mithil21/Culinary_RAG_Assistant.git
cd Culinary_RAG_Assistant

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install Python dependencies
pip install -r requirements.txt

2. Build the Vector Database
Before starting the server, you must scrape the recipes and build the FAISS index.

# Navigate to the chatbot directory
cd chatbot

# Run the ingestion pipeline (Scrapes data and saves to south_asian_corpus.json)
python vector_db_setup.py 
# Note: Ensure the vector_store.save_local("./faiss_index") runs successfully.

3. Run the Backend (Django)

# From the root Django directory
python manage.py runserver --noreload

(Note: --noreload is highly recommended to prevent Django from loading the LLM into memory twice during development).

4. Run the Frontend (Angular)

# Open a new terminal tab
cd culinary_ui
npm install
ng serve

Navigate to http://localhost:4200 in your browser to start cooking!

🛠️ Future Scope
Markdown Parsing: Implement ngx-markdown on the Angular frontend to beautifully render the LLM's structured output.

Dynamic Metadata Filtering: Upgrade the FAISS retriever from semantic keyword injection to true SelfQueryRetriever metadata filtering.

Expanded Corpus: Add more diverse South Asian recipe sources to the ingestion pipeline.
