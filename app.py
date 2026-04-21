# Main file to run app
# To run execute - streamlit run app.py
# To get requirements for running app execute - pip install -r requirements.txt

from pathlib import Path

import streamlit as st

from helpers import MODEL_PATH

st.set_page_config(page_title="Augu padomdevējs", layout="wide")

# Check, if model is available
if not Path(MODEL_PATH).exists():
    st.error(
        f"Modelis nav atrasts: {MODEL_PATH}. "
        "Apmāciet modeli ar: python train_seg.py")
    st.stop()

# Pages, each in seperate file.
pages = [
    st.Page("page_home.py", title="Sākumlapa", default=True),
    st.Page("page_measure.py", title="Jauns mērījums"),
    st.Page("page_history.py", title="Vēsture"),
    st.Page("page_plants.py", title="Augi"),
    st.Page("page_watering.py", title="Laistīšana"),
]

st.sidebar.caption(
    "Bakalaura darbs - mākslīgā intelekta algoritmu izmantošana "
    "augu lapu laukuma aprēķinam un laistīšanas padomdevējam.")

nav = st.navigation(pages)
nav.run()
