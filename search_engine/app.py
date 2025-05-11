from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from elasticsearch import Elasticsearch
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import math

app = Flask(__name__)

mongo_client = MongoClient('mongodb://localhost:27017')
db = mongo_client['crawlingdata']
collection = db['pages']

es = Elasticsearch(['http://localhost:9200'], verify_certs=False)

def extract_image(html_content, meta=None):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    except:
        pass

    if meta:
        for item in meta:
            if isinstance(item, str) and item.startswith('http') and any(ext in item for ext in ['.jpg', '.png', '.jpeg']):
                return item

    return 'https://via.placeholder.com/100x80?text=No+Image'

def get_domain(url):
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')
    except:
        return 'unknown'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'web')
    page = int(request.args.get('page', 1))
    size = 10
    from_ = (page - 1) * size
    results = []

    if query:
        base_query = {
            "query": {
                "bool": {
                    "should": []
                }
            },
            "from": from_,
            "size": size
        }

        if search_type == 'images':
            base_query["query"]["bool"]["should"] = [
                {"match_phrase": {"meta": {"query": query, "boost": 2}}},
                {"match_phrase": {"content": {"query": query}}}
            ]
        else:
            base_query["query"]["bool"]["should"] = [
                {"match_phrase": {"title": {"query": query, "boost": 3}}},
                {"match_phrase": {"content": {"query": query, "boost": 2}}},
                {"match_phrase": {"meta": {"query": query, "boost": 1}}}
            ]

        es_results = es.search(index='webpages', body=base_query)
        grouped = {}

        for hit in es_results['hits']['hits']:
            source = hit['_source']
            domain = get_domain(source.get('url', ''))
            item = {
                'url': source.get('url'),
                'title': source.get('title'),
                'snippet': source.get('content', '')[:160],
                'image': extract_image(source.get('content', ''), source.get('meta', []))
            }
            grouped.setdefault(domain, []).append(item)

        for domain, items in grouped.items():
            results.append({'domain': domain, 'pages': items})

        total = es_results['hits']['total']['value']
        total_pages = math.ceil(total / size)

        return jsonify({
            'results': results,
            'pagination': {
                'current': page,
                'total_pages': total_pages
            }
        })

    return jsonify({'results': [], 'pagination': {'current': 1, 'total_pages': 1}})

if __name__ == '__main__':
    app.run(debug=True)
