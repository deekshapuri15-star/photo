import os
from datetime import datetime

from flask import Flask, render_template, request, url_for
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "static", "output")
LOGO_PATH = os.path.join(BASE_DIR, "static", "iete_logo.png")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload cap


def remove_white_background(logo_img: Image.Image, threshold: int = 245, feather: int = 35) -> Image.Image:
    """
    Turns white/near-white pixels transparent so only the triangle (and
    its real colors) survive, with a soft-edged fade instead of a hard
    cutoff -- this avoids leaving a faint white/grey fringe around the
    triangle's anti-aliased edges. Anything outside the shape -- which
    is plain white in your iete_logo.png -- becomes transparent, so
    when it's pasted onto a photo it blends with whatever is underneath
    instead of showing a white box.
    """
    logo_img = logo_img.convert("RGBA")
    pixel_data = logo_img.getdata()

    new_pixels = []
    for r, g, b, a in pixel_data:
        brightness = min(r, g, b)
        if brightness >= threshold:
            new_alpha = 0
        elif brightness >= threshold - feather:
            # linearly fade alpha across the feather band instead of a hard edge
            fade_ratio = (brightness - (threshold - feather)) / feather
            new_alpha = int(a * (1 - fade_ratio))
        else:
            new_alpha = a
        new_pixels.append((r, g, b, new_alpha))

    logo_img.putdata(new_pixels)
    return logo_img


def add_watermark(photo_path, output_path, logo_x_frac, logo_y_frac, logo_scale_frac):
    photo = Image.open(photo_path).convert("RGBA")

    logo = Image.open(LOGO_PATH)
    logo = remove_white_background(logo)

    logo_width = max(20, int(photo.width * logo_scale_frac))
    ratio = logo_width / logo.width
    logo = logo.resize((logo_width, int(logo.height * ratio)), Image.LANCZOS)

    x = int(photo.width * logo_x_frac)
    y = int(photo.height * logo_y_frac)

    # keep the logo fully inside the photo even if the browser sent
    # a slightly out-of-range position
    x = max(0, min(x, photo.width - logo.width))
    y = max(0, min(y, photo.height - logo.height))

    photo.paste(logo, (x, y), logo)  # logo used as its own alpha mask
    photo.convert("RGB").save(output_path, quality=95)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    photo_file = request.files.get("photo")
    if not photo_file or photo_file.filename == "":
        return {"error": "No photo uploaded"}, 400

    try:
        logo_x_frac = float(request.form.get("logo_x", 0.75))
        logo_y_frac = float(request.form.get("logo_y", 0.80))
        logo_scale_frac = float(request.form.get("logo_scale", 0.18))
    except ValueError:
        return {"error": "Invalid position/scale values"}, 400

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_name = f"{timestamp}_{photo_file.filename}"
    upload_path = os.path.join(UPLOAD_FOLDER, safe_name)
    photo_file.save(upload_path)

    output_name = f"watermarked_{safe_name}"
    if not output_name.lower().endswith((".jpg", ".jpeg", ".png")):
        output_name += ".jpg"
    output_path = os.path.join(OUTPUT_FOLDER, output_name)

    add_watermark(upload_path, output_path, logo_x_frac, logo_y_frac, logo_scale_frac)

    return {"output_url": url_for("static", filename=f"output/{output_name}")}


if __name__ == "__main__":
    app.run(debug=True)