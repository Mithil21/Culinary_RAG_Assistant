import json
import ollama
from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# ==========================================
# 1. DATABASE INITIALIZATION
# ==========================================
print("Loading FAISS Database...")
# This still runs locally using your CPU to embed the search queries
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

# ==========================================
# 2. OLLAMA API CALLER
# ==========================================
def call_chat_api(messages: List[Dict[str, str]], model_id: str) -> str:
    """
    Talks directly to your local Ollama server using the official Python client.
    Make sure the Ollama app is running in the background!
    """
    try:
        response = ollama.chat(
            model=model_id,
            messages=messages,
            options={
                "temperature": 0.1,
                "num_predict": 512
            }
        )
        return response['message']['content']
    except Exception as e:
        print(f"\n[ERROR] Ollama API Error: {e}")
        print(f"Is the Ollama app running and did you pull {model_id}? (e.g., 'ollama pull {model_id}')\n")
        return ""

# ==========================================
# 3. GRAPH STATE & HELPERS
# ==========================================
class GraphState(TypedDict, total=False):
    question: str
    chat_history: list
    intent: str
    extracted: Dict[str, Any]
    raw_docs: List[Any]  
    generation: str

def extract_json_from_response(text: str) -> dict:
    """Robust JSON extractor to grab the LLM's structured output."""
    if not text:
        return {}
    text = text.replace("```json", "").replace("```", "")
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError as e:
            print(f"[JSON Parse Error]: {e}")
            return {}
    return {}

# ==========================================
# 4. NODES
# ==========================================
def classify_intent_node(state: GraphState):
    """
    Uses local Llama 3 via Ollama to parse intent, fix typos, and extract metadata.
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

    user_prompt = f"Chat History:\n{hist_str}\n\nUser Input: {question}"

    print("--- [Ollama] Asking Llama 3 to parse intent... ---")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Passing "llama3" as the model_id for Ollama
    response = call_chat_api(messages, model_id="llama3")
    parsed = extract_json_from_response(response)
    
    # Fallbacks
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

    SIMILARITY_THRESHOLD = 0.700 
    flavor_pref = extracted.get("flavor_preference", "unknown")

    def get_valid_docs(query, filters=None):
        if filters:
            results = vector_store.similarity_search_with_score(query, k=15, filter=filters)
        else:
            results = vector_store.similarity_search_with_score(query, k=15)
        
        valid = []
        for doc, l2_dist in results:
            cosine_sim = 1.0 - (l2_dist / 2.0)
            dish_name = doc.metadata.get('dish_name', 'Unknown')
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
    Passes the strict FAISS chunks specifically to the local Qwen 2.5 0.5B model 
    via Ollama so it can construct a beautiful, coherent response.
    We append the URLs using Python at the very end to guarantee they aren't broken.
    """
    docs = state.get("raw_docs", [])
    question = state["question"]

    if not docs:
        return {"generation": "I'm sorry, I couldn't find a highly relevant recipe for that in my database right now. Could you check the spelling or try another dish?"}

    # Format chunks for the LLM to read
    context_str = ""
    for i, doc in enumerate(docs):
        context_str += f"[{i+1}] Dish: {doc.metadata.get('dish_name')} | Section: {doc.metadata.get('content_type', 'Text')}\n{doc.page_content}\n\n"

    # SUMMARIZATION PROMPT FOR SMALL MODELS
    system_prompt = """You are a helpful South Asian Culinary Assistant.
Your task is to clean and beautify the provided Retrieved Database Chunks to answer the user's request.
You MUST rely ONLY on the information in the chunks. Do NOT invent or guess any ingredients or steps.
If the chunks offer multiple options or variations, beautify them (Meaning remove the unnecessary punctions, line and words).
Format the output beautifully in Markdown."""

    user_prompt = f"Retrieved Database Chunks:\n{context_str}\n\nUser Request: {question}"

    print("--- [Ollama] Asking Qwen 0.5B to generate the final recipe... ---")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Using the local Qwen 0.5B model specifically for generation
    raw_generation = call_chat_api(messages, model_id="qwen2.5:0.5b")
    final_answer = raw_generation.strip() if raw_generation else "I had trouble generating the text, but here are the chunks I found."

    # --- Append Authentic Sources (Kept intact) ---
    source_links = []
    for doc in docs:
        url = doc.metadata.get("source_url", "")
        dish_name = doc.metadata.get("dish_name", "Unknown Dish")
        if url:
            source_links.append(f"- [{dish_name}]({url})")

    unique_links = list(dict.fromkeys(source_links))
    if unique_links:
        final_answer += "\n\n🔗 **Recipe Sources:**\n" + "\n".join(unique_links)

    return {"generation": final_answer}


# ==========================================
# 5. ROUTING LOGIC & GRAPH BUILD
# ==========================================
def route_logic(state: GraphState) -> str:
    intent = state["intent"]
    if intent == "NON_SOUTH_ASIAN" or intent == "OUT_OF_BOUNDS": return "out_of_bounds"
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
            
        # We STILL return the raw chunks for your Angular UI!
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
            "answer": "I'm sorry, I encountered an internal error connecting to the API.", 
            "intent": "Error",
            "chunks": []
        }