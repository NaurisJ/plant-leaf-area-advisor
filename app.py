# Main file to run app
# To run execute - streamlit run app.py
# To get requirements for running app execute - pip install -r requirements.txt

from pathlib import Path

import streamlit as st

from helpers import MODEL_PATH

st.set_page_config(
    page_title="Augu padomdevējs",
    layout="wide",
    initial_sidebar_state="expanded")

# Small shared styling for a cleaner Streamlit UI.
st.markdown(
    """
    <style>
    :root {
        --text: #26312a;
        --muted: #667267;
        --green: #4f8a63;
        --green-dark: #2f6444;
        --green-soft: #edf5ee;
        --line: #dfe8dc;
        --page: #f7f8f4;
        --paper: #ffffff;
    }

    .stApp {
        background: var(--page);
    }

    .block-container {
        max-width: 1180px;
        padding-top: 1.6rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid var(--line);
    }

    [data-testid="stSidebarNav"] a {
        border-radius: 8px;
        margin: 0.08rem 0;
        padding: 0.42rem 0.55rem;
    }

    [data-testid="stSidebarNav"] a:hover {
        background-color: var(--green-soft);
    }

    .brand-card {
        background-color: var(--green-soft);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.9rem;
        margin-bottom: 1rem;
    }

    .brand-title {
        color: var(--text);
        font-weight: 800;
        margin-bottom: 0.2rem;
    }

    .brand-text {
        color: var(--muted);
        font-size: 0.84rem;
        line-height: 1.35;
    }

    h1, h2, h3 {
        color: var(--text);
    }

    h1 {
        padding-bottom: 0.45rem;
        border-bottom: 1px solid var(--line);
    }

    [data-testid="stMetric"] {
        background-color: var(--paper);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.85rem 1rem;
        box-shadow: 0 4px 14px rgba(38, 49, 42, 0.04);
    }

    [data-testid="stMetric"] label {
        color: var(--muted);
    }

    [data-testid="stDataFrame"],
    [data-testid="stExpander"] {
        border: 1px solid var(--line);
        border-radius: 8px;
        background-color: var(--paper);
    }

    [data-testid="stAlert"] {
        border-radius: 8px;
    }

    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stDateInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {
        border-radius: 8px;
    }

    div.stButton > button,
    div.stDownloadButton > button {
        border-radius: 8px;
        border-color: var(--green);
        color: var(--green-dark);
        font-weight: 650;
    }

    div.stButton > button:hover,
    div.stDownloadButton > button:hover {
        background-color: var(--green-soft);
        border-color: var(--green-dark);
        color: var(--green-dark);
    }

    div.stButton > button[kind="primary"],
    div.stFormSubmitButton > button[kind="primary"] {
        background-color: var(--green);
        border-color: var(--green);
        color: white;
    }

    #MainMenu, footer {
        visibility: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True)

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

st.sidebar.markdown(
    """
    <div class="brand-card">
        <div class="brand-title">Augu padomdevējs</div>
        <div class="brand-text">
            Lapu laukuma mērījumi un laistīšanas padomdevējs.
        </div>
    </div>
    """,
    unsafe_allow_html=True)

nav = st.navigation(pages)
nav.run()
