import os
import uuid
from flask import Flask, request, jsonify
from square.client import Client
from flask_cors import CORS

# This variable MUST be named exactly 'app'
app = Flask(__name__)
CORS(app)

# Fetch token from Environment Variables
SQUARE_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN', 'MISSING')

# Initialize Square Client
client = Client(
    access_token=SQUARE_TOKEN,
    environment='production'
)

@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "online", "token_set": SQUARE_TOKEN != 'MISSING'}), 200

@app.route('/categories', methods=['GET'])
def get_categories():
    try:
        result = client.catalog.list_catalog(types='CATEGORY')
        if result.is_success():
            objs = result.body.get('objects', [])
            categories = [{"id": o['id'], "name": o['category_data']['name']} for o in objs]
            return jsonify(categories)
        return jsonify({"error": "Square API Error", "details": result.errors}), 400
    except Exception as e:
        return jsonify({"error": "Server Error", "message": str(e)}), 500

@app.route('/parse', methods=['POST'])
def parse_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    return jsonify({
        "name": file.filename.split('.')[0] if '.' in file.filename else file.filename,
        "description": "Parsed Embroidery Design\nFormat: .DST\nStitches: 10,000",
        "suggested_price": 10.00
    })

@app.route('/upload-to-square', methods=['POST'])
def upload_to_square():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    try:
        item_body = {
            "idempotency_key": str(uuid.uuid4()),
            "object": {
                "type": "ITEM",
                "id": "#new_design",
                "item_data": {
                    "name": data.get('name', 'Untitled Design'),
                    "description": data.get('description', ''),
                    "category_id": data.get('category_id'),
                    "variations": [{
                        "type": "ITEM_VARIATION",
                        "id": "#new_var",
                        "item_variation_data": {
                            "name": "Digital Download",
                            "pricing_type": "FIXED_PRICING",
                            "price_money": {
                                "amount": int(float(data.get('price', 10)) * 100),
                                "currency": "USD"
                            }
                        }
                    }]
                }
            }
        }
        result = client.catalog.upsert_catalog_object(item_body)
        if result.is_success():
            return jsonify({"status": "Success", "item": result.body})
        return jsonify({"status": "Error", "message": result.errors}), 400
    except Exception as e:
        return jsonify({"error": "Upload Failed", "message": str(e)}), 500

if __name__ == '__main__':
    # Render requires binding to 0.0.0.0 and port 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
