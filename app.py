from flask import Flask, request, jsonify
from flask_cors import CORS
from pyembroidery import read
import tempfile, os, requests, uuid
import json

app = Flask(__name__)
CORS(app)

# 🔥 HARDCODED (you asked for it)
SQUARE_ACCESS_TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN")
SQUARE_LOCATION_ID = os.environ.get("SQUARE_LOCATION_ID")

# 🎯 Hoop size classification
def classify_area(w, h):
    if w <= 100 and h <= 100:
        return "4x4"
    elif w <= 130 and h <= 180:
        return "5x7"
    elif w <= 160 and h <= 260:
        return "6x10"
    elif w <= 200 and h <= 300:
        return "8x12"
    elif w <= 260 and h <= 400:
        return "10x16"
    elif w <= 300 and h <= 500:
        return "12x20"
    return "Oversized"

# 📦 Bounding box
def bbox(pattern):
    xs = [p[0] for p in pattern.stitches]
    ys = [p[1] for p in pattern.stitches]
    return min(xs), min(ys), max(xs), max(ys)

@app.route("/create", methods=["POST"])
def create():
    try:
        # ✅ Validate input
        if "file" not in request.files or "image" not in request.files:
            return jsonify({"success": False, "error": "Missing file or image"}), 400

        file = request.files["file"]
        image = request.files["image"]
        category = request.form.get("category")

        if not category:
            return jsonify({"success": False, "error": "Category required"}), 400

        design_name = file.filename.rsplit(".", 1)[0]

        # 📂 Save DST temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dst") as f:
            file.save(f.name)
            path = f.name

        # 📊 Process embroidery file
        pattern = read(path)
        l, t, r, b = bbox(pattern)

        width = round(abs(r - l) / 10, 2)
        height = round(abs(b - t) / 10, 2)
        stitches = len(pattern.stitches)

        os.unlink(path)

        # 🎯 Hoop size
        area = classify_area(width, height)

        # 💰 Auto price
        price = int(stitches * 0.05)

        # 🖼 Upload image to Square
        img_res = requests.post(
    "https://connect.squareup.com/v2/catalog/images",
    headers={
        "Authorization": f"Bearer {SQUARE_ACCESS_TOKEN}"
    },
    files={
        "file": (image.filename, image.stream, image.mimetype),
        "request": (
            None,
            json.dumps({
                "idempotency_key": str(uuid.uuid4()),
                "object_id": "#TEMP_ID"
            }),
            "application/json"
        )
    }
)

        img_json = img_res.json()

        if "image" not in img_json:
            return jsonify({
                "success": False,
                "error": "Image upload failed",
                "details": img_json
            }), 500

        img_id = img_json["image"]["id"]

        # 📝 CLEAN DESCRIPTION
        description = (
            f"Design Name: {design_name}\n"
            f"Width: {width} mm\n"
            f"Height: {height} mm\n"
            f"Stitches: {stitches}\n"
            f"Hoop Size: {area}\n"
            f"Format: DST"
        )

        # 🛒 Create product
        body = {
            "idempotency_key": str(uuid.uuid4()),
            "object": {
                "type": "ITEM",
                "id": "#item",
                "item_data": {
                    "name": design_name,
                    "description": description,
                    "category_id": category,
                    "image_ids": [img_id],
                    "variations": [{
                        "type": "ITEM_VARIATION",
                        "id": "#var",
                        "item_variation_data": {
                            "name": "Default",
                            "pricing_type": "FIXED_PRICING",
                            "price_money": {
                                "amount": price,
                                "currency": "USD"
                            }
                        }
                    }]
                }
            }
        }

        res = requests.post(
            "https://connect.squareup.com/v2/catalog/object",
            json=body,
            headers={
                "Authorization": f"Bearer {SQUARE_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
        )

        square_res = res.json()

        if "errors" in square_res:
            return jsonify({
                "success": False,
                "error": square_res["errors"]
            }), 500

        return jsonify({
            "success": True,
            "message": "Product created successfully",
            "data": {
                "name": design_name,
                "width": width,
                "height": height,
                "stitches": stitches,
                "area": area,
                "price": price
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/")
def home():
    return {
        "status": "running",
        "message": "Embroidery Auto Product API 🚀"
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
