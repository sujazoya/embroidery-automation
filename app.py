import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
# This is the modern, stable way to import the Square Client
from square.client import Client
import pyembroidery

app = Flask(__name__)
CORS(app)

# Use your Render Environment Variable
SQUARE_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN', 'MISSING')

# Initialize Client
client = Client(
    access_token=SQUARE_TOKEN,
    environment='production'
)

@app.route('/')
def health():
    return "API is Live", 200

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
        return jsonify({"error": str(e)}), 500

@app.route('/parse', methods=['POST'])
def parse_embroidery():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    temp_path = os.path.join("/tmp", file.filename)
    file.save(temp_path)
    
    try:
        pattern = pyembroidery.read(temp_path)
        stitches = pattern.count_stitches()
        bounds = pattern.bounds()
        width = round((bounds[2] - bounds[0]) / 10, 1)
        height = round((bounds[3] - bounds[1]) / 10, 1)
        
        design_name = file.filename.rsplit('.', 1)[0].replace('_', ' ').title()
        
        os.remove(temp_path)
        return jsonify({
            "name": design_name,
            "description": f"Stitches: {stitches}\nSize: {width}mm x {height}mm",
            "price": 10.00
        })
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return jsonify({"error": str(e)}), 500

@app.route('/upload-to-square', methods=['POST'])
def upload_to_square():
    data = request.json
    try:
        item_body = {
            "idempotency_key": str(uuid.uuid4()),
            "object": {
                "type": "ITEM",
                "id": "#new_design",
                "item_data": {
                    "name": data.get('name', 'Untitled'),
                    "description": data.get('description', ''),
                    "category_id": data.get('category_id'),
                    "variations": [{
                        "type": "ITEM_VARIATION",
                        "id": "#new_var",
                        "item_variation_data": {
                            "name": "Download",
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
        return jsonify(result.body if result.is_success() else result.errors)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
