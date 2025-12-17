from flask import Flask, request, render_template, send_file
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
import os
import io

app = Flask(__name__)

# Configuration
MIN_WIDTH_THRESHOLD = 800
MIN_HEIGHT_THRESHOLD = 600
TARGET_WIDTH = 4000
TARGET_HEIGHT = 2250
TARGET_DPI = (96, 96)

def apply_watermark(image, watermark_text, font_path):
    """
    Applies watermark directly to a PIL Image object in memory.
    """
    # Settings (Preserved from your previous request)
    font_size = 70
    text_color = (0, 0, 0, 255)
    box_color = (255, 255, 255, 130) # Transparent White
    line_spacing = 2
    padding_top = 10
    padding_bottom = 10
    padding_left = 10
    padding_right = 60

    # Convert to RGBA for transparency support
    image = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # --- FONT LOADING ---
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        try:
            # Fallback for Windows/Linux if specific path fails
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

    # --- TEXT METRICS ---
    try:
        ascent, descent = font.getmetrics()
        line_height = ascent + descent + line_spacing
    except:
        # Fallback logic
        try:
            line_height = font.getbbox("A")[3] + line_spacing
        except:
             line_height = 15 + line_spacing

    text_lines = watermark_text.split("\n")
    text_block_height = len(text_lines) * line_height - line_spacing
    
    # Calculate Max Width
    text_block_width = 0
    if text_lines:
        for line in text_lines:
            try:
                w = draw.textlength(line, font=font)
            except AttributeError:
                try:
                    w = font.getbbox(line)[2]
                except:
                    w = font.getsize(line)[0]
            if w > text_block_width:
                text_block_width = w

    # --- BOX POSITIONING ---
    box_width = text_block_width + padding_left + padding_right
    box_height = text_block_height + padding_top + padding_bottom

    box_left = 0
    box_bottom = image.height
    box_right = box_width
    box_top = image.height - box_height

    # Draw Box
    draw.rectangle([(box_left, box_top), (box_right, box_bottom)], fill=box_color)

    # --- DRAW TEXT ---
    current_y = box_top + padding_top
    for line in text_lines:
        draw.text((box_left + padding_left, current_y), line, fill=text_color, font=font)
        current_y += line_height

    # Combine and convert back to RGB (required for JPEG)
    watermarked_image = Image.alpha_composite(image, overlay)
    return watermarked_image.convert("RGB")


@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'photo' not in request.files:
            return "No file part", 400
        photo = request.files['photo']
        if photo.filename == '':
            return "No selected file", 400

        # Form Data processing
        labels = ["Latitude:", "Longitude:", "Elevation:", "Accuracy:", "Time:", "Note:", ""]
        postfix = ['','','±5 m','','','','']
        texts = []
        for i in range(1, 8):
            val = request.form.get(f'text{i}', '')
            if val or i == 7: 
                 texts.append(f"{labels[i-1]} {val}{postfix[i-1]}")
        watermark_text = "\n".join(texts)
        
        # Font Path (adjusted for standard PythonAnywhere structure)
        font_path = os.path.join(app.root_path, 'static', 'fonts', 'Roboto-Regular.ttf')

        try:
            # 1. Open Image from RAM
            img = Image.open(photo.stream).convert('RGB')
            
            if img.width < MIN_WIDTH_THRESHOLD: 
                return "Error: Image too small", 400

            # 2. Resize & Crop Logic
            target_r = TARGET_WIDTH / TARGET_HEIGHT
            img_r = img.width / img.height
            
            if img_r > target_r:
                new_h = TARGET_HEIGHT
                new_w = int(new_h * img_r)
            else:
                new_w = TARGET_WIDTH
                new_h = int(new_w / img_r)

            # High-quality Resize
            resized = img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)
            
            # Center Crop
            left = (new_w - TARGET_WIDTH)/2
            top = (new_h - TARGET_HEIGHT)/2
            processed_img = resized.crop((left, top, left+TARGET_WIDTH, top+TARGET_HEIGHT))

            # 3. Apply Watermark (In Memory)
            final_img = apply_watermark(processed_img, watermark_text, font_path)

            # 4. Save to BytesIO (RAM)
            img_io = io.BytesIO()
            final_img.save(img_io, 'JPEG', quality=95, dpi=TARGET_DPI)
            img_io.seek(0) # Reset pointer to start of file

            # 5. Send directly to user
            return send_file(
                img_io, 
                mimetype='image/jpeg', 
                as_attachment=True, 
                download_name=f"processed_{photo.filename}"
            )

        except UnidentifiedImageError:
            return "Error: Invalid image file", 400
        except Exception as e:
            return f"Error: {e}", 500

    return render_template('index.html')

if __name__ == '__main__':
    # Ensure fonts folder exists if running locally, 
    # but no uploads folder is created.
    app.run(debug=True)
