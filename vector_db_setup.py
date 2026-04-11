import json
import os
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# ==========================================
# 1. CONFIGURATION
# ==========================================
CORPUS_FILE = "vector_ready_corpus_with_metadata.json"
INDEX_DIR = "./faiss_index"
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"

print("=" * 60)
print("  🍛 BUILDING SEMANTIC FAISS INDEX")
print("=" * 60)

with open(CORPUS_FILE, "r", encoding="utf-8") as f:
    raw_recipes = json.load(f)

print(f"✅ Loaded {len(raw_recipes)} raw recipe documents from JSON.\n")

# ==========================================
# 2. CHUNK CREATION — 3 CHUNKS PER RECIPE
# ==========================================
# Your JSON already has pre-parsed sections inside item["recipe"]:
#   - item["recipe"]["intro"]          → string
#   - item["recipe"]["ingredients"]    → list of strings
#   - item["recipe"]["instructions"]   → list of strings
# Top-level metadata lives at: item["id"], item["title"],
#   item["source_url"], item["cuisine_type"], item["metadata"]
# ==========================================

chunked_documents = []

for item in raw_recipes:
    # --- TOP-LEVEL FIELDS ---
    dish_name    = str(item.get("title", "Unknown Dish")).strip()
    recipe_id    = str(item.get("id", dish_name.replace(" ", "_").lower())).strip()
    source_url   = item.get("source_url", "")
    cuisine_type = item.get("cuisine_type", "South Asian")

    # nested metadata block
    nested_meta  = item.get("metadata", {})
    diet         = nested_meta.get("diet", "unknown")
    prep_time    = nested_meta.get("prep_time", "unknown")
    dish_type    = nested_meta.get("dish_type", "unknown")

    # --- SHARED BASE METADATA (same for all 3 chunks) ---
    base_meta = {
        "title":        dish_name,
        "source_url":   source_url,
        "cuisine_type": cuisine_type,
        "diet":         diet,
        "prep_time":    prep_time,
        "dish_type":    dish_type,
    }

    # --- PRE-PARSED CONTENT FROM JSON ---
    recipe_block  = item.get("recipe", {})
    intro_text    = recipe_block.get("intro", "").strip()

    # ingredients is a list → join into a bullet string
    ingredients_raw = recipe_block.get("ingredients", [])
    ing_text = "\n".join(f"- {i}" for i in ingredients_raw).strip()

    # instructions is a list → join as numbered steps (already numbered in data)
    instructions_raw = recipe_block.get("instructions", [])
    inst_text = "\n".join(instructions_raw).strip()

    # ---- CHUNK 1: INTRODUCTION ----
    if intro_text:
        meta_intro = {**base_meta,
                      "db_chunk_id":  f"{recipe_id}_intro",
                      "content_type": "introduction"}
        chunked_documents.append(Document(
            page_content=(
                f"Dish: {dish_name}\n"
                f"Section: Introduction\n\n"
                f"{intro_text}"
            ),
            metadata=meta_intro
        ))

    # ---- CHUNK 2: INGREDIENTS ----
    if ing_text:
        meta_ing = {**base_meta,
                    "db_chunk_id":  f"{recipe_id}_ingredients",
                    "content_type": "ingredients"}
        chunked_documents.append(Document(
            page_content=(
                f"Dish: {dish_name}\n"
                f"Section: Ingredients\n\n"
                f"{ing_text}"
            ),
            metadata=meta_ing
        ))

    # ---- CHUNK 3: INSTRUCTIONS ----
    if inst_text:
        meta_inst = {**base_meta,
                     "db_chunk_id":  f"{recipe_id}_instructions",
                     "content_type": "instructions"}
        chunked_documents.append(Document(
            page_content=(
                f"Dish: {dish_name}\n"
                f"Section: Instructions\n\n"
                f"{inst_text}"
            ),
            metadata=meta_inst
        ))

print(f"✅ Created {len(chunked_documents)} semantic chunks "
      f"from {len(raw_recipes)} recipes "
      f"(~3 chunks each: intro + ingredients + instructions)\n")

# --- SAFETY CHECK ---
if len(chunked_documents) == 0:
    raise ValueError(
        "CRITICAL: 0 chunks were created. "
        "Check that 'recipe' keys exist in your JSON."
    )

# ==========================================
# 3. BUILD & SAVE FAISS INDEX
# ==========================================
print(f"🔄 Initialising embedding model: {EMBEDDING_MODEL} ...")
embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},  # cosine-similarity safe
)

print("🔄 Vectorising chunks and building FAISS index ...")
vector_store = FAISS.from_documents(chunked_documents, embeddings)

os.makedirs(INDEX_DIR, exist_ok=True)
vector_store.save_local(INDEX_DIR)

print(f"\n✅ FAISS index saved to '{INDEX_DIR}/'")
print("   Files created: index.faiss  +  index.pkl")
print("\n🎉 Done! Your index is ready for the LangGraph pipeline.\n")

# ==========================================
# 4. QUICK SANITY CHECK  (optional — remove in prod)
# ==========================================
print("=" * 60)
print("  🔍 SANITY CHECK — Sample chunk structure")
print("=" * 60)
sample = chunked_documents[0]
print(f"page_content preview:\n{sample.page_content[:300]}\n")
print(f"metadata:\n{json.dumps(sample.metadata, indent=2)}")