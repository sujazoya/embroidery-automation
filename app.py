import os, uuid, json
from flask import Flask, request, jsonify
from square.client import Client
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Allows your Netlify frontend to talk to Render

# Setup Square Client
client = Client(
    access_token=os.environ.get('SQUARE_ACCESS_TOKEN'),
    environment='production' 
)

# 1. GET CATEGORIES FOR DROPDOWN
@app.route('/categories', methods=['GET'])
def get_categories():
    result = client.catalog.list_catalog(types='CATEGORY')
    if result.is_success():
        # Returns list of {id, name}
        categories = [{"id": obj['id'], "name": obj['category_data']['name']} 
                      for obj in result.body.get('objects', [])]
        return jsonify(categories)
    return jsonify({"error": "Failed to fetch categories"}), 400

# 2. PARSE THE FILE (Doesn't save to Square)
@app.route('/parse', methods=['POST'])
def parse_file():
    file = request.files['file']
    # --- INSERT YOUR DST PARSER LOGIC HERE ---
    # Example extracted data:
    parsed_data = {
        "name": file.filename.split('.')[0],
        "description": "Stitches: 12,450\nColors: 4\nSize: 120mm x 150mm\nFormat: .DST",
        "suggested_price": 10.00
    }
    return jsonify(parsed_data)

# 3. CREATE PRODUCT IN SQUARE
@app.route('/upload-to-square', methods=['POST'])
def upload_to_square():
    data = request.json # Data from your frontend form
    
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
                            "amount": int(float(data['price']) * 100), # Converts $10 to 1000 cents
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

if __name__ == '__main__':
    app.run(debug=True)
