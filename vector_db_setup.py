import json
import re
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

def process_and_chunk_recipes(input_file):
    print(f"Loading enriched data from {input_file}...")
    
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = []
    
    for recipe in data:
        # Grabbing from the TOP-LEVEL of your JSON
        dish_name = recipe.get("title", "Unknown Dish")
        cuisine_type = recipe.get("cuisine_type", "South Asian")
        full_text = recipe.get("full_text", "")
        source_url = recipe.get("source_url", "")
        
        # Grabbing from the NESTED metadata of your JSON
        llm_metadata = recipe.get("metadata", {})

        # Split the full_text back into our 3 distinct sections
        sections = re.split(r'\n---\s*(Introduction|Ingredients|Instructions)\s*---\n', full_text, flags=re.IGNORECASE)
        
        # --- NEW: Extract ingredients text to add to ALL chunks for this dish ---
        ingredients_list = []
        for i in range(1, len(sections), 2):
            if sections[i].lower() == "ingredients":
                raw_ingredients = sections[i+1].strip()
                # Clean up the text into a nice list (stripping bullets/dashes)
                ingredients_list = [line.strip().lstrip("-*• ") for line in raw_ingredients.split("\n") if line.strip()]
                break
        
        for i in range(1, len(sections), 2):
            content_type = sections[i].lower()
            content_text = sections[i+1].strip()
            
            if not content_text:
                continue
                
            # Create a clean LangChain document with rich FAISS metadata
            doc = Document(
                page_content=content_text,
                metadata={
                    "dish_name": dish_name, 
                    "cuisine_type": cuisine_type,
                    "content_type": content_type,  
                    "source_url": source_url,
                    "diet": llm_metadata.get("diet", "unknown"),
                    "prep_time": llm_metadata.get("prep_time", "unknown"),
                    "dish_type": llm_metadata.get("dish_type", "unknown"),
                    "ingredients": ingredients_list  # <--- Injecting the ingredients list here!
                }
            )
            docs.append(doc)

    return docs

def main():
    input_file = "south_asian_corpus_enriched.json" 
    
    docs = process_and_chunk_recipes(input_file)
    print(f"Successfully generated {len(docs)} highly structured chunks.")
    
    print("Initializing embedding model (BAAI/bge-small-en-v1.5)...")
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    
    print("Building FAISS Vector Database...")
    vector_store = FAISS.from_documents(docs, embeddings)
    
    output_dir = "./faiss_index"
    vector_store.save_local(output_dir)
    print(f"Done! Vector store saved to {output_dir}")

if __name__ == "__main__":
    main()