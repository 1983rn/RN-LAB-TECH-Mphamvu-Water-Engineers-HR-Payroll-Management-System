import os
import uuid
try:
    from rembg import remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    def remove(*args, **kwargs):
        raise ImportError("rembg is not installed")
from PIL import Image

def clean_employee_photo(original_photo_path, final_output_dir):
    """
    Complete pipeline:
    1. Remove background
    2. Add blue background
    3. Crop to 300x300
    """
    os.makedirs(final_output_dir, exist_ok=True)
    
    unique_id = uuid.uuid4().hex
    filename = f"cleaned_{unique_id}.jpg"
    final_path = os.path.join(final_output_dir, filename)
    
    if not REMBG_AVAILABLE:
        print("rembg not installed, skipping background removal. Basic resize only.")
        img = Image.open(original_photo_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img = img.resize((300, 300), Image.Resampling.LANCZOS)
        img.save(final_path)
        return filename

    try:
        # Load and remove background
        input_img = Image.open(original_photo_path)
        removed_bg = remove(input_img).convert("RGBA")
        
        # Add blue background (RGB: 10, 60, 150)
        width, height = removed_bg.size
        blue_background = Image.new("RGBA", (width, height), (10, 60, 150, 255))
        blue_background.paste(removed_bg, (0, 0), removed_bg)
        
        # Convert to RGB and resize to strictly 300x300
        final = blue_background.convert("RGB")
        final = final.resize((300, 300), Image.Resampling.LANCZOS)
        
        # Save directly to final destination
        final.save(final_path, "JPEG", quality=95)
        
        return filename
    except Exception as e:
        print(f"Error processing background: {e}")
        # Fallback to just resizing if AI fails
        filename = f"basic_{unique_id}.jpg"
        final_path = os.path.join(final_output_dir, filename)
        
        img = Image.open(original_photo_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img = img.resize((300, 300), Image.Resampling.LANCZOS)
        img.save(final_path)
        
        return filename
