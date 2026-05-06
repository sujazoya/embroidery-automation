import os, uuid, json
from flask import Flask, request, jsonify
from square.client import Client
from flask_cors import CORS

app = Flask(__name__)
# Replace '*' with your specific Netlify URL for better security later
CORS(app, resources={r"/*": {"origins": "*"}}) 

# Setup Square Client
# It will now print a warning if the token is missing to help you debug
token = os.environ.get('SQUARE_ACCESS_TOKEN')
if not token:
    print("WARNING: SQUARE_ACCESS_TOKEN is not set in Environment Variables")

client = Client(
    access_token=token,
    environment='production' 
)

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "online"}), 200

@app.route('/categories', methods=['GET'])
def get_categories():
    result = client.catalog.list_catalog(types='CATEGORY')
    if result.is_success():
        categories = [{"id": obj['id'], "name": obj['category_data']['name']} 
                      for obj in result.body.get('objects', [])]
        return jsonify(categories)
    return jsonify({"error": "Failed to fetch categories", "details": str(result.errors)}), 400

@app.route('/parse', methods=['POST'])
def parse_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    # Placeholder for your DST parser
    parsed_data = {
        "name": file.filename.split('.')[0],
        "description": "Stitches: 12,450\nColors: 4\nSize: 120mm x 150mm\nFormat: .DST",
        "suggested_price": 10.00
    }
    return jsonify(parsed_data)

@app.route('/upload-to-square', methods=['POST'])
def upload_to_square():
    data = request.json
    item_body = {
        "idempotency_key": str(uuid.uuid4()),
        "object": {
            "type": "ITEM",
            "id": "#new_design",
            "item_data": {
                "name": data['name'],
                "description": data['description'],
                "category_id": data['category_id'],
                "variations": [{
                    "type": "ITEM_VARIATION",
                    "id": "#new_var",
                    "item_variation_data": {
                        "name": "Digital Download",
                        "pricing_type": "FIXED_PRICING",
                        "price_money": {
                            "amount": int(float(data['price']) * 100),
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

# RENDER FIX: Bind to 0.0.0.0 and use the dynamic PORT
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
