from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from elasticsearch import Elasticsearch
from bs4 import BeautifulSoup

app = Flask(__name__)

mongo_client = MongoClient('mongodb://localhost:27017')
db = mongo_client['webdata']
collection = db['pages']

es = Elasticsearch(['http://localhost:9200'], verify_certs=False)

def extract_image(html_content, meta=None):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    except Exception as e:
        print(f"extract_image HTML error: {e}")

    if meta:
        for item in meta:
            if isinstance(item, str) and item.startswith('http') and ('.jpg' in item or '.png' in item or '.jpeg' in item):
                return item

    return 'https://via.placeholder.com/100x80?text=No+Image'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'web')
    results = []

    if query:
        es_query = {
            "query": {
                "bool": {
                    "should": [
                        {"match_phrase": {"title": {"query": query, "boost": 3}}},
                        {"match_phrase": {"content": {"query": query, "boost": 2}}},
                        {"match_phrase": {"meta": {"query": query, "boost": 1}}}
                    ]
                }
            },
            "size": 50  # lebih banyak hasil
        }

        if search_type == 'images':
            es_query["query"]["bool"]["should"] = [
                {"match_phrase": {"meta": {"query": query, "boost": 2}}},
                {"match_phrase": {"content": {"query": query}}}
            ]

        es_results = es.search(index='webpages', body=es_query)
        for hit in es_results['hits']['hits']:
            source = hit['_source']
            results.append({
                'url': source.get('url'),
                'title': source.get('title'),
                'snippet': source.get('content', '')[:150],
                'image': extract_image(source.get('content', ''), source.get('meta', []))
            })

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)
