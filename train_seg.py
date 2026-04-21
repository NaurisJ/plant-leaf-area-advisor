
<<<<<<< HEAD
Usage:
    python train_seg.py              # train from scratch
    python train_seg.py --resume     # resume interrupted training
"""
=======
# Train YOLOv11-seg on the prepared dataset.

# Usage:
# python train_seg.py # train from scratch
# python train_seg.py --resume # resume interrupted training

>>>>>>> f1c9ad3 (temp-fix)

import sys
from pathlib import Path
from ultralytics import YOLO

DATASET_YAML = Path(__file__).parent / "dataset" / "dataset.yaml"

<<<<<<< HEAD
# ── Training config ──
MODEL    = "yolo11n-seg.pt"   # nano — fast on CPU, good for 196 images
=======
# Training config
MODEL    = "yolo11n-seg.pt" # nano — fast on CPU
>>>>>>> f1c9ad3 (temp-fix)
EPOCHS   = 100
IMG_SIZE = 640
BATCH    = 8                  # small batch for CPU / low RAM
PATIENCE = 20                 # early stopping if no improvement for 20 epochs
PROJECT  = str(Path(__file__).parent / "runs")
NAME     = "plant_seg"


def main():
    resume = "--resume" in sys.argv

    if resume:
        # Find last checkpoint
        last = Path(PROJECT) / NAME / "weights" / "last.pt"
        if not last.exists():
            print(f"No checkpoint found at {last}")
            return
        print(f"Resuming from {last}")
        model = YOLO(str(last))
        model.train(resume=True)
    else:
        model = YOLO(MODEL)
        model.train(
            data=str(DATASET_YAML),
            epochs=EPOCHS,
            imgsz=IMG_SIZE,
            batch=BATCH,
            patience=PATIENCE,
            project=PROJECT,
            name=NAME,
            exist_ok=True,
            # Augmentation — important for small datasets
            hsv_h=0.015,    # hue shift
            hsv_s=0.5,      # saturation shift
            hsv_v=0.3,      # value shift
            degrees=15,     # rotation
            flipud=0.5,     # vertical flip
            fliplr=0.5,     # horizontal flip
            scale=0.3,      # scale jitter
            mosaic=0.8,     # mosaic augmentation
            # Save
            save=True,
            save_period=25,  # checkpoint every 25 epochs
            plots=True,
            verbose=True,
        )

    print("\nTraining complete!")
    best = Path(PROJECT) / NAME / "weights" / "best.pt"
    print(f"Best model: {best}")


if __name__ == "__main__":
    main()
