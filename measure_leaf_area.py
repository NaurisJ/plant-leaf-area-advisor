
# Salix integra leaf-area measurement using a trained YOLOv11-seg model.


# Execution - image -> YOLOv11-seg -> plant mask -> pixel count -> area fraction -> SQLite

# Usage:
# python measure_leaf_area.py (process default dir)
# python measure_leaf_area.py path/to/img.jpg ... (specific images)
# python measure_leaf_area.py --debug (save visuals)
import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


# Config
IMAGE_DIRS = ["all_photos", "images"]
DB_PATH = "leaf_area.db"
DEBUG_DIR = "debug_masks"
MODEL_PATH = "best.pt"
IMG_SIZE = 640
CONF_THRESH = 0.25 # min confidence to count a detection
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}


# Metadata

def parse_meta(filename):
    # Parse only the date from a filename.
    name = Path(filename).stem

    # Find date in DDMMYYYY format
    date = None
    match = re.search(r"(\d{2})(\d{2})(\d{4})", name)
    if match:
        day = match.group(1)
        month = match.group(2)
        year = match.group(3)
        try:
            candidate = datetime(int(year), int(month), int(day))
            today = datetime.now()
            # Reject incorrect dates
            if 2010 <= candidate.year <= today.year + 1 and candidate <= today:
                date = candidate
        except ValueError:
            date = None

    return {"date": date}


# Measurement

def run_inference(model, img_bgr):
    # Run the seg model, returns (plant_mask, method, max_confidence)
    # Used by both the CLI and the Streamlit app so the logic
    # lives in one place
    
    h, w = img_bgr.shape[:2]
    results = model.predict(img_bgr, imgsz=IMG_SIZE, conf=CONF_THRESH, verbose=False, retina_masks=True)
    r = results[0]

    plant_mask = np.zeros((h, w), dtype=np.uint8)
    method = "segmodel"
    max_conf = 0.0

    # if the model did not find any masks, return the empty mask
    if r.masks is None:
        return plant_mask, "none", 0.0

    if len(r.masks.data) == 0:
        return plant_mask, "none", 0.0

    # Save the highest confidence score if there is one
    if r.boxes is not None and len(r.boxes.conf) > 0:
        max_conf = float(r.boxes.conf.max())

    # YOLO can return several masks.
    # This combines all detected masks into one final plant mask.
    all_masks = r.masks.data.cpu().numpy()

    for one_mask in all_masks:
        white_mask = one_mask > 0.5
        white_mask = white_mask.astype(np.uint8)
        white_mask = white_mask * 255

        if white_mask.shape != (h, w):
            white_mask = cv2.resize(white_mask,(w, h),interpolation=cv2.INTER_NEAREST)

        plant_mask = np.maximum(plant_mask, white_mask)

    return plant_mask, method, max_conf


def render_overlay(img_bgr, plant_mask):
    # return the image with the plant mask drawn on top
    vis = img_bgr.copy()

    # Green tint inside the mask
    overlay = vis.copy()
    # wherever the mask is white, paint the overlay green
    overlay[plant_mask == 255] = (0, 255, 0)
    vis = cv2.addWeighted(overlay, 0.4, vis, 0.6, 0)

    return vis


def measure_image(model, img_path, debug=False):
    # Run the model on one image and return measurement.
    # Returns None if the image cannot be read.
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        print(f"  [!] Cannot read: {Path(img_path).name}")
        return None

    h, w = img_bgr.shape[:2]
    total_px = h * w

    plant_mask, method, _ = run_inference(model, img_bgr)

    leaf_px = int(np.count_nonzero(plant_mask))
    if total_px > 0:
        leaf_area_fraction = leaf_px / total_px
    else:
        leaf_area_fraction = 0

    meta = parse_meta(Path(img_path).name)

    if meta["date"] is not None:
        date = meta["date"].isoformat()
    else:
        date = None
    result = {
        "filename": Path(img_path).name,
        "plant_id": None,
        "date": date,
        "view": "unknown",
        "leaf_area_fraction": leaf_area_fraction,
        "leaf_area_px": leaf_px,
        "image_area_px": total_px,
        "detection_method": method,
        "image_width": w,
        "image_height": h,
    }

    # Save a debug visualisation if asked
    if debug:
        os.makedirs(DEBUG_DIR, exist_ok=True)

        debug_image = render_overlay(img_bgr, plant_mask)

        image_stem = Path(img_path).stem
        debug_filename = image_stem + "_debug.jpg"
        debug_path = os.path.join(DEBUG_DIR, debug_filename)

        cv2.imwrite(debug_path, debug_image)

    return result


# Database

def init_db(db_path):
    # open the database and create all tables if they don't exist yet
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(
        "CREATE TABLE IF NOT EXISTS species ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "latin_name TEXT NOT NULL UNIQUE, "
        "common_name TEXT"
        ")"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS plants ("
        "plant_id TEXT PRIMARY KEY, "
        "display_name TEXT, "
        "species TEXT, "
        "notes TEXT, "
        "created_at TEXT DEFAULT (datetime('now')), "
        "FOREIGN KEY (species) REFERENCES species(latin_name) "
        "ON UPDATE CASCADE ON DELETE SET NULL"
        ")"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS measurements ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "filename TEXT NOT NULL, "
        "plant_id TEXT, "
        "date TEXT, "
        "view TEXT, "
        "leaf_area_fraction REAL, "
        "leaf_area_px INTEGER, "
        "image_area_px INTEGER, "
        "detection_method TEXT, "
        "image_width INTEGER, "
        "image_height INTEGER, "
        "canopy_area_cm2 REAL, "
        "calibration_object TEXT, "
        "calibration_cm REAL, "
        "calibration_px REAL, "
        "notes TEXT, "
        "processed_at TEXT DEFAULT (datetime('now')), "
        "FOREIGN KEY (plant_id) REFERENCES plants(plant_id) "
        "ON UPDATE CASCADE ON DELETE CASCADE"
        ")"
    )

    conn.execute(
        "CREATE TABLE IF NOT EXISTS watering_events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "plant_id TEXT NOT NULL, "
        "date TEXT NOT NULL, "
        "amount_ml REAL, "
        "notes TEXT, "
        "logged_at TEXT DEFAULT (datetime('now')), "
        "FOREIGN KEY (plant_id) REFERENCES plants(plant_id) "
        "ON UPDATE CASCADE ON DELETE CASCADE"
        ")"
        )

    # Insert into the species table with the trained species if its empty
    n = conn.execute("SELECT COUNT(*) FROM species").fetchone()[0]
    if n == 0:
        conn.execute(
            "INSERT INTO species (latin_name, common_name) VALUES (?, ?)",
            ("Salix integra 'Hakuro Nishiki'", "Japānas vītols"))

    conn.commit()
    return conn


def list_species(conn):
    # All species, sorted by latin name
    rows = conn.execute(
        "SELECT id, latin_name, common_name FROM species "
        "ORDER BY latin_name").fetchall()
    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "latin_name": r[1],
            "common_name": r[2],
        })
    return result


def ensure_plant(conn, plant_id, display_name=None, species=None):
    # Insert a plant row if it doesnt exist yet
    if not plant_id or plant_id == "Unknown":
        return
    conn.execute(
        "INSERT OR IGNORE INTO plants (plant_id, display_name, species) "
        "VALUES (?, ?, ?)",
        (plant_id, display_name or plant_id, species))
    conn.commit()


def list_plants(conn):
    known_plants = {}

    plant_rows = conn.execute(" SELECT plant_id, display_name, species, notes FROM plants ").fetchall()

    for row in plant_rows:
        plant_id = row[0]
        display_name = row[1]
        species = row[2]
        notes = row[3]

        if display_name is None:
            display_name = plant_id

        plant = {
            "plant_id": plant_id,
            "display_name": display_name,
            "species": species,
            "notes": notes
        }

        known_plants[plant_id] = plant

    measurement_rows = conn.execute(" SELECT DISTINCT plant_id FROM measurements "
        " WHERE plant_id IS NOT NULL "
        "AND plant_id != 'Unknown' ").fetchall()

    for row in measurement_rows:
        plant_id = row[0]

        if plant_id not in known_plants:
            plant = {
                "plant_id": plant_id,
                "display_name": plant_id,
                "species": None,
                "notes": None
            }

            known_plants[plant_id] = plant

    plants = list(known_plants.values())
    plants = sorted(plants, key=lambda plant: plant["plant_id"])

    return plants


def save_measurement(conn, measurement):
    "Save a measurement, replace any existing row with the same filename"
    filename = measurement["filename"]
    plant_id = measurement.get("plant_id")

    if plant_id == "Unknown":
        plant_id = None
        measurement["plant_id"] = None

    if plant_id is not None:
        ensure_plant(conn, plant_id)

    # Remove the old result for this filename.
    # This stops the same image from appearing twice if the script is rerun.
    conn.execute("DELETE FROM measurements WHERE filename = ?",(filename,))

    conn.execute(" INSERT INTO measurements (filename, plant_id, date, view, leaf_area_fraction, "
            "leaf_area_px, image_area_px, detection_method, "
            " image_width, image_height, canopy_area_cm2, "
            "calibration_object, calibration_cm, calibration_px, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    , (
        measurement["filename"],
        measurement["plant_id"],
        measurement["date"],
        measurement["view"],
        measurement["leaf_area_fraction"],
        measurement["leaf_area_px"],
        measurement["image_area_px"],
        measurement["detection_method"],
        measurement["image_width"],
        measurement["image_height"],
        measurement.get("canopy_area_cm2"),
        measurement.get("calibration_object"),
        measurement.get("calibration_cm"),
        measurement.get("calibration_px"),
        measurement.get("notes"),
    ))

    conn.commit()

# Main (CLI)

def find_images(paths):
    "turn files and folders into a list of image paths"
    image_paths = []

    for path in paths:
        if os.path.isfile(path):
            image_paths.append(path)

        elif os.path.isdir(path):
            filenames = os.listdir(path)
            filenames = sorted(filenames)

            for filename in filenames:
                extension = Path(filename).suffix

                if extension in IMAGE_EXT:
                    full_path = os.path.join(path, filename)
                    image_paths.append(full_path)

    return image_paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="*")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--model", default=MODEL_PATH)
    args = parser.parse_args()

    # Use the folder where this script is stored
    script_folder = Path(__file__).parent
    os.chdir(script_folder)

    conn = init_db(DB_PATH)

    # Find images to process
    if args.images:
        image_paths = find_images(args.images)
    else:
        image_paths = []
        for folder in IMAGE_DIRS:
            if os.path.isdir(folder):
                image_paths = find_images([folder])

                if len(image_paths) > 0:
                    print("Using directory:", folder + "/")
                    break

    if len(image_paths) == 0:
        print("No images found.")
        conn.close()
        sys.exit(1)

    # Check the model exists
    if not os.path.exists(args.model):
        print(f"[!] Model not found: {args.model}")
        print("Train it first: python train_seg.py")
        sys.exit(1)

    print(f"Loading model: {args.model}")
    model = YOLO(args.model)

    print(f"Processing {len(image_paths)} images...\n")
    successful_images = 0

    for image_path in image_paths:
        result = measure_image(model, image_path, debug=args.debug)

        if result is None:
            continue

        save_measurement(conn, result)
        successful_images = successful_images + 1

        leaf_percent = result["leaf_area_fraction"] * 100
        image_name = Path(image_path).name

        if result["date"] is None:
            date_text = "no-date"
        else:
            date_text = result["date"][:10]

        if result["detection_method"] == "none":
            flag = "  [no-mask]"
        else:
            flag = ""

        print(
            "  "
            + image_name.ljust(50)
            + " "
            + (result["plant_id"] or "Unknown").ljust(10)
            + " "
            + date_text.ljust(12)
            + " "
            + format(leaf_percent, "6.2f")
            + "%"
            + flag
        )
        
    print()
    print(f"\nDone. {successful_images}/{len(image_paths)} processed.")
    print(f"Results: {DB_PATH}")
    conn.close()
