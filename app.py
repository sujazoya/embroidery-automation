import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from square.client import Client
import pyembroidery

app = Flask(__name__)
CORS(app)

# Square Setup
SQUARE_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN', 'MISSING')
client = Client(access_token=SQUARE_TOKEN, environment='production')

@app.route('/')
def home():
    return jsonify({"status": "EmbDesign Square API Live"}), 200

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
        return jsonify({"success": False, "error": "No file uploaded"}), 400
    
    file = request.files['file']
    temp_path = os.path.join("/tmp", file.filename)
    file.save(temp_path)
    
    try:
        pattern = pyembroidery.read(temp_path)
        
        # Exact logic from your working parser
        stitches = pattern.count_stitches()
        bounds = pattern.bounds()  # [min_x, min_y, max_x, max_y]
        width = round((bounds[2] - bounds[0]) / 10, 1)
        height = round((bounds[3] - bounds[1]) / 10, 1)
        needles = len(pattern.threadlist) if hasattr(pattern, 'threadlist') else 1
        
        design_name = file.filename.rsplit('.', 1)[0].replace('_', ' ').title()

        # Structured description for Square
        description = (
            f"Embroidery Design Details:\n"
            f"- Design Name: {design_name}\n"
            f"- Stitches: {stitches}\n"
            f"- Dimensions: {width}mm x {height}mm\n"
            f"- Colors: {needles}\n"
            f"- Formats: .DST, .EMB"
        )

        os.remove(temp_path)

        return jsonify({
            "success": True,
            "design_details": {
                "design_name": design_name,
                "description": description,
                "width": width,
                "height": height,
                "stitches": stitches,
                "needles": needles,
                "suggested_price": 10.00
            }
        })
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/upload-to-square', methods=['POST'])
def upload():
    data = request.json
    try:
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
                            "name": "Digital Download",
                            "pricing_type": "FIXED_PRICING",
                            "price_money": {"amount": int(float(data.get('price', 10)) * 100), "currency": "USD"}
                        }
                    }]
                }
            }
        }
        result = client.catalog.upsert_catalog_object(item_body)
        if result.is_success():
            return jsonify({"success": True, "item": result.body})
        return jsonify({"success": False, "error": result.errors}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Your working repo uses the dynamic PORT env var
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
