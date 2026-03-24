import json
import os
import torch
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# ==========================================
# CONFIGURATION
# ==========================================
INPUT_FILE = "vector_ready_corpus.json"  
DB_DIR = "./faiss_index"

def main():
    print(f"Loading structured data from {INPUT_FILE}...")
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Could not find {INPUT_FILE}. Make sure the data prep script ran successfully.")
        return

    documents = []
    print("\nPackaging data into LangChain Documents...")

    for item in data:
        # 1. The Searchable Target
        page_content = item.get("full_text", "")
        if not page_content:
            continue

        # 2. The Payload
        metadata = {
            "id": item.get("id", ""),
            "title": item.get("title", "Unknown Dish"),
            "source_url": item.get("source_url", ""),
            "cuisine_type": item.get("cuisine_type", "South Asian"),
            "diet": item.get("metadata", {}).get("diet", "unknown"),
            "prep_time": item.get("metadata", {}).get("prep_time", "unknown"),
            "dish_type": item.get("metadata", {}).get("dish_type", "unknown"),
            # Stringify the complex dictionary so FAISS doesn't crash
            "recipe_json": json.dumps(item.get("recipe", {}))
        }

        doc = Document(page_content=page_content, metadata=metadata)
        documents.append(doc)

    print(f"Successfully packaged {len(documents)} documents.")

    # ==========================================
    # VECTORIZATION
    # ==========================================
    # Safely determine the best available hardware
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    print(f"\nInitializing Embedding Model (BAAI/bge-large-en-v1.5) on {device}...")
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-large-en-v1.5",
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )

    print("Crunching vectors and building FAISS database... (This might take a minute)")
    vector_store = FAISS.from_documents(documents, embeddings)

    print(f"Saving database to {DB_DIR}...")
    vector_store.save_local(DB_DIR)

    print("✅ Vector database successfully built and saved!")

if __name__ == "__main__":
    main()