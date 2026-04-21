from PIL import Image, ImageOps
import os
import sys


INPUT_FOLDER  = r"C:\Users\?\Desktop\labelme_all_images" # <-- change this
OUTPUT_FOLDER = r"C:\Users\?\Desktop\labelme_all_images_padding" # <-- change this (can be same as input)
PADDING       = 30 # pixels to add on each side
FILL_COLOR    = (255, 255, 255) # white padding, can be 0;0;0 for black

SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

def add_padding(input_folder, output_folder, padding, fill):
    os.makedirs(output_folder, exist_ok=True)

    files = []
    for filename in os.listdir(input_folder):
        extension = os.path.splitext(filename)[1].lower()
        if extension in SUPPORTED:
            files.append(filename)

    if not files:
        print("No supported image files found in the input folder.")
        return


    ok, fail = 0, 0
    for filename in files:
        src = os.path.join(input_folder, filename)
        dst = os.path.join(output_folder, filename)
        try:
            img = Image.open(src).convert("RGB")
            padded = ImageOps.expand(img, border=padding, fill=fill)
            padded.save(dst)
            print(f" GOOD {filename} -> {padded.size[0]}x{padded.size[1]}px")
            ok += 1
        except Exception as e:
            print(f" BAD {filename} -> ERROR: {e}")
            fail += 1

    print()
    print(f"Done! {ok} succeeded, {fail} failed.")
    print(f"Padded images saved to: {output_folder}")

if __name__ == "__main__":
    add_padding(INPUT_FOLDER, OUTPUT_FOLDER, PADDING, FILL_COLOR)