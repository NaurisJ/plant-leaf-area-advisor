#New measurement - upload photo, segment, save
from datetime import date, datetime

import cv2
import numpy as np
import streamlit as st

from helpers import get_plant_ids, load_model, open_conn
from measure_leaf_area import (
    ensure_plant,
    parse_meta,
    render_overlay,
    run_inference,
    save_measurement,
)

st.title("Jauns mērījums")
st.caption("Modelis ir apmācīts uz Salix integra 'Hakuro Nishiki'. "
           "Citām sugām rezultāti var nebūt precīzi.")

uploaded = st.file_uploader(
    "Attēls (.jpg / .png)", type=["jpg", "jpeg", "png"])

if uploaded is None:
    st.stop()

# Read the photo
file_bytes = np.frombuffer(uploaded.getvalue(), dtype=np.uint8)
img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
if img_bgr is None:
    st.error("Neizdevās nolasīt attēlu.")
    st.stop()

h, w = img_bgr.shape[:2]
total_px = h * w

# Segmentation
with st.spinner("Segmentē..."):
    model = load_model()
    plant_mask, method, _ = run_inference(model, img_bgr)

leaf_px = int(np.count_nonzero(plant_mask))
leaf_frac = leaf_px / max(total_px, 1)
leaf_pct = leaf_frac * 100

# Show the original and segmentation
c1, c2 = st.columns(2)
with c1:
    st.image(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB),
             caption="Oriģināls", use_container_width=True)
with c2:
    vis = render_overlay(img_bgr, plant_mask)
    st.image(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB),
             caption="Segmentācija", use_container_width=True)

if method == "none":
    st.warning("Modelis neatrada augu šajā attēlā.")
    st.stop()

c1, c2 = st.columns(2)
c1.metric("Lapotnes laukums", f"{leaf_pct:.2f}%")
c2.metric("Attēla izmērs", f"{w} x {h} px")

# Meta information - try to get from file name
parsed = parse_meta(uploaded.name)
plants = get_plant_ids()

st.subheader("Metainformācija")

# Dropdown of added plants and choice of adding a new one
plant_choices = plants + ["+ Jauns augs..."]

# Default - if file name contains a name in use, choose that
if parsed["plant_id"] in plants:
    selected_plant_index = plants.index(parsed["plant_id"])
else:
    # Else choose "+ Jauns augs..."
    selected_plant_index = len(plant_choices) - 1

plant_choice = st.selectbox("Augs", plant_choices, index=selected_plant_index)

# IF user chooses "+ Jauns augs...", show a new field
new_plant_id = ""
if plant_choice == "+ Jauns augs...":
    if parsed["plant_id"] != "Unknown":
        default_new = parsed["plant_id"]
    else:
        default_new = ""
    new_plant_id = st.text_input(
        "Jaunā auga identifikators", value=default_new,
        placeholder="piem. Plant9")

with st.form("save_form"):
    c1, c2 = st.columns(2)

    # Default date - from file or just today
    if parsed["date"]:
        default_date = parsed["date"].date()
    else:
        default_date = date.today()
    meas_date = c1.date_input("Datums", value=default_date,
                              max_value=date.today())

    # Default view - from file name or first
    view_opts = ["top", "front", "side"]
    if parsed["view"] in view_opts:
        view_idx = view_opts.index(parsed["view"])
    else:
        view_idx = 0
    view = c2.selectbox("Skats", view_opts, index=view_idx)

    notes = st.text_input("Piezīmes", placeholder="neobligāti")
    submitted = st.form_submit_button("Saglabāt", type="primary")

if submitted:
    # Detect which plant - new or existing
    if plant_choice == "+ Jauns augs...":
        final_plant = new_plant_id.strip()
    else:
        final_plant = plant_choice

    if not final_plant:
        st.error("Norādiet auga identifikatoru.")
        st.stop()

    result = {
        "filename": uploaded.name,
        "plant_id": final_plant,
        "date": datetime.combine(meas_date, datetime.min.time()).isoformat(),
        "view": view,
        "leaf_area_fraction": leaf_frac,
        "leaf_area_px": leaf_px,
        "image_area_px": total_px,
        "detection_method": method,
        "image_width": w,
        "image_height": h,
        "notes": notes or None,
    }
    conn = open_conn()
    ensure_plant(conn, final_plant)
    save_measurement(conn, result)
    conn.close()
    st.success(f"Saglabāts: {final_plant} / {meas_date} / {view}")
