import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from elasticsearch import Elasticsearch
import time

# Configuration
MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'webdata'
ES_HOST = 'http://localhost:9200'
HEADERS = {'User-Agent': 'Mozilla/5.0'}  # Agar tidak ditolak Google

# Initialize clients
mongo_client = MongoClient(MONGO_URI)
es_client = Elasticsearch([ES_HOST], verify_certs=False)

visited_urls = set()

# Check Elasticsearch connection
def check_elasticsearch_connection():
    try:
        if es_client.ping():
            print("Connected to Elasticsearch!")
        else:
            print("Elasticsearch is down!")
    except Exception as e:
        print(f"Error connecting to Elasticsearch: {e}")

# Store in MongoDB
def store_in_mongo(page_data):
    try:
        db = mongo_client[DB_NAME]
        collection = db['pages']
        if collection.find_one({'url': page_data['url']}) is None:
            collection.insert_one(page_data)
            print(f'Stored in MongoDB: {page_data["url"]}')
    except Exception as e:
        print(f'MongoDB error: {e}')

# Index in Elasticsearch
def index_in_elasticsearch(page_data):
    try:
        es_data = {
            'url': page_data['url'],
            'title': page_data['title'] or '',
            'content': page_data['content'] or '',
            'meta': page_data['meta'] or []
        }
        if not es_client.exists(index='webpages', id=page_data['url']):
            es_client.index(index='webpages', document=es_data, id=page_data['url'])
            print(f"Indexed in Elasticsearch: {page_data['url']}")
    except Exception as e:
        print(f"Elasticsearch error: {e}")

# Crawl a URL recursively
def crawl(url, depth=0, max_depth=2):
    if url in visited_urls or depth > max_depth:
        return
    try:
        print(f'Crawling: {url}')
        visited_urls.add(url)
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        page_data = {
            'url': url,
            'title': soup.title.string if soup.title else '',
            'content': soup.get_text(),
            'meta': [meta.get('content') for meta in soup.find_all('meta') if meta.get('content')]
        }
        store_in_mongo(page_data)
        index_in_elasticsearch(page_data)

        # Crawl inner links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('http'):
                crawl(href, depth + 1, max_depth)
    except Exception as e:
        print(f'Error crawling {url}: {e}')

# Get links from Google Search results
# Get links from Bing Search results
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


# Read keywords from file and start crawling
def start_from_keywords(file_path='keyword.txt'):
    try:
        with open(file_path, 'r') as f:
            keywords = [line.strip() for line in f if line.strip()]
        for keyword in keywords:
            links = get_bing_links(keyword)
            for link in links:
                crawl(link)
                time.sleep(1)  # Delay to avoid getting blocked
    except FileNotFoundError:
        print("Keyword file not found.")
    except Exception as e:
        print(f"Error reading keywords: {e}")

# Main
if __name__ == '__main__':
    check_elasticsearch_connection()
    start_from_keywords('keyword.txt')
