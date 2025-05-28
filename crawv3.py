import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from pymongo import MongoClient
from elasticsearch import Elasticsearch
import hashlib

# Configuration
MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'crawlingdata'
ES_HOST = 'http://localhost:9200'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

#halooo
# Initialize clients
mongo_client = MongoClient(MONGO_URI)
es_client = Elasticsearch([ES_HOST], verify_certs=False)

visited_urls = set()
content_hashes = set()

# Utilities
def get_domain(url):
    parsed = urlparse(url)
    return parsed.netloc.replace('www.', '')

def is_relevant_link(base_url, target_url):
    base_domain = get_domain(base_url)
    target_domain = get_domain(target_url)
    return (target_domain == base_domain or target_domain.endswith(f".{base_domain}"))

def hash_content(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

# Database and Indexing
def store_in_mongo(page_data):
    db = mongo_client[DB_NAME]
    collection = db['pages']
    if collection.find_one({'url': page_data['url']}) is None:
        collection.insert_one(page_data)
        print(f'Stored in MongoDB: {page_data["url"]}')

def index_in_elasticsearch(page_data):
    es_data = {
        'url': page_data['url'],
        'title': page_data['title'],
        'content': page_data['content'],
        'meta': page_data['meta'],
        'domain': get_domain(page_data['url']),
    }
    if not es_client.exists(index='webpages', id=page_data['url']):
        es_client.index(index='webpages', document=es_data, id=page_data['url'])
        print(f"Indexed in Elasticsearch: {page_data['url']}")

# Crawling logic
def crawl(url, depth=0, max_depth=2, root_keyword=None):
    if url in visited_urls or depth > max_depth:
        return
    try:
        print(f'Crawling: {url}')
        visited_urls.add(url)
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        text_content = ' '.join([p.get_text() for p in soup.find_all('p')]).strip()

        # Skip empty or duplicate content
        content_hash = hash_content(text_content)
        if not text_content or content_hash in content_hashes:
            return
        content_hashes.add(content_hash)

        page_data = {
            'url': url,
            'title': soup.title.string if soup.title else '',
            'content': text_content,
            'meta': [meta.get('content') for meta in soup.find_all('meta') if meta.get('content')]
        }

        store_in_mongo(page_data)
        index_in_elasticsearch(page_data)

        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)
            if full_url.startswith('http') and is_relevant_link(url, full_url):
                crawl(full_url, depth + 1, max_depth, root_keyword)
    except Exception as e:
        print(f'Error crawling {url}: {e}')

# Bing Search
def get_bing_links(keyword):
    print(f"Searching Bing for: {keyword}")
    search_url = f"https://www.bing.com/search?q={keyword}"
    try:
        response = requests.get(search_url, headers=HEADERS)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        for li in soup.find_all('li', {'class': 'b_algo'}):
            a_tag = li.find('a')
            if a_tag and a_tag['href'].startswith('http'):
                links.append(a_tag['href'])
        return links
    except Exception as e:
        print(f"Error fetching Bing results: {e}")
        return []

# Start from keywords
def start_from_keywords(file_path='key.txt'):
    try:
        with open(file_path, 'r') as f:
            keywords = [line.strip() for line in f if line.strip()]
        for keyword in keywords:
            links = get_bing_links(keyword)
            for link in links:
                crawl(link, depth=0, max_depth=2, root_keyword=keyword)
    except FileNotFoundError:
        print("Keyword file not found.")
    except Exception as e:
        print(f"Error reading keywords: {e}")

# Main
if __name__ == '__main__':
    start_from_keywords('key.txt')
