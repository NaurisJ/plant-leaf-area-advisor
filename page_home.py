# Homepage - overview of measurements and warnings

import streamlit as st

from advisor import advise
from helpers import get_plant_ids, load_measurements, watering_for

st.title("Sākumlapa")

df = load_measurements()
plants = get_plant_ids()

if df.empty:
    st.info("Datubāzē vēl nav mērījumu. Sāciet sadaļā 'Jauns mērījums'.")
    st.stop()

# Main statistics
total_measurements = len(df)
total_plants = len(plants)
last_session = df["date"].dropna().max()

if last_session:
    last_session_str = last_session.strftime("%Y-%m-%d")
else:
    last_session_str = "—"

# Check every plant if there are warnings
warnings = []
for pid in plants:
    # Take top view if available, otherwise all views
    sub = df[(df["plant_id"] == pid) & (df["view"] == "top")]
    if sub.empty:
        sub = df[df["plant_id"] == pid]
    sub = sub.dropna(subset=["date"]).sort_values("date")

    # Get ready history view as date and area pairs
    history = []
    for _, row in sub.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d")
        frac = float(row["leaf_area_fraction"])
        history.append((date_str, frac))

    rec = advise(history, watering_events=watering_for(pid))
    if rec.status in ("stress", "warning"):
        warnings.append((pid, rec))

# Metrics row
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mērījumi", total_measurements)
c2.metric("Augi", total_plants)
c3.metric("Pēdējā sesija", last_session_str)
c4.metric("Brīdinājumi", len(warnings))

# Warnings
if warnings:
    st.subheader("Nepieciešama uzmanība")
    for pid, rec in warnings:
        if rec.level == "error":
            st.error(f"**{pid}** - {rec.title}")
        else:
            st.warning(f"**{pid}** - {rec.title}")
else:
    st.success("Visi augi šobrīd ir stabilā stāvoklī.")

# Leaf area diagramm
st.subheader("Lapotnes laukums laika gaitā")
top_df = df[(df["view"] == "top") & (df["plant_id"] != "Unknown")]
top_df = top_df.dropna(subset=["date"])

if top_df.empty:
    st.info("Nav 'top' skata mērījumu, ko parādīt.")
else:
    chart_df = top_df.pivot_table(
        index="date", columns="plant_id", values="leaf_area_pct"
    ).sort_index()
    st.line_chart(chart_df, y_label="Lapotne (%)", x_label="Datums")
