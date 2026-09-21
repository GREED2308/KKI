from flask import Flask, render_template, request, jsonify, send_from_directory
import threading
import time
import json
import os

app = Flask(__name__)

CAPTURE_ROOT = "/opt/asv-dashboard/captures"
FRONT_CAPTURE_DIR = os.path.join(CAPTURE_ROOT, "front")
UNDERWATER_CAPTURE_DIR = os.path.join(CAPTURE_ROOT, "underwater")

os.makedirs(FRONT_CAPTURE_DIR, exist_ok=True)
os.makedirs(UNDERWATER_CAPTURE_DIR, exist_ok=True)

# ============================================================
# TELEMETRY STATE
# ============================================================

telemetry_lock = threading.Lock()

telemetry_data = {
    "yaw": 0.0,
    "sys_cal": 0,
    "lat": -999.0,
    "lon": -999.0,
    "satellites": 0,
    "last_update": 0.0,
}

# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# API: TELEMETRY DARI JETSON
# ============================================================

@app.route("/api/telemetry", methods=["POST"])
def receive_telemetry():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "ok": False,
            "error": "JSON body tidak valid"
        }), 400

    try:
        yaw = float(data.get("yaw", 0.0))
        sys_cal = int(data.get("sys_cal", 0))
        lat = float(data.get("lat", -999.0))
        lon = float(data.get("lon", -999.0))
        satellites = int(data.get("satellites", 0))
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "error": "Format telemetry tidak valid"
        }), 400

    with telemetry_lock:
        telemetry_data["yaw"] = yaw
        telemetry_data["sys_cal"] = sys_cal
        telemetry_data["lat"] = lat
        telemetry_data["lon"] = lon
        telemetry_data["satellites"] = satellites
        telemetry_data["last_update"] = time.time()

    return jsonify({
        "ok": True,
        "message": "Telemetry diterima"
    })


# ============================================================
# API: TELEMETRY UNTUK DASHBOARD
# ============================================================

@app.route("/api/telemetry", methods=["GET"])
def get_telemetry():
    with telemetry_lock:
        data = telemetry_data.copy()

    data["age"] = (
        time.time() - data["last_update"]
        if data["last_update"] > 0
        else None
    )

    return jsonify(data)

@app.route("/api/telemetry/view", methods=["GET"])
def view_telemetry():
    with telemetry_lock:
        data = telemetry_data.copy()

    data["age"] = (
        time.time() - data["last_update"]
        if data["last_update"] > 0
        else None
    )

    return (
        json.dumps(data, indent=4),
        200,
        {"Content-Type": "application/json; charset=utf-8"}
    )

# ============================================================
# API: UPLOAD FOTO DARI JETSON
# ============================================================

@app.route("/api/capture", methods=["POST"])
def upload_capture():

    camera = request.form.get("camera", "").lower()

    if camera not in ("front", "underwater"):
        return jsonify({
            "ok": False,
            "error": "Camera harus front atau underwater"
        }), 400

    if "image" not in request.files:
        return jsonify({
            "ok": False,
            "error": "File image tidak ditemukan"
        }), 400

    image = request.files["image"]

    if image.filename == "":
        return jsonify({
            "ok": False,
            "error": "Nama file kosong"
        }), 400

    filename = os.path.basename(image.filename)

    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        return jsonify({
            "ok": False,
            "error": "Format gambar tidak didukung"
        }), 400

    if camera == "front":
        capture_dir = FRONT_CAPTURE_DIR
    else:
        capture_dir = UNDERWATER_CAPTURE_DIR

    filepath = os.path.join(capture_dir, filename)

    try:
        image.save(filepath)

        print(
            f"[CAPTURE] Foto {camera} tersimpan: {filepath}"
        )

        return jsonify({
            "ok": True,
            "camera": camera,
            "filename": filename,
            "path": filepath
        })

    except Exception as e:

        print(
            f"[CAPTURE] Gagal menyimpan foto: {e}"
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@app.route("/captures/<camera>")
def capture_gallery(camera):

    if camera == "front":
        title = "Foto Kamera Atas / Front"
        capture_dir = FRONT_CAPTURE_DIR

    elif camera == "underwater":
        title = "Foto Kamera Bawah / Underwater"
        capture_dir = UNDERWATER_CAPTURE_DIR

    else:
        return "Kamera tidak ditemukan", 404

    files = [
        f for f in os.listdir(capture_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    files.sort(reverse=True)

    html = f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>

        <style>
            body {{
                margin: 0;
                padding: 20px;
                background: #0a111a;
                color: #e2e8f0;
                font-family: Arial, sans-serif;
            }}

            h1 {{
                color: #00e5ff;
            }}

            .gallery {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 15px;
            }}

            .photo {{
                background: #111c2b;
                border: 1px solid #1c2e45;
                border-radius: 8px;
                padding: 10px;
            }}

            .photo img {{
                width: 100%;
                display: block;
                border-radius: 6px;
            }}

            .filename {{
                margin-top: 8px;
                font-size: 12px;
                color: #94a3b8;
                word-break: break-all;
            }}

            .empty {{
                color: #94a3b8;
                margin-top: 30px;
            }}
        </style>
    </head>

    <body>

        <h1>{title}</h1>

        <div class="gallery">
    """

    if files:

        for filename in files:

            html += f"""
                <div class="photo">
                    <a href="/capture-file/{camera}/{filename}" target="_blank">
                        <img src="/capture-file/{camera}/{filename}">
                    </a>

                    <div class="filename">
                        {filename}
                    </div>
                </div>
            """

    else:

        html += """
            <div class="empty">
                Belum ada foto yang tersimpan.
            </div>
        """

    html += """
        </div>

    </body>
    </html>
    """

    return html

@app.route("/capture-file/<camera>/<path:filename>")
def capture_file(camera, filename):

    if camera == "front":
        capture_dir = FRONT_CAPTURE_DIR

    elif camera == "underwater":
        capture_dir = UNDERWATER_CAPTURE_DIR

    else:
        return "Kamera tidak ditemukan", 404

    return send_from_directory(capture_dir, filename)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False
    )
