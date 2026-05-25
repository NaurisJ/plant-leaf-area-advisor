
# Shared functions for all pages.
from pathlib import Path

import pandas as pd
import streamlit as st
from ultralytics import YOLO

from measure_leaf_area import init_db


# Absolute paths - so things work no matter what cwd is
ROOT = Path(__file__).parent
DB_PATH = str(ROOT / "leaf_area.db")
MODEL_PATH = str(ROOT / "best.pt")


@st.cache_resource(show_spinner="Ielādē modeli...")
def load_model():
    #Load the trained YOLO model
    #Cached so only loads once per Streamlit session
    return YOLO(MODEL_PATH)


def open_conn():
    # Open the database and make sure tables exist
    return init_db(DB_PATH)


def load_measurements():
    # Get all measurements as a pandas DataFrame
    conn = init_db(DB_PATH)
    df = pd.read_sql(
        "SELECT * FROM measurements ORDER BY plant_id, date", conn)
    conn.close()

    if not df.empty:
        # Convert date strings to datetime
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        # Add a percent column for easier display
        df["leaf_area_pct"] = df["leaf_area_fraction"] * 100

    return df


def load_watering():
    # Get all watering events as a pandas DataFrame
    conn = init_db(DB_PATH)
    df = pd.read_sql(
        "SELECT * FROM watering_events ORDER BY date DESC", conn)
    conn.close()

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


def get_plant_ids():
    # List of all plant IDs
    conn = open_conn()
    rows = conn.execute(
        "SELECT plant_id FROM plants ORDER BY plant_id").fetchall()
    conn.close()

    result = []
    for row in rows:
        plant_id = row[0]
        if plant_id != "Unknown":
            result.append(plant_id)
    return result


def watering_for(plant_id):
    # Get watering events for one plant as (date, ml) pairs
    conn = init_db(DB_PATH)
    rows = conn.execute(
        "SELECT date, COALESCE(amount_ml, 0) FROM watering_events "
        "WHERE plant_id = ? ORDER BY date", (plant_id,)).fetchall()
    conn.close()
    return rows
