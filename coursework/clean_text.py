import json
import re
from tqdm.auto import tqdm

INPUT_FILE = "south_asian_corpus_raw.json"
OUTPUT_FILE = "south_asian_corpus_cleaned.json"

def clean_recipe_text(text: str) -> str:
    """Removes Wikibooks Infoboxes, messy whitespace, and hidden characters."""
    if not isinstance(text, str): return ""
    
    # 1. THE INFOBOX SNIPER
    # This targets the specific starting words of the Wikibooks infobox lines and deletes the whole line.
    text = re.sub(r'(?im)^(Category|Servings|Time|Cookbook)\s*\|.*$\n?', '', text)
    text = re.sub(r'(?im)^Difficulty\s*$\n?', '', text)
    text = re.sub(r'(?im)^Title:\s*.*$\n?', '', text) # Removes redundant title line
    
    # 2. WIKI ARTIFACTS
    text = re.sub(r'\[\d+\]|\[edit\]|\[citation needed\]', '', text)
    
    # 3. WEIRD CHARACTERS & NOISE
    text = re.sub(r'[\u200b\u200e\u200f\ufeff]', '', text)
    
    # 4. WHITESPACE NORMALIZATION
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    
    return text.strip()

def extract_recipe_sections(raw_text: str) -> dict:
    """
    Slices the raw text into Intro, Ingredients, and Instructions 
    using the explicit '--- Section ---' headers.
    """
    recipe_data = {
        "intro": "",
        "ingredients": [],
        "instructions": []
    }
    
    # 1. Extract Introduction
    intro_match = re.search(r'--- Introduction ---(.*?)--- Ingredients ---', raw_text, re.DOTALL)
    if intro_match:
        recipe_data["intro"] = intro_match.group(1).strip()
        
    # 2. Extract Ingredients
    ing_match = re.search(r'--- Ingredients ---(.*?)--- Instructions ---', raw_text, re.DOTALL)
    if ing_match:
        raw_ings = ing_match.group(1).strip().split('\n')
        clean_ings = []
        for line in raw_ings:
            line = line.strip()
            # Skip empty lines, category headers (like "Dough"), and the table header
            if not line or "Ingredient |" in line or "|" not in line:
                continue
                
            # Convert "Water | 1½ cups | 375 g | 68.2%" to "Water: 1½ cups (375 g)"
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                clean_ings.append(f"{parts[0]}: {parts[1]} ({parts[2]})")
            else:
                clean_ings.append(line.replace("|", "-"))
                
        recipe_data["ingredients"] = clean_ings

    # 3. Extract Instructions
    inst_match = re.search(r'--- Instructions ---(.*)', raw_text, re.DOTALL)
    if inst_match:
        raw_inst = inst_match.group(1).strip().split('\n')
        clean_inst = []
        for line in raw_inst:
            line = line.strip()
            # Only grab actual numbered steps
            if line and re.match(r'^\d+\.', line):
                clean_inst.append(line)
                
        recipe_data["instructions"] = clean_inst

    return recipe_data

def main():
    print(f"Loading data from {INPUT_FILE}...")
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            recipes = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        return

    formatted_data = []

    print(f"Cleaning and extracting {len(recipes)} recipes...\n")
    
    for recipe in tqdm(recipes):
        title = recipe.get("title", "Unknown Dish")
        raw_text = recipe.get("full_text", "")
        
        if raw_text:
            # 1. Clean out the Wikibooks junk
            cleaned_text = clean_recipe_text(raw_text)
            
            # 2. Extract the clean text into the JSON format
            extracted_recipe = extract_recipe_sections(cleaned_text)
            
            structured_item = {
                "id": recipe.get("id", ""),
                "source_url": recipe.get("source_url", ""),
                "title": title,
                "cuisine_type": recipe.get("cuisine_type", "South Asian"),
                "full_text": cleaned_text, 
                "recipe": extracted_recipe,  
                "metadata": recipe.get("metadata", {})
            }
            
            formatted_data.append(structured_item)

    print(f"\nSaving structured JSON data to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(formatted_data, f, indent=4, ensure_ascii=False)
        
    print("✅ Process complete!")

if __name__ == "__main__":
    main()