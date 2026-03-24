# import json
# import difflib
# import requests
# import time
# import random
# import re
# from bs4 import BeautifulSoup, NavigableString, Tag
# from urllib.parse import urlparse, unquote
# from requests.adapters import HTTPAdapter
# from urllib3.util.retry import Retry

# # ==========================================
# # 1. CORE DATA MODEL
# # ==========================================
# class RecipeEntity:
#     def __init__(self, dish_name: str):
#         self.dish_name = dish_name
#         self.cuisine_type = "South Asian"
#         self.introductions = []
#         self.ingredients = []
#         self.instructions = []
#         self.source_urls = set()

#     def _is_duplicate(self, new_text: str, existing_list: list, threshold: float = 0.93) -> bool:
#         if not new_text or not new_text.strip():
#             return True

#         clean_new = normalize_text(new_text)
#         if len(clean_new) < 20:
#             return True

#         for existing_text in existing_list:
#             clean_existing = normalize_text(existing_text)
#             if difflib.SequenceMatcher(None, clean_new, clean_existing).ratio() > threshold:
#                 return True
#         return False

#     def add_introduction(self, text: str, url: str):
#         if not self._is_duplicate(text, self.introductions):
#             self.introductions.append(text.strip())
#             self.source_urls.add(url)

#     def add_ingredients(self, text: str, url: str):
#         if not self._is_duplicate(text, self.ingredients):
#             self.ingredients.append(text.strip())
#             self.source_urls.add(url)

#     def add_instructions(self, text: str, url: str):
#         if not self._is_duplicate(text, self.instructions):
#             self.instructions.append(text.strip())
#             self.source_urls.add(url)


# # ==========================================
# # 2. HELPERS
# # ==========================================
# JUNK_URL_PATTERNS = [
#     "action=edit",
#     "action=history",
#     "veaction=edit",
#     "printable=yes",
#     "oldid=",
#     "mobileaction=",
#     "Special:",
#     "Main_Page",
#     "WhatLinksHere",
#     "RecentChangesLinked",
#     "action=info",
#     "redlink=1",
# ]

# NON_RECIPE_TITLES = {
#     "Table of Contents",
#     "South Asian Cuisine",
#     "South Asian cuisines",
#     "Asian Cuisine",
#     "Cuisines",
#     "Recipes",
#     "Ingredients",
#     "Equipment",
#     "Cooking Techniques",
#     "Cuisine of India",
#     "Cuisine of Pakistan",
#     "Cuisine of Nepal",
#     "Cuisine of Afghanistan",
# }

# STOP_SECTION_WORDS = [
#     "reference", "references", "see also", "notes", "external links",
#     "gallery", "related", "navigation", "further reading"
# ]

# INGREDIENT_SECTION_WORDS = [
#     "ingredient", "ingredients", "what you need", "you will need", "needs"
# ]

# INSTRUCTION_SECTION_WORDS = [
#     "instruction", "instructions", "method", "methods", "direction",
#     "directions", "preparation", "procedure", "steps", "cooking", "methodology", "make"
# ]


# def normalize_text(text: str) -> str:
#     text = text.replace("\xa0", " ")
#     text = re.sub(r"\[\d+\]", "", text)
#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def extract_clean_text(node: Tag) -> str:
#     text = node.get_text(" ", strip=True)
#     return normalize_text(text)


# def is_junk_url(url: str) -> bool:
#     return any(p.lower() in url.lower() for p in JUNK_URL_PATTERNS)


# def looks_like_recipe_url(url: str) -> bool:
#     parsed = urlparse(url)
#     path = unquote(parsed.path)

#     if "en.wikibooks.org" not in parsed.netloc:
#         return False

#     if "/wiki/Cookbook:" not in path:
#         return False

#     return True


# def clean_dish_name_from_url(url: str) -> str:
#     parsed_url = urlparse(url)
#     if parsed_url.fragment:
#         name = unquote(parsed_url.fragment).replace("_", " ")
#     else:
#         raw_name = parsed_url.path.split("/")[-1]
#         name = unquote(raw_name).replace("_", " ").replace("Cookbook:", "")
#     return name.strip()


# def is_non_recipe_title(title: str) -> bool:
#     stripped = title.strip()
#     if stripped in NON_RECIPE_TITLES:
#         return True

#     lowered = stripped.lower()
#     if lowered.startswith("cuisine of "):
#         return True

#     return False


# def dedupe_urls(urls: list[str]) -> list[str]:
#     seen = set()
#     final = []
#     for url in urls:
#         clean = url.strip()
#         if not clean or clean in seen:
#             continue
#         seen.add(clean)
#         final.append(clean)
#     return final


# # ==========================================
# # 3. BASE SCRAPER
# # ==========================================
# class BaseScraper:
#     def __init__(self):
#         self.session = requests.Session()
#         self.session.headers.update({
#             "User-Agent": "SouthAsianRecipeBot/1.0 (Academic Research Project)",
#             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#             "Accept-Language": "en-US,en;q=0.5",
#             "Connection": "keep-alive",
#             "Upgrade-Insecure-Requests": "1",
#         })

#         retries = Retry(
#             total=4,
#             backoff_factor=2,
#             status_forcelist=[403, 429, 500, 502, 503, 504],
#             allowed_methods=["GET"],
#         )
#         adapter = HTTPAdapter(max_retries=retries)
#         self.session.mount("https://", adapter)
#         self.session.mount("http://", adapter)

#     def fetch_soup(self, url: str) -> BeautifulSoup:
#         sleep_time = random.uniform(1.5, 3.0)
#         print(f"Fetching: {url} | delay {sleep_time:.1f}s")
#         time.sleep(sleep_time)

#         response = self.session.get(url, timeout=20)
#         response.raise_for_status()
#         return BeautifulSoup(response.text, "html.parser")


# # ==========================================
# # 4. SCRAPERS
# # ==========================================
# class WikipediaScraper(BaseScraper):
#     def scrape(self, url: str, entity: RecipeEntity):
#         soup = self.fetch_soup(url)
#         parsed_url = urlparse(url)
#         intro_paragraphs = []

#         if parsed_url.fragment:
#             heading_span = soup.find(id=parsed_url.fragment)
#             if heading_span:
#                 parent_h = heading_span.parent
#                 for sibling in parent_h.next_siblings:
#                     if isinstance(sibling, Tag) and sibling.name in ["h2", "h3"]:
#                         break
#                     if isinstance(sibling, Tag) and sibling.name == "p":
#                         text = extract_clean_text(sibling)
#                         if text:
#                             intro_paragraphs.append(text)
#         else:
#             content = soup.find(id="mw-content-text")
#             if content:
#                 parser_output = content.find(class_="mw-parser-output")
#                 parent = parser_output if parser_output else content
#                 for element in parent.children:
#                     if isinstance(element, NavigableString):
#                         continue
#                     if element.name == "p":
#                         text = extract_clean_text(element)
#                         if text:
#                             intro_paragraphs.append(text)
#                     elif element.name in ["h2", "h3"]:
#                         break

#         if intro_paragraphs:
#             entity.add_introduction(" ".join(intro_paragraphs), url)


# class WikibooksScraper(BaseScraper):
#     def scrape(self, url: str, entity: RecipeEntity):
#         if is_junk_url(url):
#             print("Skipping junk/system URL")
#             return

#         soup = self.fetch_soup(url)
#         content = soup.find(id="mw-content-text")
#         if not content:
#             return

#         parser_output = content.find(class_="mw-parser-output")
#         parent = parser_output if parser_output else content

#         intro_parts = []
#         ingredient_parts = []
#         instruction_parts = []

#         current_section = "intro"

#         # iterate over direct children in order
#         for element in parent.children:
#             if isinstance(element, NavigableString):
#                 continue
#             if not isinstance(element, Tag):
#                 continue

#             heading = self._extract_heading_text(element)
#             if heading is not None:
#                 heading_lower = heading.lower()

#                 if any(word in heading_lower for word in STOP_SECTION_WORDS):
#                     break
#                 elif any(word in heading_lower for word in INGREDIENT_SECTION_WORDS):
#                     current_section = "ingredients"
#                     continue
#                 elif any(word in heading_lower for word in INSTRUCTION_SECTION_WORDS):
#                     current_section = "instructions"
#                     continue
#                 else:
#                     # do NOT switch to ignore forever
#                     # just continue and keep current section
#                     continue

#             block_texts = self._extract_block_content(element)

#             if not block_texts:
#                 continue

#             if current_section == "intro":
#                 intro_parts.extend(block_texts)
#             elif current_section == "ingredients":
#                 ingredient_parts.extend(block_texts)
#             elif current_section == "instructions":
#                 instruction_parts.extend(block_texts)

#         intro_text = "\n".join(intro_parts).strip()
#         ingredient_text = "\n".join(ingredient_parts).strip()
#         instruction_text = "\n".join(instruction_parts).strip()

#         # fallback heuristic: if nothing detected, try page-wide list extraction
#         if not ingredient_text and not instruction_text:
#             fallback_ing, fallback_inst = self._fallback_extract(parent)
#             if fallback_ing:
#                 ingredient_text = fallback_ing
#             if fallback_inst:
#                 instruction_text = fallback_inst

#         if intro_text:
#             entity.add_introduction(intro_text, url)
#         if ingredient_text:
#             entity.add_ingredients(ingredient_text, url)
#         if instruction_text:
#             entity.add_instructions(instruction_text, url)

#     def _extract_heading_text(self, element: Tag):
#         if element.name in ["h2", "h3", "h4", "h5"]:
#             return extract_clean_text(element).replace("[ edit ]", "").replace("[edit]", "")

#         if element.name == "div" and element.has_attr("class"):
#             classes = " ".join(element.get("class", []))
#             if "mw-heading" in classes:
#                 inner = element.find(["h2", "h3", "h4", "h5"])
#                 if inner:
#                     return extract_clean_text(inner).replace("[ edit ]", "").replace("[edit]", "")

#         return None

#     def _extract_block_content(self, element: Tag) -> list[str]:
#         output = []

#         # Paragraphs
#         if element.name == "p":
#             text = extract_clean_text(element)
#             if text:
#                 output.append(text)
#             return output

#         # Unordered or ordered lists
#         if element.name in ["ul", "ol"]:
#             for i, li in enumerate(element.find_all("li", recursive=False), start=1):
#                 li_text = extract_clean_text(li)
#                 if not li_text:
#                     continue
#                 if element.name == "ol":
#                     output.append(f"{i}. {li_text}")
#                 else:
#                     output.append(f"- {li_text}")
#             return output

#         # Tables sometimes hold recipe content
#         if element.name == "table":
#             rows = element.find_all("tr")
#             temp = []
#             for row in rows:
#                 cells = row.find_all(["td", "th"])
#                 row_text = " | ".join(extract_clean_text(c) for c in cells if extract_clean_text(c))
#                 if row_text:
#                     temp.append(row_text)
#             return temp

#         # Some pages wrap content in divs
#         if element.name == "div":
#             paragraphs = element.find_all("p", recursive=False)
#             lists = element.find_all(["ul", "ol"], recursive=False)

#             for p in paragraphs:
#                 text = extract_clean_text(p)
#                 if text:
#                     output.append(text)

#             for lst in lists:
#                 for i, li in enumerate(lst.find_all("li", recursive=False), start=1):
#                     li_text = extract_clean_text(li)
#                     if not li_text:
#                         continue
#                     if lst.name == "ol":
#                         output.append(f"{i}. {li_text}")
#                     else:
#                         output.append(f"- {li_text}")

#             return output

#         return output

#     def _fallback_extract(self, parent: Tag):
#         all_lists = parent.find_all(["ul", "ol"])
#         ingredient_lines = []
#         instruction_lines = []

#         for lst in all_lists:
#             items = [extract_clean_text(li) for li in lst.find_all("li")]
#             items = [x for x in items if x]
#             if not items:
#                 continue

#             # rough heuristic
#             numbered_like = 0
#             ingredient_like = 0

#             for item in items:
#                 if re.search(r"\b(cup|cups|tbsp|tsp|teaspoon|tablespoon|gram|grams|kg|ml|litre|liter)\b", item.lower()):
#                     ingredient_like += 1
#                 if re.search(r"\b(stir|add|mix|heat|boil|cook|serve|fry|bake|simmer)\b", item.lower()):
#                     numbered_like += 1

#             if ingredient_like >= max(2, len(items) // 3):
#                 ingredient_lines.extend([f"- {x}" for x in items])
#             elif numbered_like >= max(2, len(items) // 3):
#                 instruction_lines.extend([f"{i+1}. {x}" for i, x in enumerate(items)])

#         return "\n".join(ingredient_lines).strip(), "\n".join(instruction_lines).strip()


# class BlogScraper(BaseScraper):
#     def scrape(self, url: str, entity: RecipeEntity):
#         soup = self.fetch_soup(url)
#         # placeholder
#         pass


# # ==========================================
# # 5. ORCHESTRATOR
# # ==========================================
# class IngestionPipeline:
#     def __init__(self):
#         self.scrapers = {
#             "en.wikipedia.org": WikipediaScraper(),
#             "en.wikibooks.org": WikibooksScraper(),
#             "aroundtheworldin80cuisinesblog.wordpress.com": BlogScraper(),
#         }
#         self.database = {}

#     def extract_dish_name(self, url: str) -> str:
#         return clean_dish_name_from_url(url)

#     def should_process_url(self, url: str) -> bool:
#         if is_junk_url(url):
#             return False

#         dish_name = self.extract_dish_name(url)
#         if is_non_recipe_title(dish_name):
#             return False

#         parsed = urlparse(url)

#         if parsed.netloc == "en.wikibooks.org":
#             return looks_like_recipe_url(url)

#         if parsed.netloc == "en.wikipedia.org":
#             # allow only South Asian cuisine-type wiki pages if you really want them
#             return "South_Asian" in url or "South_Asian_cuisine" in url

#         return parsed.netloc in self.scrapers

#     def process_urls(self, urls: list[str]):
#         filtered_urls = dedupe_urls(urls)

#         kept = 0
#         skipped = 0

#         for url in filtered_urls:
#             if not self.should_process_url(url):
#                 print(f"Skipping non-recipe/junk URL: {url}")
#                 skipped += 1
#                 continue

#             try:
#                 domain = urlparse(url).netloc
#                 dish_name = self.extract_dish_name(url)

#                 if dish_name not in self.database:
#                     self.database[dish_name] = RecipeEntity(dish_name)
#                 entity = self.database[dish_name]

#                 scraper = self.scrapers.get(domain)
#                 if not scraper:
#                     print(f"Warning: no scraper configured for domain {domain}")
#                     skipped += 1
#                     continue

#                 print(f"Scraping {domain} -> {dish_name}")
#                 scraper.scrape(url, entity)
#                 kept += 1

#             except Exception as e:
#                 print(f"Error processing {url}: {e}")

#         print(f"\nProcessed URLs: {kept} | Skipped URLs: {skipped}")

#     def generate_json_chunks(self) -> list:
#         chunks = []
#         dish_counter = 1

#         for dish_name, entity in sorted(self.database.items()):
#             if not entity.introductions and not entity.ingredients and not entity.instructions:
#                 continue

#             dish_id_prefix = f"wiki_southasian_{dish_counter:03d}"
#             chunk_counter = 1
#             primary_url = next(iter(entity.source_urls), "")

#             for intro in entity.introductions:
#                 chunks.append(self._create_chunk_dict(
#                     dish_id_prefix, chunk_counter, intro, primary_url, entity, "Introduction"
#                 ))
#                 chunk_counter += 1

#             for ingredients in entity.ingredients:
#                 chunks.append(self._create_chunk_dict(
#                     dish_id_prefix, chunk_counter,
#                     f"Ingredients for {dish_name}:\n{ingredients}",
#                     primary_url, entity, "Ingredients"
#                 ))
#                 chunk_counter += 1

#             for instructions in entity.instructions:
#                 chunks.append(self._create_chunk_dict(
#                     dish_id_prefix, chunk_counter,
#                     f"Cooking Instructions for {dish_name}:\n{instructions}",
#                     primary_url, entity, "Instructions"
#                 ))
#                 chunk_counter += 1

#             dish_counter += 1

#         return chunks

#     def _create_chunk_dict(self, prefix, count, text, url, entity, content_type):
#         return {
#             "id": f"{prefix}_chunk_{count}",
#             "text": text,
#             "metadata": {
#                 "source_url": url,
#                 "cuisine_type": entity.cuisine_type,
#                 "dish_name": entity.dish_name,
#                 "content_type": content_type,
#             },
#         }


# # ==========================================
# # 6. EXECUTION
# # ==========================================
# if __name__ == "__main__":
#     target_links = [
#         # your URLs here
#         "https://en.wikibooks.org/wiki/Cookbook:Table_of_Contents", 
#         "https://en.wikibooks.org/wiki/Cookbook:South_Asian_Cuisine",
#         "https://en.wikibooks.org/w/index.php?title=Cookbook:South_Asian_Cuisine&action=edit", 
#         "https://en.wikibooks.org/w/index.php?title=Cookbook:South_Asian_Cuisine&action=history", 
#         "https://en.wikibooks.org/wiki/Special:WhatLinksHere/Cookbook:South_Asian_Cuisine", 
#         "https://en.wikibooks.org/wiki/Special:RecentChangesLinked/Cookbook:South_Asian_Cuisine",
#          "https://en.wikipedia.org/wiki/South_Asian_cuisine",
#             "https://en.wikibooks.org/wiki/Cookbook:Corom_Chatni_(Mango_Chutney_with_Hot_Chillies)", 
#             "https://en.wikibooks.org/wiki/Cookbook:Dum_ka_Qimah_(Spiced_Minced_Meat)", "https://en.wikibooks.org/wiki/Cookbook:Khatti_Dal_(Spiced_Tamarind_Pigeon_Peas)", "https://en.wikibooks.org/wiki/Cookbook:Malpua_(South_Asian_Sweet_Pancake)", "https://en.wikibooks.org/wiki/Cookbook:Mango_Chutney_(Chunky)", "https://en.wikibooks.org/wiki/Cookbook:Mango_Chutney_(Smooth)", "https://en.wikibooks.org/wiki/Cookbook:Masala_Chai_II", "https://en.wikibooks.org/wiki/Cookbook:Masyaura_(Nepali_Fermented_Vegetable_Balls)", "https://en.wikibooks.org/wiki/Cookbook:Mild_Salty_Lassi", "https://en.wikibooks.org/wiki/Cookbook:Papadam_(Black_Gram_Flatbread)", "https://en.wikibooks.org/wiki/Cookbook:Papaya_Lassi", "https://en.wikibooks.org/wiki/Cookbook:Papri_Chaat_(Crispy_Indian_Snack_with_Potato)", "https://en.wikibooks.org/wiki/Cookbook:Phulourie_(Split_Pea_Fritters)", "https://en.wikibooks.org/wiki/Cookbook:Prawn_Curry", "https://en.wikibooks.org/wiki/Cookbook:Qabuli_(Central_Asian_Rice_Pilaf)", "https://en.wikibooks.org/wiki/Cookbook:Seviyan_Ji_Khirni_(Sindhi_Vermicelli_Pudding)", "https://en.wikibooks.org/wiki/Cookbook:Sindhi_Fried_Potatoes", "https://en.wikibooks.org/wiki/Cookbook:Sweet_Lassi", "https://en.wikibooks.org/wiki/Cookbook:Sweet_Mango_Lassi", "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Doner_Kebab", "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Fried_Rice", "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Handesh", "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Rice_Pudding", "https://en.wikibooks.org/wiki/Cookbook:Watalappam_(Sri_Lankan_Coconut_Custard)", "https://en.wikibooks.org/w/index.php?title=Cookbook:South_Asian_Cuisine&mobileaction=toggle_view_mobile", "https://en.wikibooks.org/wiki/Cookbook:Cuisine_of_Afghanistan", "https://en.wikibooks.org/wiki/Cookbook:Afghan_Bread", "https://en.wikibooks.org/wiki/Cookbook:Chicken_Tikka", "https://en.wikibooks.org/wiki/Cookbook:Naan", "https://en.wikibooks.org/wiki/Cookbook:Recipes", "https://en.wikibooks.org/wiki/Cookbook:Ingredients", "https://en.wikibooks.org/wiki/Cookbook:Equipment", "https://en.wikibooks.org/wiki/Cookbook:Cooking_Techniques", "https://en.wikibooks.org/w/index.php?title=Cookbook:Cuisine_of_Bengal&action=edit&redlink=1", "https://en.wikibooks.org/wiki/Cookbook:Arisa_Pitha_(Fried_Indian_Sweet_Rice_Pastry)", "https://en.wikibooks.org/wiki/Cookbook:Chyapa_Shutki_Bharta", "https://en.wikibooks.org/wiki/Cookbook:Bhuna_Khichuri_(Bengali_Rice_and_Lentils)", "https://en.wikibooks.org/wiki/Cookbook:Mishti_Doi_(Bengali_Sweetened_Yogurt)", "https://en.wikibooks.org/wiki/Cookbook:Murghi_Korma_(Chicken_Korma)", "https://en.wikibooks.org/wiki/Cookbook:Pudina_Hilsa_(Bengali_Fish_with_Mint)", "https://en.wikibooks.org/wiki/Cookbook:Rosogulla_(Bengali_Milk_Balls_in_Syrup)", "https://en.wikibooks.org/wiki/Cookbook:Cuisine_of_India", "https://en.wikibooks.org/wiki/Cookbook:Potato_Curry_(Aloo_Masala)", "https://en.wikibooks.org/wiki/Cookbook:Baingan_Bartha_(South_Indian_Eggplant_with_Chili)_II", "https://en.wikibooks.org/wiki/Cookbook:Baingan_Bartha_(South_Indian_Eggplant_with_Coconut_and_Chili)_I", "https://en.wikibooks.org/wiki/Cookbook:Basic_Indian_Tomato_Gravy", "https://en.wikibooks.org/wiki/Cookbook:Bengal_Potatoes", "https://en.wikibooks.org/wiki/Cookbook:Bonda_(South_Indian_Vegetable_Fritter)", "https://en.wikibooks.org/wiki/Cookbook:Borhani_(Spiced_Yogurt_Drink)", "https://en.wikibooks.org/wiki/Cookbook:Bread_Filled_with_Potato_Curry_(Pani_Puri)", "https://en.wikibooks.org/wiki/Cookbook:Buttermilk_Curry_Soup_(Kadi_Pakora)", "https://en.wikibooks.org/wiki/Cookbook:Chakarai_Pongal_(Sweet_Rice_and_Black_Gram_Pudding)", "https://en.wikibooks.org/wiki/Cookbook:Chapati", "https://en.wikibooks.org/wiki/Cookbook:Chicken_Biryani", "https://en.wikibooks.org/wiki/Cookbook:Chicken_Curry", "https://en.wikibooks.org/wiki/Cookbook:Chicken_Curry_(Mediterranean-inspired)", "https://en.wikibooks.org/wiki/Cookbook:Chicken_Madras", "https://en.wikibooks.org/wiki/Cookbook:Chicken_Tikka_Masala", "https://en.wikibooks.org/wiki/Cookbook:Chicken_Vindaloo", "https://en.wikibooks.org/wiki/Cookbook:Chickpea_Curry_(Masaledaar_Chole)", "https://en.wikibooks.org/wiki/Cookbook:Cholley_(Chickpea_Curry)", "https://en.wikibooks.org/wiki/Cookbook:Churri_(Indian_Yogurt_Herb_Sauce)", "https://en.wikibooks.org/wiki/Cookbook:Coconut_Barfi", "https://en.wikibooks.org/wiki/Cookbook:Coconut_Chutney_(North_Indian)", "https://en.wikibooks.org/wiki/Cookbook:Coconut_Chutney_(South_Indian)", "https://en.wikibooks.org/wiki/Cookbook:Coriander_Chutney", "https://en.wikibooks.org/wiki/Cookbook:Curried_Chiles_(Mirchi_ka_Salan)", "https://en.wikibooks.org/wiki/Cookbook:Curry_Fried_Rice", "https://en.wikibooks.org/wiki/Cookbook:Dabeli_(Potato-stuffed_Buns_with_Chutney)", "https://en.wikibooks.org/wiki/Cookbook:Dahi_Baingana_(Fried_Eggplant_in_Yogurt)", "https://en.wikibooks.org/wiki/Cookbook:Dal_Makhani_(Black_Gram_with_Cream)", "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Chickpea_Dough_Balls_(Chyueeam)", "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Chickpea_Dough_Curry_Snacks_(Pakoda)", "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Chiles_Filled_with_Chickpea_Flour_(Mirchi_Bhajji)", "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Chiles_Stuffed_with_Potato_(Mirchi_Bada)", "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Lentil_Dough_Balls_(Punugu)", "https://en.wikibooks.org/wiki/Cookbook:Dharwad_Pedha_(Sweetened_Paneer_Cheese)", "https://en.wikibooks.org/wiki/Cookbook:Dhokla_(Steamed_Black_Gram_Bread)", "https://en.wikibooks.org/wiki/Cookbook:Hyderabadi_Fried_Bread_with_Syrup_and_Nuts_(Double_ka_meetha)", "https://en.wikibooks.org/wiki/Cookbook:Egg_Rice", "https://en.wikibooks.org/wiki/Cookbook:Egg_Roast", "https://en.wikibooks.org/wiki/Cookbook:Fried_Wheat_Bread_Balls_(Bhatoora)", "https://en.wikibooks.org/wiki/Cookbook:Gajjar_Halwa_(Carrot_Pudding)", "https://en.wikibooks.org/wiki/Cookbook:Ghevar_(Rajasthani_Honeycomb_Fritter)", "https://en.wikibooks.org/wiki/Cookbook:Green_Mango_and_Cumin_Drink_(Aam_Panna)", "https://en.wikibooks.org/wiki/Cookbook:Gulab_Jamun_(Fried_Milk_Balls_in_Syrup)", "https://en.wikibooks.org/wiki/Cookbook:Homemade_Paneer", "https://en.wikibooks.org/wiki/Cookbook:Hyderabad_Biryani", "https://en.wikibooks.org/wiki/Cookbook:Indian_Baked_Yoghurt_with_Saffron_and_Cardamom", "https://en.wikibooks.org/wiki/Cookbook:Indian_Beans", "https://en.wikibooks.org/wiki/Cookbook:Indian_Butter_Chicken_I", "https://en.wikibooks.org/wiki/Cookbook:Indian_Curry_Marinade", "https://en.wikibooks.org/wiki/Cookbook:Indian_Hard_Tack_(Baati)", "https://en.wikibooks.org/wiki/Cookbook:Indian_Moong_Dal", "https://en.wikibooks.org/wiki/Cookbook:Indian_Omelet", "https://en.wikibooks.org/wiki/Cookbook:Indian_Potatoes", "https://en.wikibooks.org/wiki/Cookbook:Indian_Rice", "https://en.wikibooks.org/wiki/Cookbook:Jal-jeera_(Cumin_Mango_Lemonade)", "https://en.wikibooks.org/wiki/Cookbook:Jalebi_(Fritters_in_Syrup)", "https://en.wikibooks.org/wiki/Cookbook:Jigarthanda_Milk", "https://en.wikibooks.org/wiki/Cookbook:Kaju_Barfi_(Indian_Cashew_Milk_Confection)", "https://en.wikibooks.org/wiki/Cookbook:Kal_Kals_(Sweet_Curled_Fritters)", "https://en.wikibooks.org/wiki/Cookbook:Kashmiri_Pulao", "https://en.wikibooks.org/wiki/Cookbook:Katchi_Biryani", "https://en.wikibooks.org/wiki/Cookbook:Kedgeree_(Rice_and_Smoked_Fish)", "https://en.wikibooks.org/wiki/Cookbook:Keralan_Prawns", "https://en.wikibooks.org/wiki/Cookbook:Keralan_Vegetable_Stew", "https://en.wikibooks.org/wiki/Cookbook:Khandvi_(Rolled_Chickpea_Noodles)", "https://en.wikibooks.org/wiki/Cookbook:Kheer_(Rice_Pudding)", "https://en.wikibooks.org/wiki/Cookbook:Khichdi_(South_Asian_Rice_and_Lentils)", "https://en.wikibooks.org/wiki/Cookbook:Khus_Khus_Halwa", "https://en.wikibooks.org/wiki/Cookbook:Kuddi_(Spiced_Yogurt_Sauce)", "https://en.wikibooks.org/wiki/Cookbook:Kulfi_(South_Asian_Frozen_Custard)", "https://en.wikibooks.org/wiki/Cookbook:Lemon_Pickle_I", "https://en.wikibooks.org/wiki/Cookbook:Lemon_Pickle_II", "https://en.wikibooks.org/wiki/Cookbook:Lemon_Rice", "https://en.wikibooks.org/wiki/Cookbook:Lentil,_Potato,_and_Tomato_Curry", "https://en.wikibooks.org/wiki/Cookbook:Madras_Filter_Coffee", "https://en.wikibooks.org/wiki/Cookbook:Maharashtrian_Baingan_Bartha_(South_Indian_Eggplant_with_Chili)", "https://en.wikibooks.org/wiki/Cookbook:Maharashtrian_Deep_Fried_Chickpea_Dough_Curry_Snacks_(Pakoda)", "https://en.wikibooks.org/wiki/Cookbook:Makki_di_Roti_(Indian_Cornmeal_Flatbread)", "https://en.wikibooks.org/wiki/Cookbook:Malai_Mixed_Vegetable_Curry", "https://en.wikibooks.org/wiki/Cookbook:Malvani_Chicken_Curry", "https://en.wikibooks.org/wiki/Cookbook:Mango_and_Coconut_Chutney_(Am_ki_Chatni)", "https://en.wikibooks.org/wiki/Cookbook:Mango_and_Yellow_Split_Pea_Curry", "https://en.wikibooks.org/wiki/Cookbook:Masala_Chai_I", "https://en.wikibooks.org/wiki/Cookbook:Matar_Paneer", "https://en.wikibooks.org/wiki/Cookbook:Medu_Vada_(South_Indian_Savory_Lentil_Donut)", "https://en.wikibooks.org/wiki/Cookbook:Murgh_Musallam_(Indian_Stewed_Spiced_Chicken)", "https://en.wikibooks.org/wiki/Cookbook:North_Indian_Fermented_Bread_(Batooru)", "https://en.wikibooks.org/wiki/Cookbook:Onion_Chutney", "https://en.wikibooks.org/wiki/Cookbook:Paneer_Butter_Masala", "https://en.wikibooks.org/wiki/Cookbook:Pear_Chutney", "https://en.wikibooks.org/wiki/Cookbook:Pickled_Green_Mango_(Aavakaaya)", "https://en.wikibooks.org/wiki/Cookbook:Pigeon_Pea_and_Fenugreek_Curry_(Methi_Tadka_Dal)", "https://en.wikibooks.org/wiki/Cookbook:Pohe_(Spiced_Flattened_Rice)", "https://en.wikibooks.org/wiki/Cookbook:Pork_Aachi", "https://en.wikibooks.org/wiki/Cookbook:Potato_and_Cauliflower_Curry_(Aloo_Gobi)", "https://en.wikibooks.org/wiki/Cookbook:Potato-Chickpea_Curry", "https://en.wikibooks.org/wiki/Cookbook:Puliyodarai_(South_Indian_Tamarind_Rice)", "https://en.wikibooks.org/wiki/Cookbook:Pulse_Chutney", "https://en.wikibooks.org/wiki/Cookbook:Puri_(Indian_Fried_Flatbread)", "https://en.wikibooks.org/wiki/Cookbook:Puttu_(Steamed_Rice_Flour_and_Coconut)", "https://en.wikibooks.org/wiki/Cookbook:Raita", "https://en.wikibooks.org/wiki/Cookbook:Rasam_(Tamarind_and_Tomato_Soup)", "https://en.wikibooks.org/wiki/Cookbook:Rasmalai_(Indian_Cheese_and_Milk_Dessert)", "https://en.wikibooks.org/wiki/Cookbook:Rava_Dosa_(Indian_Semolina_Pancake)", "https://en.wikibooks.org/wiki/Cookbook:Rice_Modak_(Coconut_Pastries)_I", "https://en.wikibooks.org/wiki/Cookbook:Rice_Modak_(Coconut_Pastries)_II", "https://en.wikibooks.org/wiki/Cookbook:Rice_with_Lemon_Coconut_and_Eggplant_(Vangibhat)", "https://en.wikibooks.org/wiki/Cookbook:Saffron_Rice", "https://en.wikibooks.org/wiki/Cookbook:Salty_(Namkin)_Lassi", "https://en.wikibooks.org/wiki/Cookbook:Sambar_I", "https://en.wikibooks.org/wiki/Cookbook:Sambar_III", "https://en.wikibooks.org/wiki/Cookbook:Samosa", "https://en.wikibooks.org/wiki/Cookbook:Sev_Puri_(Crispy_Indian_Snack_with_Potato)", "https://en.wikibooks.org/wiki/Cookbook:Sheer_Khurma", "https://en.wikibooks.org/wiki/Cookbook:Shirmal_(Persian_Saffron_Flatbread)", "https://en.wikibooks.org/wiki/Cookbook:Shrimp_Curry", "https://en.wikibooks.org/wiki/Cookbook:Soji_(Indian_Wheat_Pudding)", "https://en.wikibooks.org/wiki/Cookbook:South_Indian_Millet_Swallow_(Mudde)", "https://en.wikibooks.org/wiki/Cookbook:Spicy_Chilli_Chicken", "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Beef_Curry", "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Biryani", "https://en.wikibooks.org/wiki/Cookbook:Tadka_Dhal_(Spiced_Lentil_Curry)_I", "https://en.wikibooks.org/wiki/Cookbook:Tadka_Dhal_(Spiced_Lentil_Curry)_II", "https://en.wikibooks.org/wiki/Cookbook:Tamate_Ka_Kut_(Hyderabadi_Tomato_Curry)", "https://en.wikibooks.org/wiki/Cookbook:Tamil_Spice_Mix_(Milagai_Podi)", "https://en.wikibooks.org/wiki/Cookbook:Sambar_II_(Kerala/Tamil_style)", "https://en.wikibooks.org/wiki/Cookbook:Tandoori_Masala", "https://en.wikibooks.org/wiki/Cookbook:Tandoori_Tofu", "https://en.wikibooks.org/wiki/Cookbook:Thalassery_Biryani", "https://en.wikibooks.org/wiki/Cookbook:Traditional_Pilau_Rice", "https://en.wikibooks.org/wiki/Cookbook:Upeseru_(Indian_Lentils_with_Greens)", "https://en.wikibooks.org/wiki/Cookbook:Upma_(Indian_Semolina_Porridge)", "https://en.wikibooks.org/wiki/Cookbook:Uppittu_(Indian_Semolina_Porridge)", "https://en.wikibooks.org/wiki/Cookbook:Vedhmi_(Sweet_Stuffed_Flatbread)", "https://en.wikibooks.org/wiki/Cookbook:Wheat_Modak_(Coconut_Pastries)", "https://en.wikibooks.org/wiki/Cookbook:Yogurt_Curry_Soup_(Kadhi)", "https://en.wikibooks.org/wiki/Cookbook:Cuisine_of_Nepal", "https://en.wikibooks.org/wiki/Cookbook:Chukauni_(Nepalese_Potato_Salad)", "https://en.wikibooks.org/wiki/Cookbook:Jhilinga_(Nepalese_Rice_Fritters)", "https://en.wikibooks.org/wiki/Cookbook:Tibetan_Meat_Momos", "https://en.wikibooks.org/wiki/Cookbook:Cuisine_of_Pakistan", "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Onion_and_Rice_Fritters", "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Tangy_Curry", "https://en.wikibooks.org/wiki/Cookbook:South_Asian_cuisines", "https://en.wikibooks.org/wiki/Cookbook:Butter_Tea", "https://en.wikibooks.org/wiki/Cookbook:Chicken_Tikka", "https://en.wikibooks.org/wiki/Cookbook:Fried_Wheat_Bread_Balls_(Bhatoora)", "https://en.wikibooks.org/wiki/Cookbook:Potato_and_Cauliflower_Curry_(Aloo_Gobi)", "https://en.wikibooks.org/wiki/Cookbook:Salty_(Namkin)_Lassi", "https://en.wikibooks.org/wiki/Cookbook:Tandoori_Masala", "https://en.wikibooks.org/wiki/Cookbook:Appam_(Fermented_Rice_Pancake)", "https://en.wikibooks.org/wiki/Cookbook:Bonda_(South_Indian_Vegetable_Fritter)", "https://en.wikibooks.org/wiki/Cookbook:Hyderabad_Biryani", "https://en.wikibooks.org/wiki/Cookbook:Hyderabadi_Fried_Bread_with_Syrup_and_Nuts_(Double_ka_meetha)", "https://en.wikibooks.org/wiki/Cookbook:Idiyappam_(South_Indian_Rice_Noodles)", "https://en.wikibooks.org/wiki/Cookbook:Idli_(Steamed_Rice_and_Black_Gram_Bread)", "https://en.wikibooks.org/wiki/Cookbook:Kesari_(South_Indian_Semolina_Pudding)", "https://en.wikibooks.org/wiki/Cookbook:Khara_Pongal_(Rice_and_Mung_Bean_Porridge)", "https://en.wikibooks.org/wiki/Cookbook:Ragi_Dosa_(South_Indian_Millet_and_Rice_Pancake)", "https://en.wikibooks.org/wiki/Cookbook:Tamate_Ka_Kut_(Hyderabadi_Tomato_Curry)",
#     ]

#     pipeline = IngestionPipeline()
#     pipeline.process_urls(target_links)

#     final_dataset = pipeline.generate_json_chunks()

#     with open("south_asian_corpus.json", "w", encoding="utf-8") as f:
#         json.dump(final_dataset, f, indent=2, ensure_ascii=False)

#     print(f"Successfully generated {len(final_dataset)} documents and saved to south_asian_corpus.json")

import json
import difflib
import requests
import time
import random
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urlparse, unquote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 1. CORE DATA MODEL
# ==========================================
class RecipeEntity:
    def __init__(self, dish_name: str):
        self.dish_name = dish_name
        self.cuisine_type = "South Asian"
        self.introductions = []
        self.ingredients = []
        self.instructions = []
        self.source_urls = set()

    def _is_duplicate(self, new_text: str, existing_list: list, threshold: float = 0.93) -> bool:
        if not new_text or not new_text.strip():
            return True

        clean_new = normalize_text(new_text)
        if len(clean_new) < 20:
            return True

        for existing_text in existing_list:
            clean_existing = normalize_text(existing_text)
            if difflib.SequenceMatcher(None, clean_new, clean_existing).ratio() > threshold:
                return True
        return False

    def add_introduction(self, text: str, url: str):
        if not self._is_duplicate(text, self.introductions):
            self.introductions.append(text.strip())
            self.source_urls.add(url)

    def add_ingredients(self, text: str, url: str):
        if not self._is_duplicate(text, self.ingredients):
            self.ingredients.append(text.strip())
            self.source_urls.add(url)

    def add_instructions(self, text: str, url: str):
        if not self._is_duplicate(text, self.instructions):
            self.instructions.append(text.strip())
            self.source_urls.add(url)


# ==========================================
# 2. HELPERS
# ==========================================
JUNK_URL_PATTERNS = [
    "action=edit", "action=history", "veaction=edit", "printable=yes",
    "oldid=", "mobileaction=", "Special:", "Main_Page", "WhatLinksHere",
    "RecentChangesLinked", "action=info", "redlink=1",
]

NON_RECIPE_TITLES = {
    "Table of Contents", "South Asian Cuisine", "South Asian cuisines",
    "Asian Cuisine", "Cuisines", "Recipes", "Ingredients", "Equipment",
    "Cooking Techniques", "Cuisine of India", "Cuisine of Pakistan",
    "Cuisine of Nepal", "Cuisine of Afghanistan",
}

STOP_SECTION_WORDS = [
    "reference", "references", "see also", "notes", "external links",
    "gallery", "related", "navigation", "further reading"
]

INGREDIENT_SECTION_WORDS = [
    "ingredient", "ingredients", "what you need", "you will need", "needs"
]

INSTRUCTION_SECTION_WORDS = [
    "instruction", "instructions", "method", "methods", "direction",
    "directions", "preparation", "procedure", "steps", "cooking", "methodology", "make"
]


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_clean_text(node: Tag) -> str:
    text = node.get_text(" ", strip=True)
    return normalize_text(text)


def is_junk_url(url: str) -> bool:
    return any(p.lower() in url.lower() for p in JUNK_URL_PATTERNS)


def looks_like_recipe_url(url: str) -> bool:
    parsed = urlparse(url)
    path = unquote(parsed.path)

    if "en.wikibooks.org" not in parsed.netloc:
        return False

    if "/wiki/Cookbook:" not in path:
        return False

    return True


def clean_dish_name_from_url(url: str) -> str:
    parsed_url = urlparse(url)
    if parsed_url.fragment:
        name = unquote(parsed_url.fragment).replace("_", " ")
    else:
        raw_name = parsed_url.path.split("/")[-1]
        name = unquote(raw_name).replace("_", " ").replace("Cookbook:", "")
    return name.strip()


def is_non_recipe_title(title: str) -> bool:
    stripped = title.strip()
    if stripped in NON_RECIPE_TITLES:
        return True

    lowered = stripped.lower()
    if lowered.startswith("cuisine of "):
        return True

    return False


def dedupe_urls(urls: list[str]) -> list[str]:
    seen = set()
    final = []
    for url in urls:
        clean = url.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        final.append(clean)
    return final


# ==========================================
# 3. BASE SCRAPER
# ==========================================
class BaseScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SouthAsianRecipeBot/1.0 (Academic Research Project)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        retries = Retry(
            total=4,
            backoff_factor=2,
            status_forcelist=[403, 429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def fetch_soup(self, url: str) -> BeautifulSoup:
        sleep_time = random.uniform(1.5, 3.0)
        print(f"Fetching: {url} | delay {sleep_time:.1f}s")
        time.sleep(sleep_time)

        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")


# ==========================================
# 4. SCRAPERS
# ==========================================
class WikipediaScraper(BaseScraper):
    def scrape(self, url: str, entity: RecipeEntity):
        soup = self.fetch_soup(url)
        parsed_url = urlparse(url)
        intro_paragraphs = []

        if parsed_url.fragment:
            heading_span = soup.find(id=parsed_url.fragment)
            if heading_span:
                parent_h = heading_span.parent
                for sibling in parent_h.next_siblings:
                    if isinstance(sibling, Tag) and sibling.name in ["h2", "h3"]:
                        break
                    if isinstance(sibling, Tag) and sibling.name == "p":
                        text = extract_clean_text(sibling)
                        if text:
                            intro_paragraphs.append(text)
        else:
            content = soup.find(id="mw-content-text")
            if content:
                parser_output = content.find(class_="mw-parser-output")
                parent = parser_output if parser_output else content
                for element in parent.children:
                    if isinstance(element, NavigableString):
                        continue
                    if element.name == "p":
                        text = extract_clean_text(element)
                        if text:
                            intro_paragraphs.append(text)
                    elif element.name in ["h2", "h3"]:
                        break

        if intro_paragraphs:
            entity.add_introduction(" ".join(intro_paragraphs), url)


class WikibooksScraper(BaseScraper):
    def scrape(self, url: str, entity: RecipeEntity):
        if is_junk_url(url):
            print("Skipping junk/system URL")
            return

        soup = self.fetch_soup(url)
        content = soup.find(id="mw-content-text")
        if not content:
            return

        parser_output = content.find(class_="mw-parser-output")
        parent = parser_output if parser_output else content

        intro_parts = []
        ingredient_parts = []
        instruction_parts = []

        current_section = "intro"

        # iterate over direct children in order
        for element in parent.children:
            if isinstance(element, NavigableString):
                continue
            if not isinstance(element, Tag):
                continue

            heading = self._extract_heading_text(element)
            if heading is not None:
                heading_lower = heading.lower()

                if any(word in heading_lower for word in STOP_SECTION_WORDS):
                    break
                elif any(word in heading_lower for word in INGREDIENT_SECTION_WORDS):
                    current_section = "ingredients"
                    continue
                elif any(word in heading_lower for word in INSTRUCTION_SECTION_WORDS):
                    current_section = "instructions"
                    continue
                else:
                    continue

            block_texts = self._extract_block_content(element)

            if not block_texts:
                continue

            if current_section == "intro":
                intro_parts.extend(block_texts)
            elif current_section == "ingredients":
                ingredient_parts.extend(block_texts)
            elif current_section == "instructions":
                instruction_parts.extend(block_texts)

        intro_text = "\n".join(intro_parts).strip()
        ingredient_text = "\n".join(ingredient_parts).strip()
        instruction_text = "\n".join(instruction_parts).strip()

        # fallback heuristic: if nothing detected, try page-wide list extraction
        if not ingredient_text and not instruction_text:
            fallback_ing, fallback_inst = self._fallback_extract(parent)
            if fallback_ing:
                ingredient_text = fallback_ing
            if fallback_inst:
                instruction_text = fallback_inst

        if intro_text:
            entity.add_introduction(intro_text, url)
        if ingredient_text:
            entity.add_ingredients(ingredient_text, url)
        if instruction_text:
            entity.add_instructions(instruction_text, url)

    def _extract_heading_text(self, element: Tag):
        if element.name in ["h2", "h3", "h4", "h5"]:
            return extract_clean_text(element).replace("[ edit ]", "").replace("[edit]", "")

        if element.name == "div" and element.has_attr("class"):
            classes = " ".join(element.get("class", []))
            if "mw-heading" in classes:
                inner = element.find(["h2", "h3", "h4", "h5"])
                if inner:
                    return extract_clean_text(inner).replace("[ edit ]", "").replace("[edit]", "")

        return None

    def _extract_block_content(self, element: Tag) -> list[str]:
        output = []

        # Paragraphs
        if element.name == "p":
            text = extract_clean_text(element)
            if text:
                output.append(text)
            return output

        # Unordered or ordered lists
        if element.name in ["ul", "ol"]:
            for i, li in enumerate(element.find_all("li", recursive=False), start=1):
                li_text = extract_clean_text(li)
                if not li_text:
                    continue
                if element.name == "ol":
                    output.append(f"{i}. {li_text}")
                else:
                    output.append(f"- {li_text}")
            return output

        # Tables sometimes hold recipe content
        if element.name == "table":
            rows = element.find_all("tr")
            temp = []
            for row in rows:
                cells = row.find_all(["td", "th"])
                row_text = " | ".join(extract_clean_text(c) for c in cells if extract_clean_text(c))
                if row_text:
                    temp.append(row_text)
            return temp

        # Some pages wrap content in divs
        if element.name == "div":
            paragraphs = element.find_all("p", recursive=False)
            lists = element.find_all(["ul", "ol"], recursive=False)

            for p in paragraphs:
                text = extract_clean_text(p)
                if text:
                    output.append(text)

            for lst in lists:
                for i, li in enumerate(lst.find_all("li", recursive=False), start=1):
                    li_text = extract_clean_text(li)
                    if not li_text:
                        continue
                    if lst.name == "ol":
                        output.append(f"{i}. {li_text}")
                    else:
                        output.append(f"- {li_text}")

            return output

        return output

    def _fallback_extract(self, parent: Tag):
        all_lists = parent.find_all(["ul", "ol"])
        ingredient_lines = []
        instruction_lines = []

        for lst in all_lists:
            items = [extract_clean_text(li) for li in lst.find_all("li")]
            items = [x for x in items if x]
            if not items:
                continue

            # rough heuristic
            numbered_like = 0
            ingredient_like = 0

            for item in items:
                if re.search(r"\b(cup|cups|tbsp|tsp|teaspoon|tablespoon|gram|grams|kg|ml|litre|liter)\b", item.lower()):
                    ingredient_like += 1
                if re.search(r"\b(stir|add|mix|heat|boil|cook|serve|fry|bake|simmer)\b", item.lower()):
                    numbered_like += 1

            if ingredient_like >= max(2, len(items) // 3):
                ingredient_lines.extend([f"- {x}" for x in items])
            elif numbered_like >= max(2, len(items) // 3):
                instruction_lines.extend([f"{i+1}. {x}" for i, x in enumerate(items)])

        return "\n".join(ingredient_lines).strip(), "\n".join(instruction_lines).strip()


class BlogScraper(BaseScraper):
    def scrape(self, url: str, entity: RecipeEntity):
        soup = self.fetch_soup(url)
        # placeholder
        pass


# ==========================================
# 5. ORCHESTRATOR
# ==========================================
class IngestionPipeline:
    def __init__(self):
        self.scrapers = {
            "en.wikipedia.org": WikipediaScraper(),
            "en.wikibooks.org": WikibooksScraper(),
            "aroundtheworldin80cuisinesblog.wordpress.com": BlogScraper(),
        }
        self.database = {}

    def extract_dish_name(self, url: str) -> str:
        return clean_dish_name_from_url(url)

    def should_process_url(self, url: str) -> bool:
        if is_junk_url(url):
            return False

        dish_name = self.extract_dish_name(url)
        if is_non_recipe_title(dish_name):
            return False

        parsed = urlparse(url)

        if parsed.netloc == "en.wikibooks.org":
            return looks_like_recipe_url(url)

        if parsed.netloc == "en.wikipedia.org":
            return "South_Asian" in url or "South_Asian_cuisine" in url

        return parsed.netloc in self.scrapers

    def process_urls(self, urls: list[str]):
        filtered_urls = dedupe_urls(urls)

        kept = 0
        skipped = 0

        for url in filtered_urls:
            if not self.should_process_url(url):
                print(f"Skipping non-recipe/junk URL: {url}")
                skipped += 1
                continue

            try:
                domain = urlparse(url).netloc
                dish_name = self.extract_dish_name(url)

                if dish_name not in self.database:
                    self.database[dish_name] = RecipeEntity(dish_name)
                entity = self.database[dish_name]

                scraper = self.scrapers.get(domain)
                if not scraper:
                    print(f"Warning: no scraper configured for domain {domain}")
                    skipped += 1
                    continue

                print(f"Scraping {domain} -> {dish_name}")
                scraper.scrape(url, entity)
                kept += 1

            except Exception as e:
                print(f"Error processing {url}: {e}")

        print(f"\nProcessed URLs: {kept} | Skipped URLs: {skipped}")

    # ==========================================
    # MODIFIED: Output a single document per dish
    # ==========================================
    def generate_consolidated_json(self) -> list:
        documents = []
        dish_counter = 1

        for dish_name, entity in sorted(self.database.items()):
            # Skip if we didn't extract any meaningful recipe content
            if not entity.introductions and not entity.ingredients and not entity.instructions:
                continue

            dish_id = f"wiki_southasian_{dish_counter:03d}"
            primary_url = next(iter(entity.source_urls), "")

            # Combine everything into a single text block
            full_text_parts = [f"Title: {dish_name}\n"]
            
            if entity.introductions:
                full_text_parts.append("--- Introduction ---")
                full_text_parts.extend(entity.introductions)
            
            if entity.ingredients:
                full_text_parts.append("\n--- Ingredients ---")
                full_text_parts.extend(entity.ingredients)
                
            if entity.instructions:
                full_text_parts.append("\n--- Instructions ---")
                full_text_parts.extend(entity.instructions)

            full_text = "\n".join(full_text_parts).strip()

            # Create ONE document containing the entire recipe
            documents.append({
                "id": dish_id,
                "source_url": primary_url,
                "title": dish_name,
                "cuisine_type": entity.cuisine_type,
                "full_text": full_text,
                # Blank template ready for the LLM enrichment script
                "metadata": {
                    "diet": "",
                    "prep_time": "",
                    "dish_type": ""
                }
            })
            dish_counter += 1

        return documents


# ==========================================
# 6. EXECUTION
# ==========================================
if __name__ == "__main__":
    target_links = [
        "https://en.wikibooks.org/wiki/Cookbook:Table_of_Contents", 
        "https://en.wikibooks.org/wiki/Cookbook:South_Asian_Cuisine",
        "https://en.wikibooks.org/w/index.php?title=Cookbook:South_Asian_Cuisine&action=edit", 
        "https://en.wikibooks.org/w/index.php?title=Cookbook:South_Asian_Cuisine&action=history", 
        "https://en.wikibooks.org/wiki/Special:WhatLinksHere/Cookbook:South_Asian_Cuisine", 
        "https://en.wikibooks.org/wiki/Special:RecentChangesLinked/Cookbook:South_Asian_Cuisine",
        "https://en.wikipedia.org/wiki/South_Asian_cuisine",
        "https://en.wikibooks.org/wiki/Cookbook:Corom_Chatni_(Mango_Chutney_with_Hot_Chillies)", 
        "https://en.wikibooks.org/wiki/Cookbook:Dum_ka_Qimah_(Spiced_Minced_Meat)", 
        "https://en.wikibooks.org/wiki/Cookbook:Khatti_Dal_(Spiced_Tamarind_Pigeon_Peas)", 
        "https://en.wikibooks.org/wiki/Cookbook:Malpua_(South_Asian_Sweet_Pancake)", 
        "https://en.wikibooks.org/wiki/Cookbook:Mango_Chutney_(Chunky)", 
        "https://en.wikibooks.org/wiki/Cookbook:Mango_Chutney_(Smooth)", 
        "https://en.wikibooks.org/wiki/Cookbook:Masala_Chai_II", 
        "https://en.wikibooks.org/wiki/Cookbook:Masyaura_(Nepali_Fermented_Vegetable_Balls)", 
        "https://en.wikibooks.org/wiki/Cookbook:Mild_Salty_Lassi", 
        "https://en.wikibooks.org/wiki/Cookbook:Papadam_(Black_Gram_Flatbread)", 
        "https://en.wikibooks.org/wiki/Cookbook:Papaya_Lassi", 
        "https://en.wikibooks.org/wiki/Cookbook:Papri_Chaat_(Crispy_Indian_Snack_with_Potato)", 
        "https://en.wikibooks.org/wiki/Cookbook:Phulourie_(Split_Pea_Fritters)", 
        "https://en.wikibooks.org/wiki/Cookbook:Prawn_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Qabuli_(Central_Asian_Rice_Pilaf)", 
        "https://en.wikibooks.org/wiki/Cookbook:Seviyan_Ji_Khirni_(Sindhi_Vermicelli_Pudding)", 
        "https://en.wikibooks.org/wiki/Cookbook:Sindhi_Fried_Potatoes", 
        "https://en.wikibooks.org/wiki/Cookbook:Sweet_Lassi", 
        "https://en.wikibooks.org/wiki/Cookbook:Sweet_Mango_Lassi", 
        "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Doner_Kebab", 
        "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Fried_Rice", 
        "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Handesh", 
        "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Rice_Pudding", 
        "https://en.wikibooks.org/wiki/Cookbook:Watalappam_(Sri_Lankan_Coconut_Custard)", 
        "https://en.wikibooks.org/w/index.php?title=Cookbook:South_Asian_Cuisine&mobileaction=toggle_view_mobile", 
        "https://en.wikibooks.org/wiki/Cookbook:Cuisine_of_Afghanistan", 
        "https://en.wikibooks.org/wiki/Cookbook:Afghan_Bread", 
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Tikka", 
        "https://en.wikibooks.org/wiki/Cookbook:Naan", 
        "https://en.wikibooks.org/wiki/Cookbook:Recipes", 
        "https://en.wikibooks.org/wiki/Cookbook:Ingredients", 
        "https://en.wikibooks.org/wiki/Cookbook:Equipment", 
        "https://en.wikibooks.org/wiki/Cookbook:Cooking_Techniques", 
        "https://en.wikibooks.org/w/index.php?title=Cookbook:Cuisine_of_Bengal&action=edit&redlink=1", 
        "https://en.wikibooks.org/wiki/Cookbook:Arisa_Pitha_(Fried_Indian_Sweet_Rice_Pastry)", 
        "https://en.wikibooks.org/wiki/Cookbook:Chyapa_Shutki_Bharta", 
        "https://en.wikibooks.org/wiki/Cookbook:Bhuna_Khichuri_(Bengali_Rice_and_Lentils)", 
        "https://en.wikibooks.org/wiki/Cookbook:Mishti_Doi_(Bengali_Sweetened_Yogurt)", 
        "https://en.wikibooks.org/wiki/Cookbook:Murghi_Korma_(Chicken_Korma)", 
        "https://en.wikibooks.org/wiki/Cookbook:Pudina_Hilsa_(Bengali_Fish_with_Mint)", 
        "https://en.wikibooks.org/wiki/Cookbook:Rosogulla_(Bengali_Milk_Balls_in_Syrup)", 
        "https://en.wikibooks.org/wiki/Cookbook:Cuisine_of_India", 
        "https://en.wikibooks.org/wiki/Cookbook:Potato_Curry_(Aloo_Masala)", 
        "https://en.wikibooks.org/wiki/Cookbook:Baingan_Bartha_(South_Indian_Eggplant_with_Chili)_II", 
        "https://en.wikibooks.org/wiki/Cookbook:Baingan_Bartha_(South_Indian_Eggplant_with_Coconut_and_Chili)_I", 
        "https://en.wikibooks.org/wiki/Cookbook:Basic_Indian_Tomato_Gravy", 
        "https://en.wikibooks.org/wiki/Cookbook:Bengal_Potatoes", 
        "https://en.wikibooks.org/wiki/Cookbook:Bonda_(South_Indian_Vegetable_Fritter)", 
        "https://en.wikibooks.org/wiki/Cookbook:Borhani_(Spiced_Yogurt_Drink)", 
        "https://en.wikibooks.org/wiki/Cookbook:Bread_Filled_with_Potato_Curry_(Pani_Puri)", 
        "https://en.wikibooks.org/wiki/Cookbook:Buttermilk_Curry_Soup_(Kadi_Pakora)", 
        "https://en.wikibooks.org/wiki/Cookbook:Chakarai_Pongal_(Sweet_Rice_and_Black_Gram_Pudding)", 
        "https://en.wikibooks.org/wiki/Cookbook:Chapati", 
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Biryani", 
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Curry_(Mediterranean-inspired)", 
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Madras", 
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Tikka_Masala", 
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Vindaloo", 
        "https://en.wikibooks.org/wiki/Cookbook:Chickpea_Curry_(Masaledaar_Chole)", 
        "https://en.wikibooks.org/wiki/Cookbook:Cholley_(Chickpea_Curry)", 
        "https://en.wikibooks.org/wiki/Cookbook:Churri_(Indian_Yogurt_Herb_Sauce)", 
        "https://en.wikibooks.org/wiki/Cookbook:Coconut_Barfi", 
        "https://en.wikibooks.org/wiki/Cookbook:Coconut_Chutney_(North_Indian)", 
        "https://en.wikibooks.org/wiki/Cookbook:Coconut_Chutney_(South_Indian)", 
        "https://en.wikibooks.org/wiki/Cookbook:Coriander_Chutney", 
        "https://en.wikibooks.org/wiki/Cookbook:Curried_Chiles_(Mirchi_ka_Salan)", 
        "https://en.wikibooks.org/wiki/Cookbook:Curry_Fried_Rice", 
        "https://en.wikibooks.org/wiki/Cookbook:Dabeli_(Potato-stuffed_Buns_with_Chutney)", 
        "https://en.wikibooks.org/wiki/Cookbook:Dahi_Baingana_(Fried_Eggplant_in_Yogurt)", 
        "https://en.wikibooks.org/wiki/Cookbook:Dal_Makhani_(Black_Gram_with_Cream)", 
        "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Chickpea_Dough_Balls_(Chyueeam)", 
        "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Chickpea_Dough_Curry_Snacks_(Pakoda)", 
        "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Chiles_Filled_with_Chickpea_Flour_(Mirchi_Bhajji)", 
        "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Chiles_Stuffed_with_Potato_(Mirchi_Bada)", 
        "https://en.wikibooks.org/wiki/Cookbook:Deep_Fried_Lentil_Dough_Balls_(Punugu)", 
        "https://en.wikibooks.org/wiki/Cookbook:Dharwad_Pedha_(Sweetened_Paneer_Cheese)", 
        "https://en.wikibooks.org/wiki/Cookbook:Dhokla_(Steamed_Black_Gram_Bread)", 
        "https://en.wikibooks.org/wiki/Cookbook:Hyderabadi_Fried_Bread_with_Syrup_and_Nuts_(Double_ka_meetha)", 
        "https://en.wikibooks.org/wiki/Cookbook:Egg_Rice", 
        "https://en.wikibooks.org/wiki/Cookbook:Egg_Roast", 
        "https://en.wikibooks.org/wiki/Cookbook:Fried_Wheat_Bread_Balls_(Bhatoora)", 
        "https://en.wikibooks.org/wiki/Cookbook:Gajjar_Halwa_(Carrot_Pudding)", 
        "https://en.wikibooks.org/wiki/Cookbook:Ghevar_(Rajasthani_Honeycomb_Fritter)", 
        "https://en.wikibooks.org/wiki/Cookbook:Green_Mango_and_Cumin_Drink_(Aam_Panna)", 
        "https://en.wikibooks.org/wiki/Cookbook:Gulab_Jamun_(Fried_Milk_Balls_in_Syrup)", 
        "https://en.wikibooks.org/wiki/Cookbook:Homemade_Paneer", 
        "https://en.wikibooks.org/wiki/Cookbook:Hyderabad_Biryani", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Baked_Yoghurt_with_Saffron_and_Cardamom", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Beans", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Butter_Chicken_I", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Curry_Marinade", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Hard_Tack_(Baati)", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Moong_Dal", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Omelet", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Potatoes", 
        "https://en.wikibooks.org/wiki/Cookbook:Indian_Rice", 
        "https://en.wikibooks.org/wiki/Cookbook:Jal-jeera_(Cumin_Mango_Lemonade)", 
        "https://en.wikibooks.org/wiki/Cookbook:Jalebi_(Fritters_in_Syrup)", 
        "https://en.wikibooks.org/wiki/Cookbook:Jigarthanda_Milk", 
        "https://en.wikibooks.org/wiki/Cookbook:Kaju_Barfi_(Indian_Cashew_Milk_Confection)", 
        "https://en.wikibooks.org/wiki/Cookbook:Kal_Kals_(Sweet_Curled_Fritters)", 
        "https://en.wikibooks.org/wiki/Cookbook:Kashmiri_Pulao", 
        "https://en.wikibooks.org/wiki/Cookbook:Katchi_Biryani", 
        "https://en.wikibooks.org/wiki/Cookbook:Kedgeree_(Rice_and_Smoked_Fish)", 
        "https://en.wikibooks.org/wiki/Cookbook:Keralan_Prawns", 
        "https://en.wikibooks.org/wiki/Cookbook:Keralan_Vegetable_Stew", 
        "https://en.wikibooks.org/wiki/Cookbook:Khandvi_(Rolled_Chickpea_Noodles)", 
        "https://en.wikibooks.org/wiki/Cookbook:Kheer_(Rice_Pudding)", 
        "https://en.wikibooks.org/wiki/Cookbook:Khichdi_(South_Asian_Rice_and_Lentils)", 
        "https://en.wikibooks.org/wiki/Cookbook:Khus_Khus_Halwa", 
        "https://en.wikibooks.org/wiki/Cookbook:Kuddi_(Spiced_Yogurt_Sauce)", 
        "https://en.wikibooks.org/wiki/Cookbook:Kulfi_(South_Asian_Frozen_Custard)", 
        "https://en.wikibooks.org/wiki/Cookbook:Lemon_Pickle_I", 
        "https://en.wikibooks.org/wiki/Cookbook:Lemon_Pickle_II", 
        "https://en.wikibooks.org/wiki/Cookbook:Lemon_Rice", 
        "https://en.wikibooks.org/wiki/Cookbook:Lentil,_Potato,_and_Tomato_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Madras_Filter_Coffee", 
        "https://en.wikibooks.org/wiki/Cookbook:Maharashtrian_Baingan_Bartha_(South_Indian_Eggplant_with_Chili)", 
        "https://en.wikibooks.org/wiki/Cookbook:Maharashtrian_Deep_Fried_Chickpea_Dough_Curry_Snacks_(Pakoda)", 
        "https://en.wikibooks.org/wiki/Cookbook:Makki_di_Roti_(Indian_Cornmeal_Flatbread)", 
        "https://en.wikibooks.org/wiki/Cookbook:Malai_Mixed_Vegetable_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Malvani_Chicken_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Mango_and_Coconut_Chutney_(Am_ki_Chatni)", 
        "https://en.wikibooks.org/wiki/Cookbook:Mango_and_Yellow_Split_Pea_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Masala_Chai_I", 
        "https://en.wikibooks.org/wiki/Cookbook:Matar_Paneer", 
        "https://en.wikibooks.org/wiki/Cookbook:Medu_Vada_(South_Indian_Savory_Lentil_Donut)", 
        "https://en.wikibooks.org/wiki/Cookbook:Murgh_Musallam_(Indian_Stewed_Spiced_Chicken)", 
        "https://en.wikibooks.org/wiki/Cookbook:North_Indian_Fermented_Bread_(Batooru)", 
        "https://en.wikibooks.org/wiki/Cookbook:Onion_Chutney", 
        "https://en.wikibooks.org/wiki/Cookbook:Paneer_Butter_Masala", 
        "https://en.wikibooks.org/wiki/Cookbook:Pear_Chutney", 
        "https://en.wikibooks.org/wiki/Cookbook:Pickled_Green_Mango_(Aavakaaya)", 
        "https://en.wikibooks.org/wiki/Cookbook:Pigeon_Pea_and_Fenugreek_Curry_(Methi_Tadka_Dal)", 
        "https://en.wikibooks.org/wiki/Cookbook:Pohe_(Spiced_Flattened_Rice)", 
        "https://en.wikibooks.org/wiki/Cookbook:Pork_Aachi", 
        "https://en.wikibooks.org/wiki/Cookbook:Potato_and_Cauliflower_Curry_(Aloo_Gobi)", 
        "https://en.wikibooks.org/wiki/Cookbook:Potato-Chickpea_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Puliyodarai_(South_Indian_Tamarind_Rice)", 
        "https://en.wikibooks.org/wiki/Cookbook:Pulse_Chutney", 
        "https://en.wikibooks.org/wiki/Cookbook:Puri_(Indian_Fried_Flatbread)", 
        "https://en.wikibooks.org/wiki/Cookbook:Puttu_(Steamed_Rice_Flour_and_Coconut)", 
        "https://en.wikibooks.org/wiki/Cookbook:Raita", 
        "https://en.wikibooks.org/wiki/Cookbook:Rasam_(Tamarind_and_Tomato_Soup)", 
        "https://en.wikibooks.org/wiki/Cookbook:Rasmalai_(Indian_Cheese_and_Milk_Dessert)", 
        "https://en.wikibooks.org/wiki/Cookbook:Rava_Dosa_(Indian_Semolina_Pancake)", 
        "https://en.wikibooks.org/wiki/Cookbook:Rice_Modak_(Coconut_Pastries)_I", 
        "https://en.wikibooks.org/wiki/Cookbook:Rice_Modak_(Coconut_Pastries)_II", 
        "https://en.wikibooks.org/wiki/Cookbook:Rice_with_Lemon_Coconut_and_Eggplant_(Vangibhat)", 
        "https://en.wikibooks.org/wiki/Cookbook:Saffron_Rice", 
        "https://en.wikibooks.org/wiki/Cookbook:Salty_(Namkin)_Lassi", 
        "https://en.wikibooks.org/wiki/Cookbook:Sambar_I", 
        "https://en.wikibooks.org/wiki/Cookbook:Sambar_III", 
        "https://en.wikibooks.org/wiki/Cookbook:Samosa", 
        "https://en.wikibooks.org/wiki/Cookbook:Sev_Puri_(Crispy_Indian_Snack_with_Potato)", 
        "https://en.wikibooks.org/wiki/Cookbook:Sheer_Khurma", 
        "https://en.wikibooks.org/wiki/Cookbook:Shirmal_(Persian_Saffron_Flatbread)", 
        "https://en.wikibooks.org/wiki/Cookbook:Shrimp_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Soji_(Indian_Wheat_Pudding)", 
        "https://en.wikibooks.org/wiki/Cookbook:South_Indian_Millet_Swallow_(Mudde)", 
        "https://en.wikibooks.org/wiki/Cookbook:Spicy_Chilli_Chicken", 
        "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Beef_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Biryani", 
        "https://en.wikibooks.org/wiki/Cookbook:Tadka_Dhal_(Spiced_Lentil_Curry)_I", 
        "https://en.wikibooks.org/wiki/Cookbook:Tadka_Dhal_(Spiced_Lentil_Curry)_II", 
        "https://en.wikibooks.org/wiki/Cookbook:Tamate_Ka_Kut_(Hyderabadi_Tomato_Curry)", 
        "https://en.wikibooks.org/wiki/Cookbook:Tamil_Spice_Mix_(Milagai_Podi)", 
        "https://en.wikibooks.org/wiki/Cookbook:Sambar_II_(Kerala/Tamil_style)", 
        "https://en.wikibooks.org/wiki/Cookbook:Tandoori_Masala", 
        "https://en.wikibooks.org/wiki/Cookbook:Tandoori_Tofu", 
        "https://en.wikibooks.org/wiki/Cookbook:Thalassery_Biryani", 
        "https://en.wikibooks.org/wiki/Cookbook:Traditional_Pilau_Rice", 
        "https://en.wikibooks.org/wiki/Cookbook:Upeseru_(Indian_Lentils_with_Greens)", 
        "https://en.wikibooks.org/wiki/Cookbook:Upma_(Indian_Semolina_Porridge)", 
        "https://en.wikibooks.org/wiki/Cookbook:Uppittu_(Indian_Semolina_Porridge)", 
        "https://en.wikibooks.org/wiki/Cookbook:Vedhmi_(Sweet_Stuffed_Flatbread)", 
        "https://en.wikibooks.org/wiki/Cookbook:Wheat_Modak_(Coconut_Pastries)", 
        "https://en.wikibooks.org/wiki/Cookbook:Yogurt_Curry_Soup_(Kadhi)", 
        "https://en.wikibooks.org/wiki/Cookbook:Cuisine_of_Nepal", 
        "https://en.wikibooks.org/wiki/Cookbook:Chukauni_(Nepalese_Potato_Salad)", 
        "https://en.wikibooks.org/wiki/Cookbook:Jhilinga_(Nepalese_Rice_Fritters)", 
        "https://en.wikibooks.org/wiki/Cookbook:Tibetan_Meat_Momos", 
        "https://en.wikibooks.org/wiki/Cookbook:Cuisine_of_Pakistan", 
        "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Onion_and_Rice_Fritters", 
        "https://en.wikibooks.org/wiki/Cookbook:Sylheti_Tangy_Curry", 
        "https://en.wikibooks.org/wiki/Cookbook:South_Asian_cuisines", 
        "https://en.wikibooks.org/wiki/Cookbook:Butter_Tea", 
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Tikka", 
        "https://en.wikibooks.org/wiki/Cookbook:Fried_Wheat_Bread_Balls_(Bhatoora)", 
        "https://en.wikibooks.org/wiki/Cookbook:Potato_and_Cauliflower_Curry_(Aloo_Gobi)", 
        "https://en.wikibooks.org/wiki/Cookbook:Salty_(Namkin)_Lassi", 
        "https://en.wikibooks.org/wiki/Cookbook:Tandoori_Masala", 
        "https://en.wikibooks.org/wiki/Cookbook:Appam_(Fermented_Rice_Pancake)", 
        "https://en.wikibooks.org/wiki/Cookbook:Bonda_(South_Indian_Vegetable_Fritter)", 
        "https://en.wikibooks.org/wiki/Cookbook:Hyderabad_Biryani", 
        "https://en.wikibooks.org/wiki/Cookbook:Hyderabadi_Fried_Bread_with_Syrup_and_Nuts_(Double_ka_meetha)", 
        "https://en.wikibooks.org/wiki/Cookbook:Idiyappam_(South_Indian_Rice_Noodles)", 
        "https://en.wikibooks.org/wiki/Cookbook:Idli_(Steamed_Rice_and_Black_Gram_Bread)", 
        "https://en.wikibooks.org/wiki/Cookbook:Kesari_(South_Indian_Semolina_Pudding)", 
        "https://en.wikibooks.org/wiki/Cookbook:Khara_Pongal_(Rice_and_Mung_Bean_Porridge)", 
        "https://en.wikibooks.org/wiki/Cookbook:Ragi_Dosa_(South_Indian_Millet_and_Rice_Pancake)", 
        "https://en.wikibooks.org/wiki/Cookbook:Tamate_Ka_Kut_(Hyderabadi_Tomato_Curry)",
    ]

    pipeline = IngestionPipeline()
    pipeline.process_urls(target_links)

    # Use the new consolidated JSON method
    final_dataset = pipeline.generate_consolidated_json()

    # Save to the raw file name so the LLM script knows what to pick up
    with open("south_asian_corpus_raw.json", "w", encoding="utf-8") as f:
        json.dump(final_dataset, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated {len(final_dataset)} consolidated recipes and saved to south_asian_corpus_raw.json")