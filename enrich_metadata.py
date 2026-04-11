import json
import re
from tqdm.auto import tqdm

# Your input should be the file that already has the cleaned ingredients/instructions
INPUT_FILE = "./south_asian_corpus_cleaned.json"
OUTPUT_FILE = "./vector_ready_corpus_with_metadata.json"

def classify_metadata(recipe_dict):
    """
    Classifies the diet, prep_time, and dish_type using pure Python keyword matching.
    Takes 0.001 seconds and requires zero GPU.
    """
    title = recipe_dict.get("title", "").lower()
    recipe_data = recipe_dict.get("recipe", {})

    # Combine everything into one lowercase string for easy searching
    ingredients_str = " ".join(recipe_data.get("ingredients", [])).lower()
    instructions_str = " ".join(recipe_data.get("instructions", [])).lower()
    full_text = f"{title} {ingredients_str} {instructions_str}"

    metadata = {
        "diet": "veg",             # Default to veg
        "prep_time": "quick",      # Default to quick
        "dish_type": "dry-main"    # Default fallback
    }

    # ==========================================
    # 1. DIET CLASSIFICATION
    # ==========================================
    # We use \b (word boundaries) so "eggplant" doesn't trigger "egg"
    non_veg_keywords = r'\b(chicken|mutton|lamb|beef|pork|fish|prawn|shrimp|seafood|egg|eggs|meat)\b'
    if re.search(non_veg_keywords, ingredients_str):
        metadata["diet"] = "non-veg"

    # ==========================================
    # 2. PREP TIME CLASSIFICATION
    # ==========================================
    slow_keywords = r'\b(hour|hours|overnight|marinate|bake|ferment|slow cook|simmer for|40 min|45 min|50 min|60 min)\b'
    if re.search(slow_keywords, instructions_str) or re.search(slow_keywords, ingredients_str):
        metadata["prep_time"] = "slow"

    # ==========================================
    # 3. DISH TYPE CLASSIFICATION
    # ==========================================
    # We check the title first because it's the strongest indicator

    if re.search(r'\b(drink|chai|tea|lassi|sherbet|juice|milkshake)\b', title):
        # Safety check: No meat in beverages!
        if metadata["diet"] == "veg":
            metadata["dish_type"] = "beverage"

    elif re.search(r'\b(kheer|halwa|ladoo|barfi|sweet|dessert|jamun|jalebi|pudding|cake|cookie)\b', full_text):
        metadata["dish_type"] = "dessert"

    elif re.search(r'\b(roti|naan|paratha|dosa|appam|puri|bhatura|chapati|bread)\b', title):
        metadata["dish_type"] = "bread"

    elif re.search(r'\b(rice|biryani|pulao|khichdi|pilaf)\b', title):
        metadata["dish_type"] = "rice"

    elif re.search(r'\b(samosa|pakora|chaat|snack|vada|tikki|bonda|cutlet)\b', title):
        metadata["dish_type"] = "snack"

    elif re.search(r'\b(chutney|achar|pickle|raita|dip|sauce)\b', title):
        metadata["dish_type"] = "pickle-condiment"

    elif re.search(r'\b(curry|masala|gravy|korma|makhani|dal|soup|stew)\b', full_text):
        metadata["dish_type"] = "curry"

    else:
        # If it doesn't match the specific categories above, it's likely a dry main dish
        # (like dry roasted vegetables, fried fish, or dry chicken tikka)
        metadata["dish_type"] = "dry-main"

    return metadata

def main():
    print(f"Loading data from {INPUT_FILE}...")
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            recipes = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        return

    enriched_recipes = []

    print(f"Tagging {len(recipes)} recipes with metadata using Pure Python...")
    for recipe in tqdm(recipes):

        # Instantly generate the metadata
        recipe["metadata"] = classify_metadata(recipe)
        enriched_recipes.append(recipe)

    # Final save
    print(f"\nSaving tagged data to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_recipes, f, indent=4, ensure_ascii=False)

    print("✅ Successfully generated metadata in record time!")

if __name__ == "__main__":
    main()