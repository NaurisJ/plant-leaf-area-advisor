# Convert LabelMe JSON annotations -> YOLO segmentation format + train/val split

# Input:  labelme_all_images_padding
# Output: dataset/train, dataset/val

# YOLO seg label format: each line = "class x1 y1 x2 y2 ... xn yn"
# (normalized polygon coordinates, one polygon per line).

import base64
import io
import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


# Config
SRC_DIR = Path(__file__).parent / "labelme_all_images_padding"
OUT_DIR = Path(__file__).parent / "dataset"
IMG_SIZE = (640, 640) # width, height
VAL_RATIO = 0.15 # ~30 val images out of ~200
SEED = 42


def decode_labelme_mask(shape, img_w, img_h):
    # Decode a LabelMe AI mask shape into a full image binary mask
    # The mask in LabelMe is stored base64-encoded and only covers a
    # bounding-box region. Now paste it onto a full size canvas
    mask_bytes = base64.b64decode(shape["mask"])
    mask_img = Image.open(io.BytesIO(mask_bytes))
    mask_arr = np.array(mask_img) # values 0/1

    # Top left corner of the bounding box (where to paste the mask)
    pts = shape["points"]
    x0 = int(pts[0][0])
    y0 = int(pts[0][1])

    # Where the mask lands on the full image (clipped to image bounds)
    paste_y0 = max(0, y0)
    paste_x0 = max(0, x0)
    paste_y1 = min(img_h, y0 + mask_arr.shape[0])
    paste_x1 = min(img_w, x0 + mask_arr.shape[1])

    # Matching slice from the source mask (in case bbox is partly off-image)
    src_y0 = paste_y0 - y0
    src_x0 = paste_x0 - x0
    src_y1 = src_y0 + (paste_y1 - paste_y0)
    src_x1 = src_x0 + (paste_x1 - paste_x0)

    full = np.zeros((img_h, img_w), dtype=np.uint8)
    # Get rows and columns from source mask
    source_rows = src_y0, src_y1
    source_cols = src_x0, src_x1

    # Extract source area
    source_part = mask_arr[
        source_rows[0]:source_rows[1],
        source_cols[0]:source_cols[1]
    ]

    # Get destination rows and columns
    dest_rows = paste_y0, paste_y1
    dest_cols = paste_x0, paste_x1

    # Paste into final image
    full[
        dest_rows[0]:dest_rows[1],
        dest_cols[0]:dest_cols[1]
    ] = source_part
    return full


def mask_to_yolo_polygons(mask):
    # Convert a binary mask to YOLO-format normalized polygons.

    # Returns a list of polygons, each one is [x1, y1, x2, y2, ...].
    h, w = mask.shape
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    total_area = h * w
    polygons = []

    for cnt in contours:
        # Skip bad contours
        if len(cnt) < 3:
            continue
        # Skip tiny noise contours (less than 0.5% of image area)
        if cv2.contourArea(cnt) < total_area * 0.005:
            continue

        # Simplify the contour - fewer points means faster training
        epsilon = 0.002 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) < 3:
            continue

        # Normalize coordinates to [0, 1]
        coords = []
        for pt in approx:
            px, py = pt[0]
            coords.append(round(px / w, 6))
            coords.append(round(py / h, 6))
        polygons.append(coords)

    return polygons


def find_image_for(json_path):
    # Find the source image that goes with a LabelMe JSON file
    stem = json_path.stem
    for ext in [".jpg", ".JPG", ".jpeg", ".JPEG", ".png", ".PNG"]:
        candidate = json_path.parent / (stem + ext)
        if candidate.exists():
            return candidate
    return None


def process_one(json_path, out_img_dir, out_lbl_dir):
    # Convert one LabelMe JSON + image into a resized image + YOLO label.

    # Returns True on success, False if skipped.
    
    with open(json_path) as f:
        data = json.load(f)

    img_w = data["imageWidth"]
    img_h = data["imageHeight"]

    # Merge all annotation shapes into one binary mask
    combined = np.zeros((img_h, img_w), dtype=np.uint8)
    for shape in data["shapes"]:
        if shape["shape_type"] == "mask" and shape.get("mask"):
            m = decode_labelme_mask(shape, img_w, img_h)
            combined = np.maximum(combined, m)

    # Find the source image
    img_path = find_image_for(json_path)
    if img_path is None:
        print(f"  [!] No image for {json_path.name}, skip")
        return False

    # Resize and save the image
    stem = json_path.stem
    img = Image.open(img_path).convert("RGB")
    img_resized = img.resize(IMG_SIZE, Image.LANCZOS)
    img_resized.save(out_img_dir / (stem + ".jpg"), quality=95)

    # Resize the mask and extract polygons
    mask_pil = Image.fromarray(combined * 255)
    mask_resized = mask_pil.resize(IMG_SIZE, Image.NEAREST)
    mask_arr = (np.array(mask_resized) > 127).astype(np.uint8)

    polygons = mask_to_yolo_polygons(mask_arr)
    if not polygons:
        print(f"  [!] No valid polygons for {stem}, skip")
        return False

    # Write the YOLO seg label - one polygon per line, prefixed with class id
    label_path = out_lbl_dir / (stem + ".txt")
    with open(label_path, "w") as f:
        for poly in polygons:
            # Build "x1 y1 x2 y2 ..." string
            parts = []
            for c in poly:
                parts.append(str(c))
            coords_str = " ".join(parts)
            f.write(f"0 {coords_str}\n")

    return True


def main():
    random.seed(SEED)

    jsons = sorted(SRC_DIR.glob("*.json"))
    print(f"Found {len(jsons)} annotation files in {SRC_DIR}")

    # Shuffle indices and pick the first n_val for validation
    indices = list(range(len(jsons)))
    random.shuffle(indices)
    n_val = max(1, int(len(jsons) * VAL_RATIO))
    val_idx = set(indices[:n_val])

    # Create output directories
    for split in ["train", "val"]:
        for sub in ["images", "labels"]:
            out_path = OUT_DIR / split / sub
            out_path.mkdir(parents=True, exist_ok=True)

    # Process each annotation
    ok = 0
    train_n = 0
    val_n = 0

    for i, jp in enumerate(jsons):
        if i in val_idx:
            split = "val"
        else:
            split = "train"

        img_dir = OUT_DIR / split / "images"
        lbl_dir = OUT_DIR / split / "labels"

        if process_one(jp, img_dir, lbl_dir):
            ok += 1
            if split == "val":
                val_n += 1
            else:
                train_n += 1

    # Write dataset.yaml that YOLO uses to find everything
    yaml_path = OUT_DIR / "dataset.yaml"
    yaml_text = (
        f"path: {OUT_DIR.resolve()}\n"
        f"train: train/images\n"
        f"val: val/images\n"
        f"\n"
        f"names:\n"
        f"  0: plant\n"
    )
    yaml_path.write_text(yaml_text)

    print(f"\nDone. {ok}/{len(jsons)} converted.")
    print(f"  Train: {train_n} images")
    print(f"  Val:   {val_n} images")
    print(f"  Size:  {IMG_SIZE[0]}x{IMG_SIZE[1]}")
    print(f"  YAML:  {yaml_path}")


if __name__ == "__main__":
    main()
