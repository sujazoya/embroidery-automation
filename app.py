import os
import uuid
from flask import Flask, request, jsonify
from square.client import Client
from flask_cors import CORS

# The variable MUST be named 'app'
app = Flask(__name__)
CORS(app)

# Standard Health Check for Render
@app.route('/', methods=['GET'])
def home():
    return "Service is Live", 200

# Square Client Initialization
SQUARE_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN', 'MISSING')
client = Client(access_token=SQUARE_TOKEN, environment='production')

@app.route('/categories', methods=['GET'])
def get_categories():
    try:
        result = client.catalog.list_catalog(types='CATEGORY')
        if result.is_success():
            categories = [{"id": obj['id'], "name": obj['category_data']['name']} 
                          for obj in result.body.get('objects', [])]
            return jsonify(categories)
        return jsonify({"error": result.errors}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/parse', methods=['POST'])
def parse_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    return jsonify({
        "name": file.filename.split('.')[0],
        "description": "Stitches: 10,000\nFormat: .DST",
        "suggested_price": 10
    })

@app.route('/upload-to-square', methods=['POST'])
def upload():
    data = request.json
    item_body = {
        "idempotency_key": str(uuid.uuid4()),
        "object": {
            "type": "ITEM",
            "id": "#new_design",
            "item_data": {
                "name": data.get('name'),
                "description": data.get('description'),
                "category_id": data.get('category_id'),
                "variations": [{
                    "type": "ITEM_VARIATION",
                    "id": "#new_var",
                    "item_variation_data": {
                        "name": "Download",
                        "pricing_type": "FIXED_PRICING",
                        "price_money": {"amount": int(float(data.get('price', 10)) * 100), "currency": "USD"}
                    }
                }]
            }
        }
    }
    result = client.catalog.upsert_catalog_object(item_body)
    return jsonify(result.body if result.is_success() else result.errors)

if __name__ == '__main__':
    # Render requires binding to 0.0.0.0 and port 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
