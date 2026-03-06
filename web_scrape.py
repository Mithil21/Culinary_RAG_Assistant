import json
import difflib
import requests
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 1. CORE DATA MODEL (The DTO)
# ==========================================
class RecipeEntity:
    def __init__(self, dish_name: str):
        self.dish_name = dish_name
        self.cuisine_type = "South Asian"
        self.introductions = []
        self.ingredients = []
        self.instructions = []
        self.source_urls = set()

    def _is_duplicate(self, new_text: str, existing_list: list, threshold: float = 0.85) -> bool:
        """Checks for high semantic similarity to prevent redundant chunks."""
        if not new_text or not new_text.strip():
            return True
        for existing_text in existing_list:
            if difflib.SequenceMatcher(None, new_text, existing_text).ratio() > threshold:
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
# 2. DOMAIN-SPECIFIC SCRAPERS
# ==========================================
class BaseScraper:
    def __init__(self):
        # 1. Use a Session to persist connection pooling and look like a real client
        self.session = requests.Session()
        
        # 2. Configure comprehensive, polite headers
        self.session.headers.update({
            'User-Agent': 'SouthAsianRecipeBot/1.0 (Academic Research Project)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 3. Configure automatic retries with exponential backoff
        # If it hits a 403 or 429, it will wait 3s, then 6s, then 12s before trying again.
        retries = Retry(
            total=5,
            backoff_factor=3, 
            status_forcelist=[403, 429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def fetch_soup(self, url: str) -> BeautifulSoup:
        # Add a randomized delay (3 to 6 seconds) to avoid mechanical predictability
        sleep_time = random.uniform(3.0, 6.0)
        print(f"Polite delay: {sleep_time:.1f}s...")
        time.sleep(sleep_time)
        
        # Use the configured session with a 10-second timeout
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')

class WikipediaScraper(BaseScraper):
    def scrape(self, url: str, entity: RecipeEntity):
        soup = self.fetch_soup(url)
        parsed_url = urlparse(url)
        intro_paragraphs = []
        
        # 1. Handle fragment URLs (e.g., #Bangladeshi_cuisine)
        if parsed_url.fragment:
            heading_span = soup.find(id=parsed_url.fragment)
            if heading_span:
                parent_h = heading_span.parent
                # Walk through all siblings until the next major heading
                for sibling in parent_h.next_siblings:
                    if sibling.name in ['h2', 'h3']: 
                        break
                    if sibling.name == 'p':
                        text = sibling.get_text(strip=True)
                        if text: intro_paragraphs.append(text)
        
        # 2. Handle standard URLs (Top of the page introduction)
        else:
            content = soup.find(id="mw-content-text")
            if content:
                parser_output = content.find(class_="mw-parser-output")
                parent = parser_output if parser_output else content
                for element in parent.children:
                    if element.name == 'p':
                        text = element.get_text(strip=True)
                        if text: intro_paragraphs.append(text)
                    elif element.name in ['h2', 'h3']:
                        break
                        
        if intro_paragraphs:
            entity.add_introduction(" ".join(intro_paragraphs), url)

class WikibooksScraper(BaseScraper):
    def scrape(self, url: str, entity: RecipeEntity):
        soup = self.fetch_soup(url)
        content = soup.find(id="mw-content-text")
        if not content: return
        
        parser_output = content.find(class_="mw-parser-output")
        parent = parser_output if parser_output else content

        # State Machine Trackers
        current_mode = "intro"
        intro_content = []
        ingredients_content = []
        instructions_content = []

        # Read the page strictly top-to-bottom
        for element in parent.children:
            # Skip empty strings/newlines
            if isinstance(element, str):
                continue
                
            # 1. Handle Headings (Checking for the new mw-heading wrapper)
            is_heading = False
            heading_tag = None
            
            if element.name in ['h2', 'h3', 'h4']:
                is_heading = True
                heading_tag = element
            elif element.name == 'div' and element.has_attr('class') and any('mw-heading' in c for c in element.get('class', [])):
                is_heading = True
                # Extract the actual heading tag hidden inside the div
                heading_tag = element.find(['h2', 'h3', 'h4'])

            if is_heading and heading_tag:
                heading_text = heading_tag.get_text(strip=True).lower()
                
                # Check for major section changes (h2)
                if heading_tag.name == 'h2':
                    if 'ingredient' in heading_text or 'need' in heading_text:
                        current_mode = "ingredients"
                    elif any(w in heading_text for w in ['instruction', 'method', 'direction', 'preparation', 'procedure', 'step', 'cook']):
                        current_mode = "instructions"
                    elif 'reference' in heading_text or 'see also' in heading_text or 'note' in heading_text:
                        current_mode = "stop"
                    else:
                        current_mode = "ignore"
                
                # If we hit an h3 (like "Dough" or "Filling") WHILE in a section
                elif heading_tag.name == 'h3' and current_mode in ["ingredients", "instructions"]:
                    subheading = heading_tag.get_text(strip=True).replace('[edit]', '').replace('edit', '').strip()
                    if current_mode == "ingredients":
                        ingredients_content.append(f"\n--- {subheading} ---")
                    elif current_mode == "instructions":
                        instructions_content.append(f"\n--- {subheading} ---")

            # 2. Handle Lists
            elif element.name in ['ul', 'ol'] and current_mode != "ignore":
                if current_mode == "ingredients":
                    for li in element.find_all('li'):
                        ingredients_content.append(f"- {li.get_text(strip=True)}")
                elif current_mode == "instructions":
                    for i, li in enumerate(element.find_all('li')):
                        instructions_content.append(f"{i+1}. {li.get_text(strip=True)}")
                        
            # 3. Handle Paragraphs
            elif element.name == 'p' and current_mode != "ignore":
                text = element.get_text(strip=True)
                if text:
                    if current_mode == "intro":
                        intro_content.append(text)
                    elif current_mode == "ingredients":
                        ingredients_content.append(text)
                    elif current_mode == "instructions":
                        instructions_content.append(text)

        # 4. Save the data to the Entity
        if intro_content:
            entity.add_introduction(" ".join(intro_content), url)
        if ingredients_content:
            entity.add_ingredients("\n".join(ingredients_content).strip(), url)
        if instructions_content:
            entity.add_instructions("\n".join(instructions_content).strip(), url)

class BlogScraper(BaseScraper):
    def scrape(self, url: str, entity: RecipeEntity):
        # Placeholder for the "Around the World in 80 Cuisines" blog structure
        soup = self.fetch_soup(url)
        pass

# ==========================================
# 3. ORCHESTRATOR & CHUNKER
# ==========================================
class IngestionPipeline:
    def __init__(self):
        self.scrapers = {
            "en.wikipedia.org": WikipediaScraper(),
            "en.wikibooks.org": WikibooksScraper(),
            "aroundtheworldin80cuisinesblog.wordpress.com": BlogScraper()
        }
        self.database = {}

    def extract_dish_name(self, url: str) -> str:
        """Extracts a clean dish name, respecting URL fragments."""
        parsed_url = urlparse(url)
        if parsed_url.fragment:
            clean_name = requests.utils.unquote(parsed_url.fragment).replace('_', ' ')
        else:
            raw_name = parsed_url.path.split('/')[-1]
            clean_name = requests.utils.unquote(raw_name).replace('_', ' ').replace('Cookbook:', '')
        return clean_name.strip()

    def process_urls(self, urls: list):
        for url in urls:
            try:
                domain = urlparse(url).netloc
                dish_name = self.extract_dish_name(url)
                
                if dish_name not in self.database:
                    self.database[dish_name] = RecipeEntity(dish_name)
                entity = self.database[dish_name]

                if domain in self.scrapers:
                    print(f"Scraping {domain} for {dish_name}...")
                    self.scrapers[domain].scrape(url, entity)
                else:
                    print(f"Warning: No scraper configured for domain {domain}")
                    
            except Exception as e:
                print(f"Error processing {url}: {e}")

    def generate_json_chunks(self) -> list:
        chunks = []
        dish_counter = 1
        
        for dish_name, entity in self.database.items():
            dish_id_prefix = f"wiki_southasian_{dish_counter:03d}"
            chunk_counter = 1
            primary_url = list(entity.source_urls)[0] if entity.source_urls else ""

            for intro in entity.introductions:
                chunks.append(self._create_chunk_dict(dish_id_prefix, chunk_counter, intro, primary_url, entity, "Introduction"))
                chunk_counter += 1

            for ingredients in entity.ingredients:
                chunks.append(self._create_chunk_dict(dish_id_prefix, chunk_counter, f"Ingredients for {dish_name}:\n{ingredients}", primary_url, entity, "Ingredients"))
                chunk_counter += 1

            for instructions in entity.instructions:
                chunks.append(self._create_chunk_dict(dish_id_prefix, chunk_counter, f"Cooking Instructions for {dish_name}:\n{instructions}", primary_url, entity, "Instructions"))
                chunk_counter += 1
                
            dish_counter += 1
            
        return chunks

    def _create_chunk_dict(self, prefix, count, text, url, entity, content_type):
        return {
            "id": f"{prefix}_chunk_{count}",
            "text": text,
            "metadata": {
                "source_url": url,
                "cuisine_type": entity.cuisine_type,
                "dish_name": entity.dish_name,
                "content_type": content_type
            }
        }

# ==========================================
# 4. EXECUTION
# ==========================================
if __name__ == "__main__":
    target_links = [
        "https://en.wikipedia.org/wiki/South_Asian_cuisine",
        "https://en.wikipedia.org/wiki/South_Asian_cuisine#Bangladeshi_cuisine",
        "https://en.wikibooks.org/wiki/Cookbook:Arisa_Pitha_(Fried_Indian_Sweet_Rice_Pastry)",
        "https://en.wikibooks.org/wiki/Cookbook:Chyapa_Shutki_Bharta",
        "https://en.wikibooks.org/wiki/Cookbook:Bhuna_Khichuri_(Bengali_Rice_and_Lentils)",
        "https://en.wikibooks.org/wiki/Cookbook:Mishti_Doi_(Bengali_Sweetened_Yogurt)",
        "https://en.wikibooks.org/wiki/Cookbook:Murghi_Korma_(Chicken_Korma)",
        "https://en.wikibooks.org/wiki/Cookbook:Pudina_Hilsa_(Bengali_Fish_with_Mint)",
        "https://en.wikibooks.org/wiki/Cookbook:Rosogulla_(Bengali_Milk_Balls_in_Syrup)",
        "https://en.wikibooks.org/wiki/Cookbook:Afghan_Bread",
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Tikka",
        "https://en.wikibooks.org/wiki/Cookbook:Afghan_Bread",
        "https://en.wikibooks.org/wiki/Cookbook:Chicken_Tikka",
        "https://en.wikibooks.org/wiki/Cookbook:Naan",
        "https://en.wikipedia.org/wiki/Afghan_cuisine"
    ]

    pipeline = IngestionPipeline()
    pipeline.process_urls(target_links)
    
    final_dataset = pipeline.generate_json_chunks()
    
    with open('south_asian_corpus.json', 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully generated {len(final_dataset)} chunks and saved to south_asian_corpus.json")