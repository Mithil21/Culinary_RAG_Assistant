import json
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# 1. Load your raw JSON data
print("Loading raw JSON data...")
with open("south_asian_corpus_enriched.json", "r", encoding="utf-8") as f:
    raw_data = json.load(f)

documents = []

print("Auto-tagging and creating documents...")
for item in raw_data:
    text_content = item.get("text", "")
    existing_metadata = item.get("metadata", {})
    
    dish_name = existing_metadata.get("dish_name", "Unknown Dish")
    
    # Auto-Tagger: Analyze both the text and the dish name for keywords
    search_text = (text_content + " " + dish_name).lower()
    
    # Define tags based on keywords
    is_veg = "yes" if any(w in search_text for w in ["paneer", "vegetable", "lentil", "dal", "chickpea"]) else "no"
    is_non_veg = "yes" if any(w in search_text for w in ["chicken", "meat", "fish", "mutton", "lamb"]) else "no"
    is_quick = "yes" if any(w in search_text for w in ["quick", "10 mins", "15 mins", "fast", "easy"]) else "no"
    is_spicy = "yes" if any(w in search_text for w in ["chili", "spicy", "hot", "masala", "pepper"]) else "no"
    is_sweet = "yes" if any(w in search_text for w in ["sweet", "dessert", "sugar", "syrup", "jaggery"]) else "no"
    
    # Create a consolidated flavor tag for easier searching
    flavor = "spicy" if is_spicy == "yes" else ("sweet" if is_sweet == "yes" else "")
    
    # Merge your existing JSON metadata with the new tags using Python's ** unpacking
    enhanced_metadata = {
        **existing_metadata, 
        "vegetarian": is_veg,
        "non_vegetarian": is_non_veg,
        "quick": is_quick,
        "flavor": flavor
    }
    
    # Create the final LangChain Document
    doc = Document(
        page_content=text_content,
        metadata=enhanced_metadata
    )
    documents.append(doc)

print(f"Successfully processed {len(documents)} documents.")

# 2. Embed and save to FAISS
print("Initializing Embedding Model...")
bge_embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

print("Building FAISS index... (This may take a minute)")
vector_store = FAISS.from_documents(documents, bge_embeddings)

print("Saving FAISS index locally...")
vector_store.save_local("./faiss_index")
print("Done! Your database is now tagged and ready.")