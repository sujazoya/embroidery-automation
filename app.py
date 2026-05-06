import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
import pyembroidery

# Use a safe import for Square to prevent the Status 1 crash
try:
    from square.client import Client
except ImportError:
    Client = None

app = Flask(__name__)
CORS(app)

# Square Setup
SQUARE_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN', 'MISSING')
client = Client(access_token=SQUARE_TOKEN, environment='production') if Client else None

@app.route('/')
def home():
    return jsonify({"status": "Live", "sdk_loaded": client is not None}), 200

@app.route('/categories', methods=['GET'])
def get_categories():
    if not client:
        return jsonify({"error": "Square SDK failed to load"}), 500
    try:
        res = client.catalog.list_catalog(types='CATEGORY')
        if res.is_success():
            objs = res.body.get('objects', [])
            return jsonify([{"id": o['id'], "name": o['category_data']['name']} for o in objs])
        return jsonify({"error": res.errors}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/parse', methods=['POST'])
def parse_embroidery():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files['file']
    temp_path = os.path.join("/tmp", file.filename)
    file.save(temp_path)
    
    try:
        pattern = pyembroidery.read(temp_path)
        stitches = pattern.count_stitches()
        bounds = pattern.bounds()
        width = round((bounds[2] - bounds[0]) / 10, 1)
        height = round((bounds[3] - bounds[1]) / 10, 1)
        
        os.remove(temp_path)
        return jsonify({
            "name": file.filename.rsplit('.', 1)[0].replace('_', ' ').title(),
            "description": f"Stitches: {stitches}\nSize: {width}mm x {height}mm",
            "price": 10.00
        })
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return jsonify({"error": str(e)}), 500

@app.route('/upload-to-square', methods=['POST'])
def upload():
    if not client: return jsonify({"error": "SDK Missing"}), 500
    data = request.json
    item_body = {
        "idempotency_key": str(uuid.uuid4()),
        "object": {
            "type": "ITEM",
            "id": "#new",
            "item_data": {
                "name": data.get('name'),
                "description": data.get('description'),
                "category_id": data.get('category_id'),
                "variations": [{
                    "type": "ITEM_VARIATION",
                    "id": "#var",
                    "item_variation_data": {
                        "name": "Download",
                        "pricing_type": "FIXED_PRICING",
                        "price_money": {"amount": int(float(data.get('price', 10)) * 100), "currency": "USD"}
                    }
                }]
            }
        }
    }
    res = client.catalog.upsert_catalog_object(item_body)
    return jsonify(res.body if res.is_success() else res.errors)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
