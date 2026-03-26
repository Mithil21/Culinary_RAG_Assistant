# Author: Mithil Baria
# import os

# # ==========================================
# # 1. INITIALIZE MODELS & DATABASE
# # ==========================================
# print("Loading FAISS Database...")
# # Load the BAAI embedding model exactly as before
# bge_embeddings = HuggingFaceEmbeddings(
#     model_name="BAAI/bge-small-en-v1.5",
#     model_kwargs={'device': 'cpu'}, 
#     encode_kwargs={'normalize_embeddings': True}
# )
# # Load the vector store from your local folder
# vector_store = FAISS.load_local("./faiss_index", bge_embeddings, allow_dangerous_deserialization=True)
# retriever = vector_store.as_retriever(search_kwargs={"k": 3}) # Strict maximum of 3 chunks to reduce noise

# print("Loading Qwen2.5-0.5B-Instruct Model...")
# model_id = "Qwen/Qwen2.5-0.5B-Instruct"
# tokenizer = AutoTokenizer.from_pretrained(model_id)
# model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")

# # Wrap Qwen in a LangChain Pipeline
# pipe = pipeline(
#     "text-generation",
#     model=model,
#     tokenizer=tokenizer,
#     max_new_tokens=256,
#     max_length=None, # Suppresses the warning
#     temperature=0.1, # Low temp for more deterministic routing and answers
#     repetition_penalty=1.1,
#     return_full_text=False # Prevents the prompt from bleeding into the output
# )
# llm = HuggingFacePipeline(pipeline=pipe)

# # ==========================================
# # 2. DEFINE THE GRAPH STATE
# # ==========================================
# class GraphState(TypedDict):
#     """Represents the state of our graph."""
#     question: str
#     intent: str
#     context: List[str]
#     generation: str

# # ==========================================
# # 3. DEFINE THE NODES (The Functions)
# # ==========================================
# def classify_intent_node(state: GraphState):
#     """Classifies the prompt using Few-Shot examples and a foolproof Regex parser."""
#     question = state["question"]
    
#     prompt = PromptTemplate(
#         template="""<|im_start|>system
# You are a strict routing assistant. Classify the user's input into A, B, or C.
# A: ANY recipe request, general food query (like "yoghurt", "chicken", "mishti doi"), or conversational reply ("yes", "okay").
# B: ONLY listing raw ingredients (e.g., "milk, sugar, rice").
# C: Explicitly asking for a NON-South Asian cuisine (e.g., "Mexican", "Italian", "tacos").

# Output ONLY the single letter A, B, or C. Do not write anything else.

# Examples:
# Input: "How do I make a chicken dish?"
# Output: A

# Input: "milk, sugar"
# Output: B

# Input: "How do I make Mexican tacos?"
# Output: C

# Input: "how do i make sweet yoghurt dish?"
# Output: A

# Input: "yes"
# Output: A<|im_end|>
# <|im_start|>user
# {question}<|im_end|>
# <|im_start|>assistant
# """,
#         input_variables=["question"]
#     )
    
#     chain = prompt | llm
#     result = chain.invoke({"question": question}).strip().upper()
    
#     # The Bug-Killer Parser: Look for A, B, or C as a standalone word
#     intent = "A" # Default
#     match = re.search(r'\b[ABC]\b', result)
    
#     if match:
#         intent = match.group(0) # Grabs the isolated A, B, or C
#     else:
#         # Absolute fallback if regex misses
#         if result.startswith("C"): intent = "C"
#         elif result.startswith("B"): intent = "B"
#         else: intent = "A"
        
#     print(f"--- ROUTER CLASSIFIED AS SCENARIO {intent} (Raw output: '{result}') ---")
#     return {"intent": intent}

# def retrieve_node(state: GraphState):
#     """Retrieves chunks from FAISS for Scenario A and removes exact duplicates."""
#     question = state["question"]
#     print("--- RETRIEVING FROM FAISS ---")
#     docs = retriever.invoke(question)
    
#     unique_chunks = []
#     seen_texts = set()
    
#     for d in docs:
#         # Strip whitespace to catch slight formatting duplicates
#         clean_text = d.page_content.strip() 
#         if clean_text not in seen_texts:
#             seen_texts.add(clean_text)
#             unique_chunks.append(f"Dish: {d.metadata['dish_name']}\nContent: {clean_text}")
            
#     return {"context": unique_chunks}

# def generate_recipe_node(state: GraphState):
#     """Generates the final recipe using Qwen's native ChatML format."""
#     question = state["question"]
#     context = "\n\n".join(state["context"])
#     print("--- GENERATING FINAL RECIPE (QWEN) ---")
    
#     prompt = PromptTemplate(
#         template="""<|im_start|>system
# You are a professional, friendly South Asian Culinary Assistant.
# Rule 1: Use ONLY the provided Context to answer the question.
# Rule 2: If the Context contains multiple different dishes (e.g., Chicken Tikka AND Chicken Korma) and the request is vague, DO NOT give a full recipe. Instead, list the available dishes and ask the user which one they prefer.
# Rule 3: If the Context does not contain the answer, say exactly: "I'm sorry, I don't have a recipe for that in my database."
# Rule 4: Format your response beautifully using Markdown. Include a friendly opening sentence. Use bold headings like **Ingredients** and **Instructions**. Use bullet points for ingredients and numbered lists for the cooking steps.<|im_end|>
# <|im_start|>user
# Context:
# {context}

# Question: {question}<|im_end|>
# <|im_start|>assistant
# """,
#         input_variables=["context", "question"]
#     )
    
#     chain = prompt | llm
#     generation = chain.invoke({"context": context, "question": question})
    
#     final_answer = generation.split("<|im_start|>assistant")[-1].replace("<|im_end|>", "").strip()
#     return {"generation": final_answer}

# def clarify_ingredients_node(state: GraphState):
#     """Scenario B: Asks for more details when only ingredients are provided."""
#     print("--- GENERATING CLARIFICATION ---")
#     response = "I see you listed some ingredients! Before I find a recipe, do you want a quick meal or a slow-cooked dish? Also, what kind of cooking utensils do you have available?"
#     return {"generation": response}

# def out_of_bounds_node(state: GraphState):
#     """Scenario C: Handles non-South Asian queries."""
#     print("--- GENERATING OUT OF BOUNDS RESPONSE ---")
#     response = "My database is specialized only for South Asian cuisine. However, there might be similar styles of recipes in my database. Would you like me to look for a South Asian alternative?"
#     return {"generation": response}

# # ==========================================
# # 4. DEFINE ROUTING LOGIC & COMPILE GRAPH
# # ==========================================
# def route_logic(state: GraphState) -> str:
#     """Decides which node to go to next based on the intent."""
#     intent = state["intent"]
#     if intent == "A": return "retrieve"
#     elif intent == "B": return "clarify"
#     elif intent == "C": return "out_of_bounds"
#     return "retrieve" # Fallback

# # Build the Graph
# workflow = StateGraph(GraphState)

# # Add Nodes
# workflow.add_node("classifier", classify_intent_node)
# workflow.add_node("retrieve", retrieve_node)
# workflow.add_node("generate", generate_recipe_node)
# workflow.add_node("clarify", clarify_ingredients_node)
# workflow.add_node("out_of_bounds", out_of_bounds_node)

# # Add Edges
# workflow.set_entry_point("classifier")
# workflow.add_conditional_edges("classifier", route_logic)
# workflow.add_edge("retrieve", "generate")
# workflow.add_edge("generate", END)
# workflow.add_edge("clarify", END)
# workflow.add_edge("out_of_bounds", END)

# # Compile
# app = workflow.compile()

# # ==========================================
# # 5. DJANGO INTERFACE
# # ==========================================
# def get_assistant_response(user_input: str) -> dict:
#     """
#     This function is called by the Django view. 
#     It runs the LangGraph workflow and packages the output for the API.
#     """
#     try:
#         inputs = {"question": user_input}
#         final_state = app.invoke(inputs)
        
#         return {
#             "answer": final_state.get('generation', ''),
#             "chunks_used": final_state.get('context', []),
#             "intent": final_state.get('intent', 'Unknown')
#         }
#     except Exception as e:
#         print(f"Error in LangGraph execution: {e}")
#         return {
#             "answer": "I'm sorry, I encountered an internal error processing your request.",
#             "chunks_used": [],
#             "intent": "Error"
#         }

import json
import re
import torch
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

bge_embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

vector_store = FAISS.load_local(
    "./faiss_index",
    bge_embeddings,
    allow_dangerous_deserialization=True,
)

# Use retriever for normal semantic search
retriever = vector_store.as_retriever(search_kwargs={"k": 8})


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
    max_new_tokens=50, # Keep this very low so it responds instantly!
    temperature=0.1,   # Keep it cold so it doesn't get creative
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
    max_new_tokens=300,
    temperature=0.1,
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

    if looks_like_ingredient_list(q):
        return "INGREDIENTS_ONLY"

    if any(re.search(p, q) for p in RECIPE_PATTERNS):
        return "RECIPE_REQUEST"

    if any(re.search(p, q) for p in SUGGESTION_PATTERNS):
        return "SUGGESTION_REQUEST"

    if any(re.search(p, q) for p in VAGUE_PATTERNS):
        return "VAGUE_REQUEST"

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
    
    # Extract flavor profiles
    flavor_preference = ""
    if "spicy" in q or "hot" in q or "chili" in q or "masala" in q:
        flavor_preference = "spicy"
    elif "sweet" in q or "dessert" in q or "mithai" in q:
        flavor_preference = "sweet"

    ingredients = []
    tokens = re.split(r",| and |\n", q)
    for token in tokens:
        tok = token.strip()
        if not tok:
            continue
        if tok in COMMON_INGREDIENT_WORDS:
            ingredients.append(tok)

    return {
        "ingredients": list(dict.fromkeys(ingredients)),
        "time_preference": time_preference,
        "diet_preference": diet_preference,
        "flavor_preference": flavor_preference,
        "cuisine_scope": "south_asian",
    }


def build_retrieval_query(question: str, intent: str, extracted: Dict[str, Any]) -> str:
    ingredients = extracted.get("ingredients", [])
    time_preference = extracted.get("time_preference", "")
    diet = extracted.get("diet_preference", "")
    flavor = extracted.get("flavor_preference", "")

    # Build the descriptive modifiers
    modifiers = f"{time_preference} {flavor} {diet}".strip()
    
    # Format the ingredients if we have them
    ingredient_str = " ".join(ingredients) if ingredients else ""

    # 1. Handle Alternative Requests (Pizza -> Naan)
    if intent == "ALTERNATIVE_REQUEST":
        alt_search = extracted.get("alternative_search", "")
        return f"South Asian {modifiers} recipe {alt_search}"

    # 2. THE FIX: If we have ingredients in memory, ALWAYS inject them into the search!
    if ingredient_str:
        return f"South Asian {modifiers} recipe using {ingredient_str} {question}".strip()

    # 3. Fallback for generic questions
    return f"South Asian {modifiers} recipe {question}".strip()


def group_docs_by_dish(docs) -> Dict[str, Dict[str, str]]:
    grouped: Dict[str, Dict[str, str]] = {}

    for d in docs:
        metadata = d.metadata or {}
        dish_name = metadata.get("dish_name", "Unknown Dish").strip()
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


def score_grouped_dishes(grouped: Dict[str, Dict[str, str]]) -> List[str]:
    """
    Prefer dishes with more complete structure:
    Introduction + Ingredients + Instructions
    """
    scored = []

    for dish, parts in grouped.items():
        score = 0
        if parts.get("Introduction"):
            score += 2
        if parts.get("Ingredients"):
            score += 3
        if parts.get("Instructions"):
            score += 4
        scored.append((dish, score))

    scored.sort(key=lambda x: x[1], reverse=True)
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
    """
    Retrieve relevant chunks and group them by dish_name so generation can always produce:
    About the dish -> Ingredients -> Instructions
    """
    question = state["question"]
    intent = state["intent"]
    extracted = state.get("extracted", {})

    retrieval_query = build_retrieval_query(question, intent, extracted)
    print(f"--- RETRIEVING FROM FAISS: {retrieval_query} ---")

    docs = retriever.invoke(retrieval_query)

    grouped = group_docs_by_dish(docs)
    ranked_dishes = score_grouped_dishes(grouped)

    # keep top 3 dish candidates max
    selected_dishes = ranked_dishes[:3]

    raw_context = []
    for dish in selected_dishes:
        parts = grouped[dish]
        raw_context.append(
            f"Dish: {dish}\n"
            f"Introduction: {parts.get('Introduction', '')}\n"
            f"Ingredients: {parts.get('Ingredients', '')}\n"
            f"Instructions: {parts.get('Instructions', '')}"
        )

    print(f"--- DISH CANDIDATES: {selected_dishes} ---")

    return {
        "context": raw_context,
        "grouped_context": grouped,
        "selected_dishes": selected_dishes
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
    """
    Final response rules:
    - If one strong dish match: provide
      1. About the dish
      2. Ingredients
      3. Instructions
    - If multiple plausible dish matches and query is vague/suggestive: list options first
    """
    question = state["question"]
    intent = state["intent"]
    grouped = state.get("grouped_context", {})
    selected_dishes = state.get("selected_dishes", [])

    print("--- GENERATING FINAL RECIPE ---")

    if not grouped or not selected_dishes:
        return {
            "generation": "I'm sorry, I don't have a recipe for that in my database."
        }

    context_text = serialize_grouped_context_for_prompt(grouped, selected_dishes)

    prompt = PromptTemplate(
        template="""<|im_start|>system
You are a professional, friendly South Asian Culinary Assistant.

You must follow these rules exactly:

Rule 1:
Use ONLY the provided Context.

Rule 2:
If there is one clearly relevant dish, answer in this exact order:
1. A short friendly opening
2. **About the Dish**
3. **Ingredients**
4. **Instructions**

Rule 3:
If multiple different dishes are present and the user's request is vague, short, or suggestive, do NOT give a full recipe immediately.
Instead:
- list 2 to 3 matching dish names
- give 1 short line about each
- ask the user which one they want

Rule 4:
If the context is missing the answer, say exactly:
"I'm sorry, I don't have a recipe for that in my database."

Rule 5:
Do not invent ingredients or steps.
Do not use knowledge outside the context.

Rule 6:
When giving a recipe:
- Use Markdown
- Use bold section headings
- Ingredients should be bullet points if possible
- Instructions should be numbered

Rule 7:
When answering, beautify the answer with a friendly tone, emojis, and engaging language to make it more enjoyable to read.
Make the answers look correct and well formatted.

Intent: {intent}
<|im_end|>
<|im_start|>user
Context:
{context}

Question:
{question}
<|im_end|>
<|im_start|>assistant
""",
        input_variables=["intent", "context", "question"]
    )

    chain = prompt | llm
    raw_generation = chain.invoke({
        "intent": intent,
        "context": context_text,
        "question": question
    })

    final_answer = safe_strip_generation(raw_generation)

    if not final_answer:
        final_answer = "I'm sorry, I don't have a recipe for that in my database."

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
   - "non vegetarian"
3. Do NOT answer the user.
4. Output ONLY the rewritten search query text.
5. Do NOT include explanations, labels, bullets, quotes, or extra text.
6. If the new message is already clear and standalone, return it with only minimal cleanup.
7. If the user is accepting a South Asian alternative after rejecting a non-South-Asian dish, rewrite toward a similar South Asian dish search.
8. If the new message adds preferences, merge them with the latest relevant food request from history.
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
            "chunks_used": final_state.get("context", []),
            "intent": final_state.get("intent", "Unknown"),
            "selected_dishes": final_state.get("selected_dishes", []),
            "extracted": final_state.get("extracted", {})
        }

    except Exception as e:
        print(f"Error in LangGraph execution: {e}")
        return {
            "answer": "I'm sorry, I encountered an internal error processing your request.",
            "chunks_used": [],
            "intent": "Error",
            "selected_dishes": [],
            "extracted": {}
        }