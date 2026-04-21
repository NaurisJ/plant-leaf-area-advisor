# History page - canopy trend and watering advisor
import streamlit as st

from advisor import advise
from helpers import load_measurements, watering_for

st.title("Vēsture un padomdevējs")

df = load_measurements()
if df.empty:
    st.info("Datubāzē nav mērījumu.")
    st.stop()

# Plants to choose from"

plants = []
for p in df["plant_id"].unique():
    if p != "Unknown":
        plants.append(p)
plants.sort()

if not plants:
    st.warning("Nav reģistrētu augu.")
    st.stop()

# Views to choose from
views = []
for v in df["view"].dropna().unique():
    if v != "unknown":
        views.append(v)
views.sort()

if not views:
    views = ["top"]

# Default - choose top, if its available
if "top" in views:
    view_idx = views.index("top")
else:
    view_idx = 0

c1, c2 = st.columns([2, 1])
plant = c1.selectbox("Augs", plants)
view = c2.selectbox("Skats", views, index=view_idx)

# Filtered data
sub = df[(df["plant_id"] == plant) & (df["view"] == view)]
sub = sub.dropna(subset=["date"]).sort_values("date")

if sub.empty:
    st.warning(f"Nav datu: {plant} / {view}")
    st.stop()

# Diagramm
chart_df = sub.set_index("date")[["leaf_area_pct"]]
chart_df.columns = [f"{plant} ({view})"]
st.line_chart(chart_df, y_label="Lapotne (%)", x_label="Datums")

# Get the history ready for advisor - date, area in pairs
history = []
for _, row in sub.iterrows():
    date_str = row["date"].strftime("%Y-%m-%d")
    frac = float(row["leaf_area_fraction"])
    history.append((date_str, frac))

watering = watering_for(plant)
rec = advise(history, watering_events=watering)

# Advisor advice
st.subheader("Ieteikums")
if rec.level == "error":
    st.error(f"**{rec.title}**\n\n{rec.message}")
elif rec.level == "warning":
    st.warning(f"**{rec.title}**\n\n{rec.message}")
elif rec.level == "success":
    st.success(f"**{rec.title}**\n\n{rec.message}")
else:
    st.info(f"**{rec.title}**\n\n{rec.message}")

# Main metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pēdējais mērījums", f"{rec.latest_pct:.2f}%")
if rec.rgr is not None:
    c2.metric("RGR", f"{rec.rgr * 100:+.2f}%/d")
if rec.z_score is not None:
    c3.metric("Novirze", f"{rec.z_score:+.2f}σ")
c4.metric("Pārliecība", rec.confidence.upper())

with st.expander("Detalizēta informācija"):
    for line in rec.details:
        st.text(line)

# Measurements table
st.subheader("Mērījumi")
table = sub[["date", "filename", "leaf_area_pct", "notes"]].copy()
table.columns = ["Datums", "Fails", "Lapotne %", "Piezīmes"]
st.dataframe(table, use_container_width=True, hide_index=True)
