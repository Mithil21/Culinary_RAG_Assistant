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

if torch.cuda.is_available():
    device = "cuda"
elif torch.backends.mps.is_available():
    device = "mps" 
else:
    device = "cpu"

print(f"Loading Qwen2.5-0.5B-Instruct Model on {device}...")
model_id = "Qwen/Qwen2.5-0.5B-Instruct"

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.float16 if device != "cpu" else torch.float32
).to(device)

print("Setting up Generator Pipeline...")
pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=400,
    max_length=None, 
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
    raw_docs: List[Any]  # Added to strictly pass the raw FAISS chunks
    generation: str

# ==========================================
# 3. HELPERS & ONTOLOGY
# ==========================================
NON_SOUTH_ASIAN_KEYWORDS = {
    "mexican", "italian", "chinese", "thai", "japanese", "korean",
    "french", "american", "continental", "spanish", "turkish",
    "pizza", "pasta", "taco", "sushi", "ramen", "burger", "spaghetti", "noodles"
}

ALTERNATIVE_MAP = {
    "pasta": "vermicelli seviyan",
    "noodles": "idiyappam sev",
    "pizza": "naan uttapam flatbread roti",
    "taco": "dosa chapati roll kathi",
    "burger": "vada pav dabeli bonda",
    "sushi": "fish rice",
    "mexican": "spicy rajma beans",
    "italian": "tomato garlic paneer",
    "chinese": "indo chinese fried rice spicy",
    "ramen": "spicy soup rasam thukpa",
}

CHAT_REPLY_PATTERNS = r"^\s*(yes|yeah|yep|ok|okay|sure|go ahead|continue|quick one|easy one|slow one)\s*$"
SUGGESTION_PATTERNS = [r"\bwhat can i make\b", r"\bsuggest\b", r"\brecommend\b", r"\bidea\b", r"\bwhat should i cook\b"]
RECIPE_PATTERNS = [r"\bhow to make\b", r"\bhow do i make\b", r"\brecipe\b", r"\bcook\b", r"\bprepare\b"]
INGREDIENT_HINTS = ["i have", "with", "using", "fridge"]
VAGUE_PATTERNS = [r"\bsomething tasty\b", r"\bsomething spicy\b", r"\bsomething easy\b", r"\bsurprise me\b"]

COMMON_INGREDIENT_WORDS = {
    "rice", "lentils", "dal", "milk", "sugar", "salt", "turmeric", "cumin",
    "chili", "chiles", "cardamom", "cloves", "cinnamon", "ginger", "garlic",
    "onion", "onions", "tomato", "tomatoes", "paneer", "chicken", "fish",
    "mutton", "beef", "egg", "eggs", "peas", "chickpeas", "butter", "ghee", "curd",
    "yogurt", "yoghurt", "coriander", "bay leaves", "flour", "roti", "potato", "aloo"
}

def safe_strip_generation(raw: str) -> str:
    if not isinstance(raw, str):
        raw = str(raw)
    return raw.replace("<|im_end|>", "").replace("<|im_start|>assistant", "").strip()

def looks_like_ingredient_list(question: str) -> bool:
    q = question.lower().strip()
    if "," in q:
        tokens = [t.strip() for t in q.split(",") if t.strip()]
        if len(tokens) >= 2: return True
    if any(hint in q for hint in INGREDIENT_HINTS): return True
    words = set(re.findall(r"[a-zA-Z]+", q))
    overlap = words.intersection(COMMON_INGREDIENT_WORDS)
    if len(overlap) >= 2 and len(words) <= 8: return True
    return False

def rule_based_intent(question: str) -> str:
    q = question.lower().strip()
    if any(word in q for word in NON_SOUTH_ASIAN_KEYWORDS): return "NON_SOUTH_ASIAN"
    if re.fullmatch(CHAT_REPLY_PATTERNS, q): return "CHAT_REPLY"
    if looks_like_ingredient_list(q): return "INGREDIENTS_ONLY"
    if any(re.search(p, q) for p in RECIPE_PATTERNS): return "RECIPE_REQUEST"
    if any(re.search(p, q) for p in SUGGESTION_PATTERNS): return "SUGGESTION_REQUEST"
    if any(re.search(p, q) for p in VAGUE_PATTERNS): return "VAGUE_REQUEST"
    if len(q.split()) <= 4: return "DISH_QUERY"
    return "RECIPE_REQUEST"

def extract_basic_slots(question: str) -> Dict[str, Any]:
    q = question.lower()
    time_preference = "quick" if any(w in q for w in ["quick", "fast", "easy"]) else "elaborate" if any(w in q for w in ["slow", "elaborate"]) else ""
    diet_preference = "veg" if any(w in q for w in ["vegetarian", "veg"]) and not "non" in q else "non_veg" if any(w in q for w in ["non veg", "non-veg", "chicken", "fish", "mutton", "beef", "egg"]) else ""
    flavor_preference = "spicy" if any(w in q for w in ["spicy", "hot", "chili", "masala"]) else "sweet" if any(w in q for w in ["sweet", "dessert"]) else ""
    
    words = re.findall(r"\b[a-z]+\b", q)
    ingredients = list(set(words).intersection(COMMON_INGREDIENT_WORDS))
    
    return {
        "ingredients": ingredients,
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

    modifiers = f"{time_preference} {flavor} {diet}".strip()
    ingredient_str = " ".join(ingredients) if ingredients else ""

    if intent == "ALTERNATIVE_REQUEST":
        alt_search = extracted.get("alternative_search", "")
        return f"South Asian {modifiers} recipe {alt_search}"

    if ingredient_str:
        return f"South Asian {modifiers} recipe using {ingredient_str} {question}".strip()

    return f"South Asian {modifiers} recipe {question}".strip()


# ==========================================
# 4. NODES
# ==========================================
def classify_intent_node(state: GraphState):
    question = state["question"].strip()
    history = state.get("chat_history", [])

    intent = rule_based_intent(question)
    
    recent_user_msgs = [m['content'] for m in history if m.get('role') == 'user'][-2:]
    combined_context = " ".join(recent_user_msgs + [question])
    extracted = extract_basic_slots(combined_context)

    if len(history) >= 2:
        last_bot_msg = history[-1].get("content", "").lower()
        if intent == "CHAT_REPLY" and "alternative" in last_bot_msg:
            intent = "ALTERNATIVE_REQUEST"
            last_user_msg = history[-2].get("content", "").lower()
            alt_keywords = [sa_alts for foreign, sa_alts in ALTERNATIVE_MAP.items() if foreign in last_user_msg]
            extracted["alternative_search"] = " ".join(alt_keywords) if alt_keywords else "popular snack"
            question = f"What is a good South Asian alternative to {last_user_msg}?"
            
        elif intent in ["CHAT_REPLY", "DISH_QUERY"] and any(w in last_bot_msg for w in ["fridge", "rice-based", "curry", "snack"]):
            intent = "RECIPE_REQUEST"

    if extracted.get("ingredients") and len(question.split()) <= 4 and intent != "INGREDIENTS_ONLY":
        ing_str = " and ".join(extracted["ingredients"])
        if not any(ing in question.lower() for ing in extracted["ingredients"]):
            question = f"{question} using {ing_str}"

    print(f"\n--- [ROUTER] Intent: {intent} | Slots: {extracted} | Q: '{question}' ---")
    return {"intent": intent, "extracted": extracted, "question": question}


def retrieve_node(state: GraphState):
    question = state["question"]
    intent = state["intent"]
    extracted = state.get("extracted", {})

    retrieval_query = build_retrieval_query(question, intent, extracted)
    
    search_filters = {}
    diet = extracted.get("diet_preference")
    if diet == "veg": search_filters["diet"] = "veg"
    elif diet in ["non_veg", "egg"]: search_filters["diet"] = "non-veg"
        
    time_pref = extracted.get("time_preference")
    if time_pref == "quick": search_filters["prep_time"] = "quick"
    elif time_pref == "elaborate": search_filters["prep_time"] = "slow"

    print(f"--- [FAISS] Searching: '{retrieval_query}' | Filters: {search_filters} ---")

    # --- BUG FIX: Strict Threshold Filtering ---
    SIMILARITY_THRESHOLD = 0.75 # Adjust between 0.0 and 1.0 (Higher = Stricter)

    def get_valid_docs(query, filters=None):
        """Helper to fetch documents and strictly filter out low-score garbage."""
        if filters:
            results = vector_store.similarity_search_with_score(query, k=5, filter=filters)
        else:
            results = vector_store.similarity_search_with_score(query, k=5)
        
        valid = []
        for doc, l2_dist in results:
            # Because our embeddings are normalized, L2 distance directly translates to Cosine Sim.
            cosine_sim = 1.0 - (l2_dist / 2.0)
            print(f"[FAISS Chunk]: {doc.metadata.get('dish_name')} | Score: {cosine_sim:.3f}")
            
            # Only keep chunks above the threshold
            if cosine_sim >= SIMILARITY_THRESHOLD:
                valid.append(doc)
        return valid

    # 1. Try with strict filters first
    valid_docs = []
    if search_filters:
        valid_docs = get_valid_docs(retrieval_query, search_filters)
        if not valid_docs:
            print("--- [FAISS] Filters too strict. Falling back to semantic search. ---")
            valid_docs = get_valid_docs(retrieval_query)
    else:
        # 2. Normal semantic search
        valid_docs = get_valid_docs(retrieval_query)

    print(f"--- [FAISS] Kept {len(valid_docs)} chunks above threshold ---")
    
    return {"raw_docs": valid_docs}


def clarify_ingredients_node(state: GraphState):
    extracted = state.get("extracted", {})
    ingredients = extracted.get("ingredients", [])
    if ingredients:
        response = f"I see you have **{', '.join(ingredients)}**! 🥘\n\nDo you want a **quick snack**, a **hearty curry**, or a **rice-based** dish?"
    else:
        response = "I can definitely suggest a dish based on what's in your fridge!\n\nDo you prefer something **quick**, **spicy**, **vegetarian**, or **non-vegetarian**?"
    return {"generation": response}


def clarify_vague_node(state: GraphState):
    response = "I'd love to suggest something delicious! 🍛\n\nTo help me narrow it down, are you in the mood for:\n- **Vegetarian** or **Non-vegetarian**?\n- Something **quick** or an **elaborate** meal?\n- A **curry**, **bread**, or **rice** dish?"
    return {"generation": response}


def out_of_bounds_node(state: GraphState):
    response = "I specialize strictly in **South Asian cuisine** (Indian, Pakistani, Bangladeshi, etc.)! 🌶️\n\nIf you'd like, I can suggest a highly popular **South Asian alternative** that satisfies that exact same craving. Would you like that?"
    return {"generation": response}


def generate_recipe_node(state: GraphState):
    """
    Bypasses the LLM entirely to guarantee 100% accurate chunks are displayed to the user.
    """
    docs = state.get("raw_docs", [])

    if not docs:
        return {"generation": "I'm sorry, I couldn't find any highly relevant recipes for that right now. Try adjusting your request!"}

    # Format the precise chunks cleanly using Python
    final_answer = "Here are the most relevant exact chunks I retrieved from the database:\n\n"

    for i, doc in enumerate(docs, 1):
        metadata = doc.metadata or {}
        dish_name = metadata.get("dish_name") or metadata.get("title") or "Unknown Dish"
        content_type = metadata.get("content_type", "Text").title()
        url = metadata.get("source_url", "")

        # Format each chunk to be clearly separated
        final_answer += f"### 📌 Chunk {i}: {dish_name} ({content_type})\n"
        final_answer += f"{doc.page_content.strip()}\n\n"
        
        if url:
            final_answer += f"🔗 **Source:** [{url}]({url})\n\n"
            
        # Add a visual separator if it's not the last chunk
        if i < len(docs):
            final_answer += "---\n\n"

    print("--- [RAG] Returning Exact Chunks ---")
    return {"generation": final_answer.strip()}


# ==========================================
# 5. ROUTING LOGIC & GRAPH BUILD
# ==========================================
def route_logic(state: GraphState) -> str:
    intent = state["intent"]
    if intent == "NON_SOUTH_ASIAN": return "out_of_bounds"
    if intent == "INGREDIENTS_ONLY": return "clarify"
    if intent == "VAGUE_REQUEST": return "clarify_vague"
    return "retrieve"

workflow = StateGraph(GraphState)
workflow.add_node("classifier", classify_intent_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_recipe_node)
workflow.add_node("clarify", clarify_ingredients_node)
workflow.add_node("clarify_vague", clarify_vague_node)
workflow.add_node("out_of_bounds", out_of_bounds_node)

workflow.set_entry_point("classifier")
workflow.add_conditional_edges("classifier", route_logic, {
    "retrieve": "retrieve", "clarify": "clarify", 
    "clarify_vague": "clarify_vague", "out_of_bounds": "out_of_bounds"
})

workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)
workflow.add_edge("clarify", END)
workflow.add_edge("clarify_vague", END)
workflow.add_edge("out_of_bounds", END)

app = workflow.compile()

# ==========================================
# 6. DJANGO INTERFACE
# ==========================================
def get_assistant_response(user_input: str, chat_history: list) -> dict: 
    try:
        final_state = app.invoke({"question": user_input, "chat_history": chat_history})
        
        generation = final_state.get("generation", "")
        if not isinstance(generation, str):
            generation = str(generation)
            
        raw_docs = final_state.get("raw_docs", [])
        structured_chunks = []
        
        for doc in raw_docs:
            structured_chunks.append({
                "dish_name": doc.metadata.get("dish_name", "Unknown Dish"),
                "content_type": doc.metadata.get("content_type", "Text").title(),
                "content": doc.page_content,
                "source_url": doc.metadata.get("source_url", "")
            })
            
        return {
            "answer": generation,
            "intent": final_state.get("intent", "Unknown"),
            "chunks": structured_chunks 
        }
    except Exception as e:
        print(f"[ERROR] LangGraph execution failed: {e}")
        return {
            "answer": "I'm sorry, I encountered an internal error processing your request.", 
            "intent": "Error",
            "chunks": []
        }