import os
import uuid
from flask import Flask, request, jsonify
from square.client import Client
from flask_cors import CORS
import pyembroidery  # This is the actual parser

app = Flask(__name__)
CORS(app)

# Square Setup
SQUARE_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN')
client = Client(access_token=SQUARE_TOKEN, environment='production')

@app.route('/', methods=['GET'])
def health():
    return "Embroidery Parser is Live", 200

@app.route('/categories', methods=['GET'])
def get_categories():
    result = client.catalog.list_catalog(types='CATEGORY')
    if result.is_success():
        objs = result.body.get('objects', [])
        return jsonify([{"id": o['id'], "name": o['category_data']['name']} for o in objs])
    return jsonify({"error": "No categories found"}), 400

@app.route('/parse', methods=['POST'])
def parse_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files['file']
    temp_path = os.path.join("/tmp", file.filename)
    file.save(temp_path)
    
    try:
        # --- ACTUAL DST PARSER LOGIC ---
        pattern = pyembroidery.read(temp_path)
        
        # Get Stitch Count
        stitches = pattern.count_stitches()
        
        # Get Dimensions (converted from 0.1mm units to mm)
        bounds = pattern.bounds() # [min_x, min_y, max_x, max_y]
        width = round((bounds[2] - bounds[0]) / 10, 2)
        height = round((bounds[3] - bounds[1]) / 10, 2)
        
        # Get Color Count
        colors = len(pattern.threadlist) if hasattr(pattern, 'threadlist') else 1

        os.remove(temp_path) # Clean up

        return jsonify({
            "name": file.filename.split('.')[0].replace('_', ' ').title(),
            "description": f"Design Details:\n- Stitches: {stitches}\n- Size: {width}mm x {height}mm\n- Colors: {colors}\n- Format: .DST",
            "suggested_price": 10.00
        })
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return jsonify({"error": f"Parser Error: {str(e)}"}), 500

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
                        "price_money": {"amount": int(float(data['price']) * 100), "currency": "USD"}
                    }
                }]
            }
        }
    }
    result = client.catalog.upsert_catalog_object(item_body)
    return jsonify(result.body if result.is_success() else result.errors)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
