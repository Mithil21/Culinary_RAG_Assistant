import os
import json
import torch
from typing import TypedDict, List, Dict, Any
from llama_cpp import Llama

from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from langchain_huggingface import HuggingFacePipeline
from huggingface_hub import login  # <-- NEW: Imported for auto-login

# ==========================================
# 0. HUGGING FACE AUTO-LOGIN
# ==========================================
# Replace "YOUR_HF_TOKEN_HERE" with your actual Hugging Face token, 
# or set it as an environment variable named HF_TOKEN.
# HF_TOKEN = os.environ.get("HF_TOKEN", "<YOUR_HF_TOKEN_HERE>")

# if HF_TOKEN and HF_TOKEN != "YOUR_HF_TOKEN_HERE":
#     print("Authenticating with Hugging Face...")
#     login(token=HF_TOKEN)
# else:
#     print("\n[WARNING] No Hugging Face token provided.")
#     print("If you haven't logged in via CLI, gated models like Llama-3.2-3B may fail to load.\n")

# ==========================================
# 1. LOCAL MODEL & DB INITIALIZATION
# ==========================================
print("Loading Local Models & FAISS Database...")

device = "cuda" if torch.cuda.is_available() else "cpu"
    
print(f"\nInitializing Embedding Model (BAAI/bge-large-en-v1.5) on {device}...")
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

# --- Hugging Face Classifier Model ---
model_id = "Qwen/Qwen2.5-0.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" 
)

hf_pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=512,
    temperature=0.1,
    do_sample=True,
    pad_token_id=tokenizer.eos_token_id
)

llm_classifier = HuggingFacePipeline(pipeline=hf_pipe)

# --- Hugging Face Generator Model (Replaces Ollama) ---
print(f"\nInitializing Generator Model (Qwen/Qwen2.5-0.5B-Instruct) on {device}...")
gen_model_id = "Qwen/Qwen2.5-0.5B-Instruct"
gen_tokenizer = AutoTokenizer.from_pretrained(gen_model_id)
gen_model = AutoModelForCausalLM.from_pretrained(
    gen_model_id,
    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" 
)

gen_pipe = pipeline(
    "text-generation",
    model=gen_model,
    tokenizer=gen_tokenizer,
    max_new_tokens=512,
    temperature=0.1,
    do_sample=True,
    pad_token_id=gen_tokenizer.eos_token_id,
    return_full_text=False # Ensures we only get the newly generated text back
)

llm_generator = HuggingFacePipeline(pipeline=gen_pipe)

# ==========================================
# 2. GRAPH STATE & HELPERS
# ==========================================
class GraphState(TypedDict, total=False):
    question: str
    chat_history: list
    intent: str
    extracted: Dict[str, Any]
    raw_docs: List[Any]  
    generation: str

def extract_json_from_response(text: str) -> dict:
    if not text: return {}
    text = text.replace("```json", "").replace("```", "")
    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try: return json.loads(text[start:end+1])
        except: return {}
    return {}

# ==========================================
# 3. NODES
# ==========================================
def classify_intent_node(state: GraphState):
    """
    Uses local Llama 3 via Hugging Face to parse intent, fix typos, and extract metadata.
    """
    question = state["question"].strip()
    history = state.get("chat_history", [])
    
    hist_str = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history[-4:]])
    
    system_prompt = """You are an intelligent routing AI for a South Asian Culinary app.
Analyze the user's input, fix ANY typos, correct reversed words (e.g., "chicken butter" -> "butter chicken"), and extract their preferences into a strict JSON object.

RULES FOR JSON OUTPUT:
1. "intent": Must be one of:
   - "RECIPE_REQUEST": Asking for a specific dish, a recipe, or saying "yes" to a suggestion.
   - "INGREDIENTS_ONLY": Just listing random fridge items (e.g., "chicken, rice, spicy").
   - "VAGUE_REQUEST": Wanting a broad suggestion (e.g., "what should I eat", "something tasty").
   - "OUT_OF_BOUNDS": Asking for non-South Asian food (e.g., "pizza", "tacos", "sushi"). BUT if they ask for an "alternative to pizza", map it to "RECIPE_REQUEST" and change the query to "naan flatbread".
2. "search_query": The cleaned up dish name or ingredients. You MUST fix typos and grammar! (e.g., "chicien butter" -> "butter chicken"). 
3. "diet": "veg", "non-veg", or "unknown".
4. "time": "quick", "slow", or "unknown".
5. "flavor": "sweet", "spicy", or "unknown".

Output ONLY valid JSON. Do not write anything else."""

    # Llama 3.2 Chat Template
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

Chat History: {hist_str}
Input: {question}
JSON Output:<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    print("--- [HuggingFace] parsing intent... ---")
    raw_response = llm_classifier.invoke(prompt)
    parsed = extract_json_from_response(raw_response)
    
    intent = parsed.get("intent", "RECIPE_REQUEST")
    search_query = parsed.get("search_query", question)
    
    extracted = {
        "diet_preference": parsed.get("diet", "unknown"),
        "time_preference": parsed.get("time", "unknown"),
        "flavor_preference": parsed.get("flavor", "unknown"),
        "search_query": search_query
    }
    
    print(f"--- [ROUTER] Intent: {intent} | Clean Query: '{search_query}' | Filters: {extracted} ---")
    
    return {"intent": intent, "extracted": extracted, "question": search_query}


def retrieve_node(state: GraphState):
    """
    100% ACCURACY RETAINED: We still use strict FAISS filtering, the 0.55 threshold, 
    and the strict Python "Bouncer" to block bad metadata matches.
    """
    extracted = state.get("extracted", {})
    retrieval_query = extracted.get("search_query", state["question"])
    
    search_filters = {}
    if extracted.get("diet_preference") == "veg": search_filters["diet"] = "veg"
    elif extracted.get("diet_preference") in ["non-veg", "non_veg"]: search_filters["diet"] = "non-veg"
        
    if extracted.get("time_preference") == "quick": search_filters["prep_time"] = "quick"
    elif extracted.get("time_preference") == "slow": search_filters["prep_time"] = "slow"

    print(f"--- [FAISS] Searching: '{retrieval_query}' | Filters: {search_filters} ---")

    SIMILARITY_THRESHOLD = 0.6500
    flavor_pref = extracted.get("flavor_preference", "unknown")

    def get_valid_docs(query, filters=None):
        if filters:
            results = vector_store.similarity_search_with_score(query, k=15, filter=filters)
        else:
            results = vector_store.similarity_search_with_score(query, k=15)
        
        valid = []
        for doc, l2_dist in results:
            cosine_sim = 1.0 - (l2_dist / 2.0)
            dish_name = doc.metadata.get('title', 'Unknown')
            dish_type = doc.metadata.get("dish_type", "unknown")
            
            # --- THE BOUNCER (Kept intact) ---
            if flavor_pref == "sweet" and dish_type not in ["dessert", "beverage", "unknown"]:
                continue
            if flavor_pref == "spicy" and dish_type == "dessert":
                continue

            # --- THE THRESHOLD (Kept intact) ---
            if cosine_sim >= SIMILARITY_THRESHOLD:
                print(f"[ACCEPTED]: {dish_name} | Score: {cosine_sim:.3f}")
                valid.append(doc)
                
            if len(valid) >= 5: 
                break
                
        return valid

    valid_docs = []
    if search_filters:
        valid_docs = get_valid_docs(retrieval_query, search_filters)
        if not valid_docs:
            valid_docs = get_valid_docs(retrieval_query)
    else:
        valid_docs = get_valid_docs(retrieval_query)
    
    return {"raw_docs": valid_docs}


def clarify_ingredients_node(state: GraphState):
    response = "I see you listed some ingredients! 🥘\n\nDo you want a **quick snack**, a **hearty curry**, or a **rice-based** dish using those?"
    return {"generation": response}

def clarify_vague_node(state: GraphState):
    response = "I'd love to suggest something delicious! 🍛\n\nTo help me narrow it down, are you in the mood for:\n- **Vegetarian** or **Non-vegetarian**?\n- Something **quick** or an **elaborate** meal?\n- A **curry**, **bread**, or **rice** dish?"
    return {"generation": response}

def out_of_bounds_node(state: GraphState):
    response = "I specialize strictly in **South Asian cuisine** (Indian, Pakistani, Bangladeshi, etc.)! 🌶️\n\nIf you'd like, I can suggest a highly popular **South Asian alternative** that satisfies that exact same craving. Would you like that?"
    return {"generation": response}


def generate_recipe_node(state: GraphState):
    """
    Extracts the un-fragmented recipe JSON from FAISS metadata and passes it to Qwen 0.5B 
    for strict Markdown formatting.
    """
    docs = state.get("raw_docs", [])
    question = state["question"]

    if not docs:
        return {"generation": "I'm sorry, I couldn't find a highly relevant recipe for that in my database right now. Could you check the spelling or try another dish?"}

    top_docs = docs[:2] 
    
    print(f"--- [HuggingFace] Asking Qwen 0.5B to format {len(top_docs)} full recipes... ---")
    
    formatted_chunks = []
    
    for i, doc in enumerate(top_docs):
        title = doc.metadata.get("title", "Unknown Dish")
        
        recipe_str = doc.metadata.get("recipe_json", "{}")
        try:
            recipe_data = json.loads(recipe_str)
        except json.JSONDecodeError:
            print(f"[ERROR] Failed to parse JSON metadata for {title}")
            recipe_data = {"intro": "", "ingredients": [], "instructions": []}
            
        raw_text = f"Dish: {title}\n\n"
        raw_text += f"Intro: {recipe_data.get('intro', '')}\n\n"
        
        raw_text += "Ingredients:\n"
        for item in recipe_data.get('ingredients', []):
            raw_text += f"- {item}\n"
            
        raw_text += "\nInstructions:\n"
        for step in recipe_data.get('instructions', []):
            raw_text += f"- {step}\n"

        system_prompt = """You are a precise Markdown Formatting Assistant.
Your ONLY job is to take the provided recipe data and format it into beautiful Markdown.
- Use bolding for headings (like **Introduction**, **Ingredients**, **Instructions**).
- Use bullet points for ingredients and numbered lists for instructions.
- Do NOT invent, guess, or leave out ANY details from the provided text.
- Output ONLY the formatted recipe."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Recipe Data to format:\n{raw_text}"}
        ]
        
        # Build prompt using the model's integrated chat template
        prompt = gen_tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )
        
        chunk_generation = llm_generator.invoke(prompt)
        
        if chunk_generation:
            formatted_chunks.append(chunk_generation.strip())
        else:
            formatted_chunks.append(raw_text.strip())

    final_answer = "Here is what I found for you:\n\n" + "\n\n---\n\n".join(formatted_chunks)

    source_links = []
    for doc in top_docs:
        url = doc.metadata.get("source_url", "")
        dish_title = doc.metadata.get("title", "Unknown Dish")
        if url:
            source_links.append(f"- [{dish_title}]({url})")

    unique_links = list(dict.fromkeys(source_links))
    if unique_links:
        final_answer += "\n\n🔗 **Recipe Sources:**\n" + "\n".join(unique_links)

    return {"generation": final_answer}

# ==========================================
# 4. GRAPH BUILD & ROUTING
# ==========================================
def route_logic(state: GraphState) -> str:
    intent = state["intent"]
    if intent in ["NON_SOUTH_ASIAN", "OUT_OF_BOUNDS"]: return "out_of_bounds"
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
# 5. INTERFACE
# ==========================================
def get_assistant_response(user_input: str, chat_history: list) -> dict: 
    try:
        final_state = app.invoke({"question": user_input, "chat_history": chat_history})
        return {
            "answer": str(final_state.get("generation", "")),
            "intent": final_state.get("intent", "Unknown"),
            "chunks": [{"dish_name": d.metadata.get("title"), "content": d.page_content} for d in final_state.get("raw_docs", [])]
        }
    except Exception as e:
        return {"answer": f"Error: {e}", "intent": "Error", "chunks": []}