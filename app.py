import os
import uuid
from flask import Flask, request, jsonify
from square.client import Client
from flask_cors import CORS

# Initialize Flask - The variable MUST be named 'app' for Gunicorn
app = Flask(__name__)
CORS(app)

# Fetch token from Render Environment Variables
SQUARE_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN')

# Initialize Square Client
# This setup prevents a crash even if the token is temporarily missing
client = Client(
    access_token=SQUARE_TOKEN if SQUARE_TOKEN else "MISSING",
    environment='production' 
)

@app.route('/', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "token_detected": bool(SQUARE_TOKEN)
    }), 200

@app.route('/categories', methods=['GET'])
def get_categories():
    try:
        result = client.catalog.list_catalog(types='CATEGORY')
        if result.is_success():
            categories = [{"id": obj['id'], "name": obj['category_data']['name']} 
                          for obj in result.body.get('objects', [])]
            return jsonify(categories)
        return jsonify({"error": "Square API Error", "details": result.errors}), 400
    except Exception as e:
        return jsonify({"error": "Server Exception", "message": str(e)}), 500

@app.route('/parse', methods=['POST'])
def parse_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    # Placeholder for your specific DST parser logic
    parsed_data = {
        "name": file.filename.split('.')[0] if '.' in file.filename else file.filename,
        "description": "Parsed Embroidery Design\nFormat: .DST",
        "suggested_price": 10.00
    }
    return jsonify(parsed_data)

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

# Required for Render to bind to the correct port
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
