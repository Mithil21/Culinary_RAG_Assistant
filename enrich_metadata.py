# !pip install -U transformers accelerate bitsandbytes tqdm

import json
import re
import torch
from tqdm.notebook import tqdm
from transformers import pipeline, BitsAndBytesConfig

print("Loading Llama 3 (8B) in 4-bit quantization...")

# 1. Properly format the quantization config to save Kaggle GPU memory
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16
)

# 2. Initialize the Ungated Llama 3 pipeline
model_id = "NousResearch/Meta-Llama-3-8B-Instruct"

generator = pipeline(
    "text-generation", 
    model=model_id, 
    device_map="auto",
    model_kwargs={
        "quantization_config": quantization_config,
    }
)

def extract_json_from_response(text):
    """
    Highly aggressive JSON extractor. Finds the first '{' and the last '}'.
    """
    text = text.replace("```json", "").replace("```", "")
    start = text.find('{')
    end = text.rfind('}')
    
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"\n[JSON Parse Error]: {e}")
            return None
    return None

def generate_metadata(recipe_text):
    """
    Uses Few-Shot prompting with Llama 3 to enforce JSON output.
    """
    system_prompt = (
        "You are a strict JSON data extraction API. "
        "Analyze the recipe and return a valid JSON object. "
        "RULES:\n"
        "1. Keys must be EXACTLY: \"diet\", \"prep_time\", \"dish_type\". Do not add any other keys.\n"
        "2. \"diet\" values: \"veg\" (no meat/eggs), \"non-veg\" (contains meat/poultry/fish/eggs).\n"
        "3. \"prep_time\" values: \"quick\" (under 30 mins) or \"slow\" (over 30 mins or requires soaking/fermenting).\n"
        "4. \"dish_type\" values: \"curry\", \"rice\", \"bread\", \"snack\", \"dessert\", \"beverage\".\n"
        "5. Output ONLY the JSON."
    )
    
    truncated_text = recipe_text[:2000]

    # Llama 3 handles chat templates natively through the pipeline
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Recipe: Title: Chicken Tikka Masala\nIntro: A delicious dish.\nIngredients: Chicken breast, yogurt, spices, tomatoes, cream. Time: 45 mins."},
        {"role": "assistant", "content": "{\"diet\": \"non-veg\", \"prep_time\": \"slow\", \"dish_type\": \"curry\"}"},
        {"role": "user", "content": "Recipe: Title: Onion Pakoda\nIntro: Fried snack.\nIngredients: Onions, chickpea flour, salt, oil. Time: 15 mins."},
        {"role": "assistant", "content": "{\"diet\": \"veg\", \"prep_time\": \"quick\", \"dish_type\": \"snack\"}"},
        {"role": "user", "content": f"Recipe: {truncated_text}"}
    ]

    # Generate the response
    outputs = generator(
        messages, 
        max_new_tokens=60, 
        temperature=0.01,  
        do_sample=False,
        # Llama 3 specific token adjustment to prevent endless generation
        pad_token_id=generator.tokenizer.eos_token_id
    )
    
    # The pipeline with messages appends the new text, so we grab the last content block
    raw_response = outputs[0]["generated_text"][-1]["content"]
    metadata = extract_json_from_response(raw_response)
    
    # Fallback and Schema sanitization
    if not metadata:
        metadata = {"diet": "unknown", "prep_time": "unknown", "dish_type": "unknown"}
        
    return {
        "diet": metadata.get("diet", "unknown"),
        "prep_time": metadata.get("prep_time", "unknown"),
        "dish_type": metadata.get("dish_type", "unknown")
    }

def main():
    # Kaggle paths
    # Remember to change 'your-dataset-name' to match your uploaded dataset directory!
    input_file = "/kaggle/input/datasets/mithilbaria/rag-dataset/south_asian_corpus_raw.json"
    output_file = "/kaggle/working/south_asian_corpus_enriched.json"

    print(f"Loading data from {input_file}...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            recipes = json.load(f)
    except FileNotFoundError:
        print(f"Error: {input_file} not found. Please check your Kaggle input directory path.")
        return

    enriched_recipes = []

    print(f"Processing {len(recipes)} recipes...")
    for recipe in tqdm(recipes):
        recipe_text = recipe.get("full_text", "") 
        
        if recipe_text:
            recipe["metadata"] = generate_metadata(recipe_text)
        
        enriched_recipes.append(recipe)
        
        # Save checkpoints every 25 recipes
        if len(enriched_recipes) % 25 == 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(enriched_recipes, f, indent=4)

    # Final save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(enriched_recipes, f, indent=4)
        
    print(f"\nSuccessfully saved enriched data to {output_file}")
    print("You can now download the file from the /kaggle/working/ directory on the right sidebar!")

if __name__ == "__main__":
    main()