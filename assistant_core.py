# Author: Mithil Baria

import json
import re
import torch
import traceback
from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# ==========================================
# 1. INITIALIZE MODELS & DATABASE
# ==========================================
print("Loading FAISS Database...")
device = "cuda" if torch.cuda.is_available() else "cpu"
bge_embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-large-en-v1.5",
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )

vector_store = FAISS.load_local(
    "./faiss_index",
    bge_embeddings,
    allow_dangerous_deserialization=True,
)

# Use retriever for normal semantic search
# retriever = vector_store.as_retriever(search_kwargs={"k": 8})

# --- THE FIX IS HERE ---
# Determine local hardware
if torch.cuda.is_available():
    device = "cuda"
elif torch.backends.mps.is_available():
    device = "mps" # For Apple Silicon Macs
else:
    device = "cpu"

print(f"Loading Qwen2.5-0.5B-Instruct Model on {device}...")
model_id = "Qwen/Qwen2.5-0.5B-Instruct"

# Load the model strictly ONCE to save memory
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    # Use float16 on GPU/Mac for speed, float32 on CPU for stability
    torch_dtype=torch.float16 if device != "cpu" else torch.float32
).to(device)

print("Setting up Rewriter & Generator Pipelines...")

# Pipeline 1: The Brain (Rewriter) - Uses the loaded model
rewriter_pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=300,
    max_length=None,     # <--- ADD THIS to kill the warning
    do_sample=False,      # <--- ADD THIS because temperature is set
    # temperature=0.1,   
    repetition_penalty=1.1,
    return_full_text=False,
    pad_token_id=tokenizer.eos_token_id
)
rewriter_llm = HuggingFacePipeline(pipeline=rewriter_pipe)

# Pipeline 2: The Chef (Generator) - Uses the exact SAME loaded model
pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=800,
    max_length=None,     # <--- ADD THIS
    do_sample=False,      # <--- ADD THIS
    # temperature=0.1,
    repetition_penalty=1.1,
    return_full_text=False,
    pad_token_id=tokenizer.eos_token_id
)
llm = HuggingFacePipeline(pipeline=pipe)

# ==========================================
# 2. GRAPH STATE
# ==========================================
class GraphState(TypedDict, total=False):
    question: str
    chat_history: list
    intent: str
    extracted: Dict[str, Any]
    context: List[str]
    grouped_context: Dict[str, Dict[str, str]]
    selected_dishes: List[str]
    raw_chunks: Dict[str, List[Dict[str, str]]] # <-- Added dict tracking for raw chunks
    generation: str

# ==========================================
# 3. HELPERS
# ==========================================
NON_SOUTH_ASIAN_KEYWORDS = {
    "mexican", "italian", "chinese", "thai", "japanese", "korean",
    "french", "american", "continental", "spanish", "turkish",
    "pizza", "pasta", "taco", "sushi", "ramen", "burger"
}

ALTERNATIVE_MAP = {
    "pasta": "vermicelli seviyan noodles",
    "pizza": "naan uttapam flatbread roti",
    "taco": "dosa chapati roll kathi",
    "burger": "vada pav dabeli bonda",
    "sushi": "fish rice",
    "mexican": "spicy rajma beans rice",
    "italian": "tomato garlic gravy paneer",
    "chinese": "fried rice spicy chicken",
    "ramen": "spicy soup rasam",
}

CHAT_REPLY_PATTERNS = r"^\s*(yes|yeah|yep|ok|okay|sure|go ahead|continue|quick one|easy one|slow one)\s*$"

SUGGESTION_PATTERNS = [
    r"\bwhat can i make\b",
    r"\bsuggest\b",
    r"\brecommend\b",
    r"\bidea\b",
    r"\bwhat should i cook\b",
    r"\bwhat should i eat\b",
]

RECIPE_PATTERNS = [
    r"\bhow to make\b",
    r"\bhow do i make\b",
    r"\brecipe\b",
    r"\bcook\b",
    r"\bprepare\b",
]

INGREDIENT_HINTS = [
    "i have", "with", "using"
]

VAGUE_PATTERNS = [
    r"\bsomething tasty\b",
    r"\bsomething spicy\b",
    r"\bsomething easy\b",
    r"\bgive me food\b",
    r"\bsurprise me\b",
]

COMMON_INGREDIENT_WORDS = {
    "rice", "lentils", "dal", "milk", "sugar", "salt", "turmeric", "cumin",
    "chili", "chiles", "cardamom", "cloves", "cinnamon", "ginger", "garlic",
    "onion", "onions", "tomato", "tomatoes", "paneer", "chicken", "fish",
    "mutton", "egg", "eggs", "peas", "chickpeas", "butter", "ghee", "curd",
    "yogurt", "yoghurt", "coriander", "bay leaves", "flour", "roti"
}


def safe_strip_generation(raw: str) -> str:
    if not isinstance(raw, str):
        raw = str(raw)
    return raw.replace("<|im_end|>", "").replace("<|im_start|>assistant", "").strip()


def looks_like_ingredient_list(question: str) -> bool:
    q = question.lower().strip()

    # comma-separated ingredient-like input
    if "," in q:
        tokens = [t.strip() for t in q.split(",") if t.strip()]
        if len(tokens) >= 2:
            return True

    # "i have x y z" pattern
    if any(hint in q for hint in INGREDIENT_HINTS):
        return True

    # very short input full of ingredient words
    words = set(re.findall(r"[a-zA-Z]+", q))
    overlap = words.intersection(COMMON_INGREDIENT_WORDS)
    if len(overlap) >= 2 and len(words) <= 8:
        return True

    return False


def rule_based_intent(question: str) -> str:
    q = question.lower().strip()

    if any(word in q for word in NON_SOUTH_ASIAN_KEYWORDS):
        return "NON_SOUTH_ASIAN"

    if re.fullmatch(CHAT_REPLY_PATTERNS, q):
        return "CHAT_REPLY"

    # --- THE FIX: Move these explicit requests ABOVE the ingredient check ---
    if any(re.search(p, q) for p in RECIPE_PATTERNS):
        return "RECIPE_REQUEST"

    if any(re.search(p, q) for p in SUGGESTION_PATTERNS):
        return "SUGGESTION_REQUEST"
        
    if any(re.search(p, q) for p in VAGUE_PATTERNS):
        return "VAGUE_REQUEST"

    # --- NOW run the ingredient check ---
    if looks_like_ingredient_list(q):
        return "INGREDIENTS_ONLY"

    # short dish-like query such as "biryani"
    if len(q.split()) <= 4:
        return "DISH_QUERY"

    return "RECIPE_REQUEST"


def extract_basic_slots(question: str) -> Dict[str, Any]:
    q = question.lower()

    time_preference = ""
    if "quick" in q or "fast" in q or "easy" in q:
        time_preference = "quick"
    elif "slow" in q or "elaborate" in q or "festive" in q:
        time_preference = "elaborate"

    diet_preference = ""
    if "vegetarian" in q or re.search(r"\bveg\b", q):
        diet_preference = "veg"
    elif "non veg" in q or "non-veg" in q or any(x in q for x in ["chicken", "fish", "mutton"]):
        diet_preference = "non_veg"
    elif "egg" in q:
        diet_preference = "egg"
    
    flavor_preference = ""
    if "spicy" in q or "hot" in q or "chili" in q or "masala" in q:
        flavor_preference = "spicy"
    elif "sweet" in q or "dessert" in q or "mithai" in q:
        flavor_preference = "sweet"

    # --- FIX 1: Safely extract ingredients using word boundaries ---
    ingredients = []
    words = re.findall(r"[a-zA-Z]+", q)
    for w in words:
        if w in COMMON_INGREDIENT_WORDS and w not in ingredients:
            ingredients.append(w)

    return {
        "ingredients": ingredients,
        "time_preference": time_preference,
        "diet_preference": diet_preference,
        "flavor_preference": flavor_preference,
        "cuisine_scope": "south_asian",
    }



# def build_retrieval_query(question: str, intent: str, extracted: Dict[str, Any]) -> str:
#     ingredients = extracted.get("ingredients", [])
#     time_preference = extracted.get("time_preference", "")
#     diet = extracted.get("diet_preference", "")
#     flavor = extracted.get("flavor_preference", "")

#     # Clean up modifiers
#     modifiers = f"{time_preference} {flavor} {diet}".strip()
#     modifiers = re.sub(r'\s+', ' ', modifiers) 
    
#     ingredient_str = " ".join(ingredients) if ingredients else ""

#     # Strip instructional filler words (added 'based' to clean up 'rice based')
#     clean_question = re.sub(r"(?i)\b(how to make|how do i make|recipe for|recipe|cook|prepare|based)\b", "", question).strip()
#     if not clean_question:
#         clean_question = question

#     if intent == "ALTERNATIVE_REQUEST":
#         alt_search = extracted.get("alternative_search", "")
#         return f"{modifiers} {alt_search}".strip()

#     # --- THE FIX: Highly Concentrated Semantic Query ---
#     # We completely remove "South Asian recipe using" because those generic words 
#     # dilute the embedding vector away from the specific ingredients!
#     raw_query = f"{modifiers} {ingredient_str} {clean_question}".strip()
    
#     # Remove duplicate words (like 'rice rice') while keeping the exact order
#     final_query = " ".join(dict.fromkeys(raw_query.split()))

#     if not final_query:
#         final_query = question

#     return final_query

def build_retrieval_query(question: str, intent: str, extracted: Dict[str, Any]) -> str:
    ingredients = " ".join(extracted.get("ingredients", []))
    modifiers = f"{extracted.get('time_preference', '')} {extracted.get('flavor_preference', '')} {extracted.get('diet_preference', '')}".strip()
    if intent == "ALTERNATIVE_REQUEST":
        alt_search = extracted.get("alternative_search", "")
        return f"South Asian {modifiers} recipe {alt_search}"
    if ingredients:
        return f"South Asian {modifiers} recipe using {ingredients} {question}".strip()
    return f"South Asian {modifiers} recipe {question}".strip()


def group_docs_by_dish(docs) -> Dict[str, Dict[str, str]]:
    grouped: Dict[str, Dict[str, str]] = {}

    for d in docs:
        metadata = d.metadata or {}
        dish_name = metadata.get("dish_name", metadata.get("title", "Unknown Dish")).strip()
        content_type = metadata.get("content_type", "Unknown").strip().lower()
        text = d.page_content.strip()

        if dish_name not in grouped:
            grouped[dish_name] = {
                "Introduction": "",
                "Ingredients": "",
                "Instructions": "",
                "source_url": metadata.get("source_url", ""),
            }

        if content_type == "introduction":
            grouped[dish_name]["Introduction"] = text
        elif content_type == "ingredients":
            grouped[dish_name]["Ingredients"] = text
        elif content_type == "instructions":
            grouped[dish_name]["Instructions"] = text
        else:
            # fallback
            if not grouped[dish_name]["Introduction"]:
                grouped[dish_name]["Introduction"] = text

    return grouped


import re

def score_grouped_dishes(grouped: Dict[str, Dict[str, str]], structured_chunks: Dict[str, list], extracted_slots: Dict[str, Any]) -> List[str]:
    """
    Rank dishes using Hybrid Scoring: Best L2 Distance + Exact Keyword Bonuses.
    Lower final score = Better match!
    """
    user_ingredients = extracted_slots.get("ingredients", [])
    scored = []

    for dish, parts in grouped.items():
        dish_chunks = structured_chunks.get(dish, [])
        if not dish_chunks:
            continue
            
        # 1. Take the BEST (lowest) score from the chunks. Do NOT average!
        best_score = min(c.get("score", 1.0) for c in dish_chunks)
        
        # 2. Combine the text to search for exact ingredient matches
        dish_name_lower = dish.lower()
        recipe_text_lower = (parts.get("Introduction", "") + " " + parts.get("Ingredients", "")).lower()

        # 3. Apply Keyword Bonuses to force exact matches to the top
        bonus = 0.0
        for ing in user_ingredients:
            ing_lower = ing.lower()
            
            # Massive bonus if the ingredient is literally in the title (e.g., "Egg" in "Egg Rice")
            if re.search(rf"\b{ing_lower}\b", dish_name_lower):
                bonus += 0.15
            # Moderate bonus if the ingredient is explicitly listed in the recipe text
            elif re.search(rf"\b{ing_lower}\b", recipe_text_lower):
                bonus += 0.05

        final_score = best_score - bonus
        scored.append((dish, round(final_score, 4)))

    # 4. Sort by final score ASCENDING (Lowest score = Best Match)
    scored.sort(key=lambda x: x[1])

    print(f"--- ROBUST RANKINGS (Lower is better): {scored} ---")

    return [dish for dish, _ in scored]


def serialize_grouped_context_for_prompt(grouped: Dict[str, Dict[str, str]], selected_dishes: List[str]) -> str:
    blocks = []

    for dish in selected_dishes:
        parts = grouped[dish]
        block = [
            f"Dish: {dish}",
            f"Introduction: {parts.get('Introduction', '')}",
            f"Ingredients: {parts.get('Ingredients', '')}",
            f"Instructions: {parts.get('Instructions', '')}",
        ]
        blocks.append("\n".join(block))

    return "\n\n---\n\n".join(blocks)


# ==========================================
# 4. NODES
# ==========================================
def classify_intent_node(state: GraphState):
    question = state["question"].strip()
    history = state.get("chat_history", [])

    # 1. Standard intent based on the immediate question
    intent = rule_based_intent(question)
    
    recent_user_msgs = [m['content'] for m in history if m.get('role') == 'user'][-2:]
    combined_context = " ".join(recent_user_msgs + [question])
    
    extracted = extract_basic_slots(combined_context)

    # --- THE FIX: CATCHING THE "YES" FOR ALTERNATIVES ---
    if intent == "CHAT_REPLY" and len(history) >= 2:
        last_bot_msg = history[-1].get("content", "")
        
        # If the bot just offered an alternative, and the user said yes!
        if "South Asian alternative" in last_bot_msg:
            intent = "ALTERNATIVE_REQUEST"
            last_user_msg = history[-2].get("content", "").lower()
            
            # Map the foreign food to South Asian keywords
            alt_keywords = []
            for foreign_dish, sa_alts in ALTERNATIVE_MAP.items():
                if foreign_dish in last_user_msg:
                    alt_keywords.append(sa_alts)
            
            extracted["alternative_search"] = " ".join(alt_keywords) if alt_keywords else "popular snack"
            
            # Rewrite the state question so the LLM doesn't just see the word "yes"
            question = f"What is a good South Asian alternative to {last_user_msg}?"

    print(f"--- CLASSIFIER: {intent} ---")
    print(f"--- EXTRACTED SLOTS: {extracted} ---")
    return {
        "intent": intent,
        "extracted": extracted,
        "question": question # Updates the graph state with the rewritten question!
    }


def retrieve_node(state: GraphState):
    question = state["question"]
    intent = state["intent"]
    extracted = state.get("extracted", {})

    retrieval_query = build_retrieval_query(question, intent, extracted)
    print(f"--- RETRIEVING FROM FAISS: {retrieval_query} ---")

    # 1. Similarity Search with Score
    raw_docs_with_scores = vector_store.similarity_search_with_score(retrieval_query, k=15)
    print(raw_docs_with_scores)

    # 2. Filter by threshold AND KEEP THE SCORE TUPLE
    filtered_docs_with_scores = [(doc, score) for doc, score in raw_docs_with_scores if score >= 0.30 and score <= 0.60]
    
    # 3. Bulletproof Fallback
    # if len(filtered_docs_with_scores) < 3:
    #     docs_with_scores = raw_docs_with_scores[:6]
    # else:
    #     docs_with_scores = filtered_docs_with_scores

    docs_with_scores = filtered_docs_with_scores

    print(f'=========DOCS RETRIEVED ({len(docs_with_scores)} chunks)=========')

    # 4. Extract data and inject the exact L2 score!
    structured_chunks = {}
    just_docs = [] # We need a clean list of just docs for your grouping function
    
    for i, (d, score) in enumerate(docs_with_scores):
        just_docs.append(d) # Save the document for the grouping helper
        
        meta = d.metadata or {}
        dish_title = str(meta.get("title", meta.get("dish_name", "Unknown Dish"))).strip()
        chunk_type = str(meta.get("content_type", "content")).lower()
        db_chunk_id = str(meta.get("db_chunk_id", f"chunk_{i+1}"))
        
        if dish_title not in structured_chunks:
            structured_chunks[dish_title] = []
            
        structured_chunks[dish_title].append({
            "chunk_id": db_chunk_id,
            "type": chunk_type,
            "score": round(float(score), 4), # <--- SCORE IS SAVED HERE!
            "text": d.page_content.strip()
        })

    # Pass the clean list of docs to your grouping helper
    grouped = group_docs_by_dish(just_docs)
    ranked_dishes = score_grouped_dishes(grouped, structured_chunks, extracted)

    # --- FETCH ONLY 1 FOOD DISH ---
    selected_dishes = ranked_dishes[:1]

    raw_context = []
    for dish in selected_dishes:
        parts = grouped[dish]
        raw_context.append(
            f"Dish: {dish}\n"
            f"Introduction: {parts.get('Introduction', '')}\n"
            f"Ingredients: {parts.get('Ingredients', '')}\n"
            f"Instructions: {parts.get('Instructions', '')}"
        )

    print(f"--- DISH CANDIDATE: {selected_dishes} ---")

    # Clean the JSON output so it only shows the chunks for the winning dish
    final_chunks = {dish: structured_chunks[dish] for dish in selected_dishes if dish in structured_chunks}

    return {
        "context": raw_context,
        "grouped_context": grouped,
        "selected_dishes": selected_dishes,
        "raw_chunks": final_chunks
    }


def clarify_ingredients_node(state: GraphState):
    extracted = state.get("extracted", {})
    ingredients = extracted.get("ingredients", [])

    print("--- GENERATING INGREDIENT CLARIFICATION ---")

    if ingredients:
        ingredient_text = ", ".join(ingredients)
        response = (
            f"I can work with these ingredients: **{ingredient_text}**.\n\n"
            f"Do you want a **quick South Asian meal**, a **curry**, or something **rice-based**?"
        )
    else:
        response = (
            "I can suggest a South Asian dish from those ingredients.\n\n"
            "Do you want something **quick**, **spicy**, **vegetarian**, or **non-vegetarian**?"
        )

    return {"generation": response}


def clarify_vague_node(state: GraphState):
    print("--- GENERATING VAGUE CLARIFICATION ---")
    response = (
        "I can help with South Asian dishes.\n\n"
        "Tell me one of these so I can narrow it down:\n"
        "- **vegetarian** or **non-vegetarian**\n"
        "- **quick** or **elaborate**\n"
        "- **rice-based**, **bread-based**, or **curry**"
    )
    return {"generation": response}


def out_of_bounds_node(state: GraphState):
    print("--- GENERATING OUT OF BOUNDS RESPONSE ---")
    response = (
        "My database is focused on **South Asian cuisine** only.\n\n"
        "If you want, I can still suggest a **similar South Asian alternative**."
    )
    return {"generation": response}


def generate_recipe_node(state: GraphState):
    question = state["question"]
    intent = state["intent"]
    grouped = state.get("grouped_context", {})
    selected_dishes = state.get("selected_dishes", [])

    if not grouped or not selected_dishes:
        return {"generation": "I'm sorry, I don't have a recipe for that in my database."}

    print(f"--- GENERATING FINAL RECIPES ({len(selected_dishes)} found) ---")
    
    formatted_chunks = []

    # Run a for loop to beautify each recipe individually
    for dish in selected_dishes:
        parts = grouped[dish]
        
        # 1. Build the raw text for just this single dish
        raw_text = f"Dish: {dish}\n\n"
        if parts.get('Introduction'): 
            raw_text += f"Introduction:\n{parts['Introduction']}\n\n"
        if parts.get('Ingredients'): 
            raw_text += f"Ingredients:\n{parts['Ingredients']}\n\n"
        if parts.get('Instructions'): 
            raw_text += f"Instructions:\n{parts['Instructions']}\n"

        # 2. Build the strict ChatML prompt for the Qwen model
        # 2. Build the LangChain Prompt Template
        prompt = PromptTemplate(
            template="""<|im_start|>system
You are a precise Markdown Formatting Assistant.
Your ONLY job is to take the provided recipe data and format it into beautiful Markdown.
- Use bolding for headings (like **Introduction**, **Ingredients**, **Instructions**).
- Use bullet points for ingredients and numbered lists for instructions.
- Do NOT invent, guess, or leave out ANY details from the provided text.
- Output ONLY the formatted recipe.<|im_end|>
<|im_start|>user
Recipe Data to format:
{raw_text}<|im_end|>
<|im_start|>assistant
""",
            input_variables=["raw_text"]
        )
        
        # 3. Call the LLM safely via LangChain
        chain = prompt | llm
        
        # Pass the raw_text variable into the prompt template dynamically
        raw_generation = chain.invoke({"raw_text": raw_text})
        
        # Strip the ChatML tags
        clean_generation = safe_strip_generation(raw_generation)
        
        # 4. Save the beautified recipe (or fallback to raw text if the LLM fails)
        if clean_generation:
            formatted_chunks.append(clean_generation)
        else:
            formatted_chunks.append(raw_text)

    # Join all the individually formatted recipes together with a clean divider
    final_answer = "Here is what I found for you:\n\n" + "\n\n---\n\n".join(formatted_chunks)

    return {"generation": final_answer}

# ==========================================
# 5. ROUTING LOGIC
# ==========================================
def route_logic(state: GraphState) -> str:
    intent = state["intent"]

    if intent == "NON_SOUTH_ASIAN":
        return "out_of_bounds"

    if intent == "INGREDIENTS_ONLY":
        return "clarify"

    if intent == "VAGUE_REQUEST":
        return "clarify_vague"

    # Added ALTERNATIVE_REQUEST here so it goes to FAISS
    if intent in {"RECIPE_REQUEST", "DISH_QUERY", "SUGGESTION_REQUEST", "CHAT_REPLY", "ALTERNATIVE_REQUEST"}:
        return "retrieve"

    return "retrieve"


def rewrite_query_node(state: GraphState):
    """
    Uses the 1.5B 'Brain' to read the chat history and rewrite vague
    user messages into strong standalone retrieval queries.
    """
    question = state["question"].strip()
    history = state.get("chat_history", [])

    if not history:
        return {"question": question}

    print("--- REWRITING QUERY USING 1.5B BRAIN ---")

    recent_history = "\n".join(
        [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history[-6:]]
    )

    prompt = PromptTemplate(
        template="""<|im_start|>system
You are a search-query rewriting assistant for a South Asian culinary chatbot.

Your task:
Rewrite the user's NEW MESSAGE into ONE standalone search query that can be used for recipe retrieval.

Rules:
1. Default to South Asian cuisine unless the user explicitly asked for a non-South-Asian cuisine.
2. Use the Chat History to resolve vague follow-ups like:
   - "yes"
   - "okay"
   - "quick"
   - "spicy"
   - "curry"
   - "rice-based"
   - "rice based"
   - "veg"
   - "vegetarian"
   - "non veg"
   - "non vegetarian"
3. Do NOT answer the user.
4. Output ONLY the rewritten search query text.
5. Do NOT include explanations, labels, bullets, quotes, or extra text.
6. If the new message is already clear and standalone, return it with only minimal cleanup.
7. If the user is accepting a South Asian alternative after rejecting a non-South-Asian dish, rewrite toward a similar South Asian dish search.
8. If the user adds preferences, merge them with the latest relevant food request from history.
9. Keep the rewritten query short, natural, and retrieval-friendly.

Good examples:

History:
user: surprise me
assistant: I can suggest a dish. Quick or elaborate?
New Message: quick
Output: quick South Asian dish recipe

History:
user: I want chicken
assistant: Do you want a curry or rice dish?
New Message: curry
Output: South Asian chicken curry recipe

History:
user: How to cook pasta?
assistant: My database is focused on South Asian cuisine only. Would you like a similar South Asian alternative?
New Message: yes
Output: similar South Asian dish to pasta recipe

History:
user: surprise me
assistant: Tell me one of these: vegetarian or non-vegetarian, quick or elaborate, rice-based, bread-based, or curry
New Message: non vegetarian, quick and curry based
Output: quick non-vegetarian South Asian curry recipe

History:
user: surprise me
assistant: Tell me one of these: vegetarian or non-vegetarian, quick or elaborate, rice-based, bread-based, or curry
user: non vegetarian, quick and curry based
assistant: Any flavor preference?
New Message: spicy
Output: quick spicy non-vegetarian South Asian curry recipe

Bad examples:
New Message: yes
Bad Output: yes

New Message: spicy
Bad Output: spicy

New Message: okay
Bad Output: okay

<|im_end|>
<|im_start|>user
Chat History:
{history}

New Message: {question}<|im_end|>
<|im_start|>assistant
""",
        input_variables=["history", "question"]
    )

    chain = prompt | rewriter_llm
    standalone_query = chain.invoke(
        {"history": recent_history, "question": question}
    ).strip()

    if not standalone_query or len(standalone_query) < 2:
        standalone_query = question

    print(f"--- ORIGINAL: '{question}' | REWRITTEN: '{standalone_query}' ---")
    return {"question": standalone_query}

# ==========================================
# 6. BUILD GRAPH
# ==========================================
workflow = StateGraph(GraphState)

# 1. We removed the rewriter node here
workflow.add_node("classifier", classify_intent_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_recipe_node)
workflow.add_node("clarify", clarify_ingredients_node)
workflow.add_node("clarify_vague", clarify_vague_node)
workflow.add_node("out_of_bounds", out_of_bounds_node)

# 2. Set the entry point BACK to the classifier
workflow.set_entry_point("classifier")

# 3. Keep your conditional edges exactly the same
workflow.add_conditional_edges(
    "classifier",
    route_logic,
    {
        "retrieve": "retrieve",
        "clarify": "clarify",
        "clarify_vague": "clarify_vague",
        "out_of_bounds": "out_of_bounds",
    }
)

workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)
workflow.add_edge("clarify", END)
workflow.add_edge("clarify_vague", END)
workflow.add_edge("out_of_bounds", END)

app = workflow.compile()


# ==========================================
# 7. DJANGO INTERFACE
# ==========================================
def get_assistant_response(user_input: str, chat_history: list) -> dict: 
    try:
        # Pass the history into the initial state!
        inputs = {"question": user_input, "chat_history": chat_history}
        final_state = app.invoke(inputs)

        return {
            "answer": final_state.get("generation", ""),
            # Map raw JSON chunks exactly as they came from FAISS dict
            "chunks_used": final_state.get("raw_chunks", {}), 
            "intent": final_state.get("intent", "Unknown"),
            "selected_dishes": final_state.get("selected_dishes", []),
            "extracted": final_state.get("extracted", {})
        }

    except Exception as e:
        print(f"Error in LangGraph execution: {e}")
        traceback.print_exc()
        return {
            "answer": "I'm sorry, I encountered an internal error processing your request.",
            "chunks_used": {},
            "intent": "Error",
            "selected_dishes": [],
            "extracted": {}
        }