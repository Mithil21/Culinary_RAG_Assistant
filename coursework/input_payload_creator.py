import json
import random

def generate_massive_benchmark(corpus_path="vector_ready_corpus.json", output_path="input_payload.json", target_size=500):
    print(f"Loading corpus from {corpus_path}...")
    
    try:
        with open(corpus_path, "r", encoding="utf-8") as f:
            corpus = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {corpus_path}.")
        return

    # 1. Extract unique dishes and their metadata
    dishes = {}
    for item in corpus:
        meta = item.get("metadata", {})
        dish_name = meta.get("dish_name")
        
        if not dish_name or dish_name == "Unknown Dish":
            continue
            
        if dish_name not in dishes:
            dishes[dish_name] = {
                "diet": meta.get("vegetarian", "no"),
                "quick": meta.get("quick", "no"),
                "flavor": meta.get("flavor", "unknown"),
                "dish_type": meta.get("dish_type", "unknown")
            }

    # 2. Hardcoded Edge-Case Queries (The traps)
    benchmark_data = [
        {"question": "How do I make pizza?", "expected_intent": "NON_SOUTH_ASIAN", "target_dish": ""},
        {"question": "I want sushi", "expected_intent": "NON_SOUTH_ASIAN", "target_dish": ""},
        {"question": "surprise me", "expected_intent": "VAGUE_REQUEST", "target_dish": ""},
        {"question": "what should i eat?", "expected_intent": "VAGUE_REQUEST", "target_dish": ""},
        {"question": "rice, lentils, turmeric", "expected_intent": "INGREDIENTS_ONLY", "target_dish": ""},
        {"question": "milk, sugar, cardamom", "expected_intent": "INGREDIENTS_ONLY", "target_dish": ""},
        {"question": "chicken, onion, tomato", "expected_intent": "INGREDIENTS_ONLY", "target_dish": ""},
    ]

    # 3. Dynamic Queries: Multiply by applying multiple templates to EVERY dish
    dynamic_queries = []
    
    dish_templates = [
        ("How do I make {dish}?", "RECIPE_REQUEST"),
        ("{dish} recipe", "DISH_QUERY"),
        ("What are the ingredients for {dish}?", "RECIPE_REQUEST"),
        ("I want to cook {dish}, how do I do it?", "RECIPE_REQUEST"),
        ("Can you teach me how to prepare {dish}?", "RECIPE_REQUEST")
    ]

    for dish_name, traits in dishes.items():
        clean_name = dish_name.split("(")[0].strip().replace("_", " ")
        
        # Apply every template to this dish
        for template, expected_intent in dish_templates:
            dynamic_queries.append({
                "question": template.format(dish=clean_name),
                "expected_intent": expected_intent,
                "target_dish": dish_name
            })
            
    # 4. Metadata Combination Queries (Testing the FAISS filters)
    # Generate variations of trait-based searches
    for _ in range(100): # Generate 100 random trait combinations
        diet = random.choice(["vegetarian", "non-vegetarian"])
        speed = random.choice(["quick", "slow-cooked", ""])
        flavor = random.choice(["spicy", "sweet", ""])
        
        # Build the question naturally
        traits_str = f"{speed} {flavor} {diet}".strip()
        traits_str = " ".join(traits_str.split()) # clean up extra spaces
        
        if traits_str:
            dynamic_queries.append({
                "question": f"Suggest a {traits_str} recipe",
                "expected_intent": "RECIPE_REQUEST",
                "target_dish": "" # Target is blank because multiple dishes could correctly match this
            })

    # 5. Shuffle all the generated dynamic queries
    random.shuffle(dynamic_queries)
    
    # Fill up the benchmark data until we hit the target size (500)
    needed_queries = target_size - len(benchmark_data)
    benchmark_data.extend(dynamic_queries[:needed_queries])

    # 6. Assign clean sequential IDs
    for i, item in enumerate(benchmark_data):
        item["query_id"] = f"q{(i+1):03d}" # Uses 001, 002 format

    # 7. Save to payload
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print(f"✅ Successfully generated {len(benchmark_data)} benchmark questions and saved to {output_path}!")

if __name__ == "__main__":
    generate_massive_benchmark(target_size=500)