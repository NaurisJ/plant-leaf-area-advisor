# History page - canopy trend and watering advisor
import streamlit as st

from advisor import advise
from helpers import load_measurements, watering_for

st.title("Vēsture un padomdevējs")

df = load_measurements()
if df.empty:
    st.info("Datubāzē nav mērījumu.")
    st.stop()

plants = []
for p in df["plant_id"].unique():
    if p != "Unknown":
        plants.append(p)
plants.sort()

if not plants:
    st.warning("Nav reģistrētu augu.")
    st.stop()

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

sub = df[(df["plant_id"] == plant) & (df["view"] == view)]
sub = sub.dropna(subset=["date"]).sort_values("date")

if sub.empty:
    st.warning(f"Nav datu: {plant} / {view}")
    st.stop()

chart_df = sub.set_index("date")[["leaf_area_pct"]]
chart_df.columns = [f"{plant} ({view})"]
st.line_chart(chart_df, y_label="Lapotne (%)", x_label="Datums")

history = []
for _, row in sub.iterrows():
    date_str = row["date"].strftime("%Y-%m-%d")
    frac = float(row["leaf_area_fraction"])
    history.append((date_str, frac))

watering = watering_for(plant)
rec = advise(history, watering_events=watering)

# st.subheader("Ieteikums")
# message = f"**{rec.title}**\n\n{rec.message}"
# if rec.action:
#     message += f"\n\n**Darbība:** {rec.action}"

# if rec.level == "error":
#     st.error(message)
# elif rec.level == "warning":
#     st.warning(message)
# elif rec.level == "success":
#     st.success(message)
# else:
#     st.info(message)

c1, c2, c3 = st.columns(3)
c1.metric("Pēdējais mērījums", f"{rec.latest_pct:.2f}%")
if rec.days_between_latest is not None:
    c2.metric("Dienas starp mērījumiem", f"{rec.days_between_latest}")
else:
    c2.metric("Dienas starp mērījumiem", "nav datu")
if rec.days_since_water is not None:
    c3.metric("Kopš laistīšanas", f"{rec.days_since_water} d")
else:
    c3.metric("Kopš laistīšanas", "nav datu")

c4, c5, c6 = st.columns(3)
if rec.rgr is not None:
    c4.metric("Pēdējais RGR", f"{rec.rgr * 100:+.2f}%/d")
else:
    c4.metric("Pēdējais RGR", "nav datu")
if rec.rgr_baseline_mean is not None:
    c5.metric("Bāzes RGR", f"{rec.rgr_baseline_mean * 100:+.2f}%/d")
else:
    c5.metric("Bāzes RGR", "nav datu")
c6.metric("Pārliecība", f"{rec.confidence.upper()} ({rec.confidence_score}/5)")

with st.expander("Ko nozīmē pārliecība?"):
    st.write(
        "Pārliecība nav segmentācijas modeļa precizitāte. Tā rāda, cik "
        "daudz konteksta ir padomdevējam: mērījumu skaits, iepriekšējo RGR "
        "pāru skaits bāzlīnijai un vai ir reģistrēta laistīšanas vēsture."
    )

with st.expander("Īss aprēķina pamatojums", expanded=True):
    for line in rec.details:
        st.text(line)

st.subheader("Mērījumi")
table = sub[["date", "filename", "leaf_area_pct", "notes"]].copy()
table.columns = ["Datums", "Fails", "Lapotne %", "Piezīmes"]
st.dataframe(table, use_container_width=True, hide_index=True)
