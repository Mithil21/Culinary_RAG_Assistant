# Author: Mithil Baria
import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://en.wikibooks.org"
START_URL = "https://en.wikibooks.org/wiki/Cookbook:South_Asian_Cuisine"

HEADERS = {
    "User-Agent": "Mithil-Recipe-Scraper/1.0 (research project; contact: mithil@example.com)"
}

def get_soup(url):
    """Fetch page with delay to avoid 403"""
    time.sleep(2)  # IMPORTANT: Respect Wikimedia limits
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        print(f"Skipping {url} -> {r.status_code}")
        return None

    return BeautifulSoup(r.text, "html.parser")


def full_url(href):
    if not href or href.startswith("#"):
        return None
    return urljoin(BASE_URL, href)


def scrape():

    soup = get_soup(START_URL)
    if soup is None:
        return

    target_links = []
    category_links = []

    # Extract links from main page
    for a in soup.select("a[href]"):

        url = full_url(a["href"])
        if not url:
            continue

        if "Category:" in url and "recipes" in url.lower():
            category_links.append(url)

        elif (
            "Cookbook:" in url
            or "wikipedia.org/wiki" in url
        ):
            target_links.append(url)

    # Visit category pages
    for cat in category_links:

        cat_soup = get_soup(cat)
        if cat_soup is None:
            continue

        for a in cat_soup.select("a[href]"):
            url = full_url(a["href"])

            if url and "Cookbook:" in url:
                target_links.append(url)

    # Remove duplicates (optional)
    target_links = list(dict.fromkeys(target_links))

    print("target_links = [")
    for link in target_links:
        print(f'    "{link}",')
    print("]")

    return target_links


scrape()