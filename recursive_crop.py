import os
from PIL import Image

# 1. Set your folder names here!
INPUT_DIR = "valo-dataset" # <-- Change this to the name of your main folder
OUTPUT_DIR = "cropped_dataset"

# Standard 1080p Crop Settings (Adjust if you play on 1440p or 4K)
CROP_LEFT_PCT = 0.75   # Start 75% across the screen
CROP_TOP_PCT = 0.0     # Start at the top
CROP_RIGHT_PCT = 1.0   # Go to the right edge
CROP_BOTTOM_PCT = 0.25 # Go 25% down the screen

print("🚀 Starting the recursive crop pipeline...")

# Walk through every folder and file in the input directory
for root, dirs, files in os.walk(INPUT_DIR):
    for file in files:
        if file.lower().endswith((".png", ".jpg", ".jpeg")):
            # Get the exact path of the current image
            img_path = os.path.join(root, file)
            
            # Figure out which subfolder it belongs to (e.g., "Vandal", "Ghost")
            relative_path = os.path.relpath(root, INPUT_DIR)
            
            # Create the matching subfolder in the Output directory
            output_subfolder = os.path.join(OUTPUT_DIR, relative_path)
            os.makedirs(output_subfolder, exist_ok=True)
            
            # Open and crop the image
            try:
                img = Image.open(img_path)
                width, height = img.size
                
                left = int(width * CROP_LEFT_PCT)
                top = int(height * CROP_TOP_PCT)
                right = int(width * CROP_RIGHT_PCT)
                bottom = int(height * CROP_BOTTOM_PCT)
                
                cropped_img = img.crop((left, top, right, bottom))
                
                # Save it to the new categorized folder
                save_path = os.path.join(output_subfolder, f"crop_{file}")
                cropped_img.save(save_path)
                print(f"✅ Cropped: {relative_path}/{file}")
                
            except Exception as e:
                print(f"❌ Failed to crop {file}: {e}")

print(f"🎉 All done! Your cropped images are in the '{OUTPUT_DIR}' folder.")