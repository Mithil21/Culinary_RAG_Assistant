import os
from typing import TypedDict, List
import re
from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# ==========================================
# 1. INITIALIZE MODELS & DATABASE
# ==========================================
print("Loading FAISS Database...")
# Load the BAAI embedding model exactly as before
bge_embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={'device': 'cpu'}, 
    encode_kwargs={'normalize_embeddings': True}
)
# Load the vector store from your local folder
vector_store = FAISS.load_local("./faiss_index", bge_embeddings, allow_dangerous_deserialization=True)
retriever = vector_store.as_retriever(search_kwargs={"k": 3}) # Strict maximum of 3 chunks to reduce noise

print("Loading Qwen2.5-0.5B-Instruct Model...")
model_id = "Qwen/Qwen2.5-0.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")

# Wrap Qwen in a LangChain Pipeline
pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=256,
    max_length=None, # Suppresses the warning
    temperature=0.1, # Low temp for more deterministic routing and answers
    repetition_penalty=1.1,
    return_full_text=False # Prevents the prompt from bleeding into the output
)
llm = HuggingFacePipeline(pipeline=pipe)

# ==========================================
# 2. DEFINE THE GRAPH STATE
# ==========================================
class GraphState(TypedDict):
    """Represents the state of our graph."""
    question: str
    intent: str
    context: List[str]
    generation: str

# ==========================================
# 3. DEFINE THE NODES (The Functions)
# ==========================================
def classify_intent_node(state: GraphState):
    """Classifies the prompt using Few-Shot examples and a foolproof Regex parser."""
    question = state["question"]
    
    prompt = PromptTemplate(
        template="""<|im_start|>system
You are a strict routing assistant. Classify the user's input into A, B, or C.
A: ANY recipe request, general food query (like "yoghurt", "chicken", "mishti doi"), or conversational reply ("yes", "okay").
B: ONLY listing raw ingredients (e.g., "milk, sugar, rice").
C: Explicitly asking for a NON-South Asian cuisine (e.g., "Mexican", "Italian", "tacos").

Output ONLY the single letter A, B, or C. Do not write anything else.

Examples:
Input: "How do I make a chicken dish?"
Output: A

Input: "milk, sugar"
Output: B

Input: "How do I make Mexican tacos?"
Output: C

Input: "how do i make sweet yoghurt dish?"
Output: A

Input: "yes"
Output: A<|im_end|>
<|im_start|>user
{question}<|im_end|>
<|im_start|>assistant
""",
        input_variables=["question"]
    )
    
    chain = prompt | llm
    result = chain.invoke({"question": question}).strip().upper()
    
    # The Bug-Killer Parser: Look for A, B, or C as a standalone word
    intent = "A" # Default
    match = re.search(r'\b[ABC]\b', result)
    
    if match:
        intent = match.group(0) # Grabs the isolated A, B, or C
    else:
        # Absolute fallback if regex misses
        if result.startswith("C"): intent = "C"
        elif result.startswith("B"): intent = "B"
        else: intent = "A"
        
    print(f"--- ROUTER CLASSIFIED AS SCENARIO {intent} (Raw output: '{result}') ---")
    return {"intent": intent}

def retrieve_node(state: GraphState):
    """Retrieves chunks from FAISS for Scenario A and removes exact duplicates."""
    question = state["question"]
    print("--- RETRIEVING FROM FAISS ---")
    docs = retriever.invoke(question)
    
    unique_chunks = []
    seen_texts = set()
    
    for d in docs:
        # Strip whitespace to catch slight formatting duplicates
        clean_text = d.page_content.strip() 
        if clean_text not in seen_texts:
            seen_texts.add(clean_text)
            unique_chunks.append(f"Dish: {d.metadata['dish_name']}\nContent: {clean_text}")
            
    return {"context": unique_chunks}

def generate_recipe_node(state: GraphState):
    """Generates the final recipe using Qwen's native ChatML format."""
    question = state["question"]
    context = "\n\n".join(state["context"])
    print("--- GENERATING FINAL RECIPE (QWEN) ---")
    
    prompt = PromptTemplate(
        template="""<|im_start|>system
You are a professional, friendly South Asian Culinary Assistant.
Rule 1: Use ONLY the provided Context to answer the question.
Rule 2: If the Context contains multiple different dishes (e.g., Chicken Tikka AND Chicken Korma) and the request is vague, DO NOT give a full recipe. Instead, list the available dishes and ask the user which one they prefer.
Rule 3: If the Context does not contain the answer, say exactly: "I'm sorry, I don't have a recipe for that in my database."
Rule 4: Format your response beautifully using Markdown. Include a friendly opening sentence. Use bold headings like **Ingredients** and **Instructions**. Use bullet points for ingredients and numbered lists for the cooking steps.<|im_end|>
<|im_start|>user
Context:
{context}

Question: {question}<|im_end|>
<|im_start|>assistant
""",
        input_variables=["context", "question"]
    )
    
    chain = prompt | llm
    generation = chain.invoke({"context": context, "question": question})
    
    final_answer = generation.split("<|im_start|>assistant")[-1].replace("<|im_end|>", "").strip()
    return {"generation": final_answer}

def clarify_ingredients_node(state: GraphState):
    """Scenario B: Asks for more details when only ingredients are provided."""
    print("--- GENERATING CLARIFICATION ---")
    response = "I see you listed some ingredients! Before I find a recipe, do you want a quick meal or a slow-cooked dish? Also, what kind of cooking utensils do you have available?"
    return {"generation": response}

def out_of_bounds_node(state: GraphState):
    """Scenario C: Handles non-South Asian queries."""
    print("--- GENERATING OUT OF BOUNDS RESPONSE ---")
    response = "My database is specialized only for South Asian cuisine. However, there might be similar styles of recipes in my database. Would you like me to look for a South Asian alternative?"
    return {"generation": response}

# ==========================================
# 4. DEFINE ROUTING LOGIC & COMPILE GRAPH
# ==========================================
def route_logic(state: GraphState) -> str:
    """Decides which node to go to next based on the intent."""
    intent = state["intent"]
    if intent == "A": return "retrieve"
    elif intent == "B": return "clarify"
    elif intent == "C": return "out_of_bounds"
    return "retrieve" # Fallback

# Build the Graph
workflow = StateGraph(GraphState)

# Add Nodes
workflow.add_node("classifier", classify_intent_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_recipe_node)
workflow.add_node("clarify", clarify_ingredients_node)
workflow.add_node("out_of_bounds", out_of_bounds_node)

# Add Edges
workflow.set_entry_point("classifier")
workflow.add_conditional_edges("classifier", route_logic)
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)
workflow.add_edge("clarify", END)
workflow.add_edge("out_of_bounds", END)

# Compile
app = workflow.compile()

# ==========================================
# 5. DJANGO INTERFACE
# ==========================================
def get_assistant_response(user_input: str) -> dict:
    """
    This function is called by the Django view. 
    It runs the LangGraph workflow and packages the output for the API.
    """
    try:
        inputs = {"question": user_input}
        final_state = app.invoke(inputs)
        
        return {
            "answer": final_state.get('generation', ''),
            "chunks_used": final_state.get('context', []),
            "intent": final_state.get('intent', 'Unknown')
        }
    except Exception as e:
        print(f"Error in LangGraph execution: {e}")
        return {
            "answer": "I'm sorry, I encountered an internal error processing your request.",
            "chunks_used": [],
            "intent": "Error"
        }