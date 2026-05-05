from flask import Flask, request, jsonify
from flask_cors import CORS
from pyembroidery import read
import tempfile, os, requests, uuid

app = Flask(__name__)
CORS(app)

SQUARE_ACCESS_TOKEN = "EAAAl4nOZHrwp_oBdosTVg0l4PX9fl_u8vD70r64pG47JdvAutDQYL_dW8mi7CiA
SQUARE_LOCATION_ID = "LZTJ86J91SXMN"

def classify_area(w, h):
    if w <= 100 and h <= 100: return "4x4"
    if w <= 130 and h <= 180: return "5x7"
    if w <= 160 and h <= 260: return "6x10"
    return "Large"

def bbox(pattern):
    xs = [p[0] for p in pattern.stitches]
    ys = [p[1] for p in pattern.stitches]
    return min(xs), min(ys), max(xs), max(ys)

@app.route("/create", methods=["POST"])
def create():
    file = request.files["file"]
    image = request.files["image"]
    category = request.form["category"]

    # save dst
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dst") as f:
        file.save(f.name)
        path = f.name

    pattern = read(path)
    l,t,r,b = bbox(pattern)

    w = abs(r-l)/10
    h = abs(b-t)/10
    stitches = len(pattern.stitches)

    os.unlink(path

    # 🔥 AUTO PRICE
    price = int(stitches * 0.05)

    # 🔥 Upload image
    img_res = requests.post(
    "https://connect.squareup.com/v2/catalog/images",
    headers={
        "Authorization": f"Bearer {SQUARE_ACCESS_TOKEN}"
    },
    files={
        "file": (image.filename, image.stream, image.mimetype),
        "request": (None, '{"idempotency_key": "' + str(uuid.uuid4()) + '"}', "application/json")
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

    # 🔥 Create product
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "object": {
            "type": "ITEM",
            "id": "#item",
            "item_data": {
                "name": file.filename.split(".")[0],
                "description": f"""
Width: {w:.2f}mm
Height: {h:.2f}mm
Stitches: {stitches}
Auto Price: ${price/100}
                """,
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
    "product": square_res
})

@app.route("/")
def home():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
