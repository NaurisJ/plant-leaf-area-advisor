#New measurement - upload photo, segment, save
from datetime import date, datetime
import math

import cv2
import numpy as np
import streamlit as st
from PIL import Image

try:
    from streamlit_image_coordinates import streamlit_image_coordinates
except ImportError:
    streamlit_image_coordinates = None

from helpers import get_plant_ids, load_model, open_conn
from measure_leaf_area import (
    ensure_plant,
    parse_meta,
    render_overlay,
    run_inference,
    save_measurement,
)

NEW_PLANT_OPTION = "+ Jauns augs..."

st.title("Jauns mērījums")
st.caption("Modelis ir apmācīts uz Salix integra 'Hakuro Nishiki'. "
           "Citām sugām rezultāti nav.")

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

ys, xs = np.nonzero(plant_mask == 255)

plant_width_px = None
plant_height_px = None

if len(xs) > 0 and len(ys) > 0:
    left = xs.min()
    right = xs.max()

    top = ys.min()
    bottom = ys.max()

    plant_width_px = right - left
    plant_height_px = bottom - top
canopy_area_cm2 = None
calibration_object = None
calibration_cm = None
calibration_px = None

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
c1.metric("Lapotnes laukuma īpatsvars", f"{leaf_pct:.2f}%")
c2.metric("Attēla izmērs", f"{w} x {h} px")

st.subheader("Kalibrācija cm² aprēķinam")
st.caption(
    "Neobligāti. Izvēlieties zināmu references objektu un noklikšķiniet "
    "divus punktus pāri tā diametram vai platumam.")

use_calibration = st.checkbox("Aprēķināt aptuveno laukumu cm²")

if use_calibration:
    selected_calibration_cm = st.number_input(
        "References garums (cm)", min_value=0.1, value=15.0, step=0.1)

    if streamlit_image_coordinates is None:
        st.error(
            "Kalibrācijai nepieciešama streamlit-image-coordinates pakotne.")
        st.stop()

    if "calibration_points" not in st.session_state:
        st.session_state.calibration_points = []

    if st.button("Notīrīt kalibrācijas punktus"):
        st.session_state.calibration_points = []

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    display_width = min(700, w)
    display_height = int(h * display_width / w)
    img_small = cv2.resize(img_rgb, (display_width, display_height))
    pil_img = Image.fromarray(img_small)

    click = streamlit_image_coordinates(
        pil_img, key=f"calibration_{uploaded.name}")

    if click is not None:
        point = (int(click["x"]), int(click["y"]))
        points = st.session_state.calibration_points
        if len(points) == 0 or points[-1] != point:
            if len(points) >= 2:
                points = []
            points.append(point)
            st.session_state.calibration_points = points

    points = st.session_state.calibration_points
    if len(points) == 0:
        st.info("Klikšķiniet pirmo references punktu.")
    elif len(points) == 1:
        st.info("Klikšķiniet otro references punktu.")
    else:
        p1 = points[0]
        p2 = points[1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        calibration_px_small = math.sqrt(dx * dx + dy * dy)
        scale_to_original = w / display_width
        calibration_px = calibration_px_small * scale_to_original

        if calibration_px <= 0:
            st.warning("References punktiem jābūt atšķirīgās vietās.")
            st.stop()

        calibration_object = "Pielāgots references garums"
        calibration_cm = selected_calibration_cm
        cm_per_px = calibration_cm / calibration_px
        canopy_area_cm2 = leaf_px * cm_per_px * cm_per_px

        plant_width_cm = plant_width_px * cm_per_px
        plant_height_cm = plant_height_px * cm_per_px

        st.write(f"Platums: {plant_width_cm:.1f} cm")
        st.write(f"Augstums: {plant_height_cm:.1f} cm")

        st.success(
            f"References garums: {calibration_px:.1f} px. "
            f"Aptuvenais lapotnes projekcijas laukums: "
            f"{canopy_area_cm2:.1f} cm²")

# Meta information - try to get the date from file name
parsed = parse_meta(uploaded.name)
plants = get_plant_ids()

st.subheader("Metainformācija")

# Dropdown of added plants and choice of adding a new one
plant_choices = plants + [NEW_PLANT_OPTION]

# Default - if file name contains a name in use, choose that
selected_plant_index = len(plant_choices) - 1

plant_choice = st.selectbox("Augs", plant_choices, index=selected_plant_index)

# IF user chooses "+ Jauns augs...", show a new field
new_plant_id = ""
if plant_choice == NEW_PLANT_OPTION:
    new_plant_id = st.text_input(
        "Jaunā auga identifikators", value="",
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

    # View is selected manually.
    view_opts = ["top", "front"]
    view = c2.selectbox("Skats", view_opts, index=0)

    notes = st.text_input("Piezīmes", placeholder="neobligāti")
    submitted = st.form_submit_button("Saglabāt", type="primary")

if submitted:
    # Detect which plant - new or existing
    if plant_choice == NEW_PLANT_OPTION:
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
        "canopy_area_cm2": canopy_area_cm2,
        "calibration_object": calibration_object,
        "calibration_cm": calibration_cm,
        "calibration_px": calibration_px,
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
