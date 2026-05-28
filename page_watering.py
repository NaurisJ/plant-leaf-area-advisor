# Watering - watering journal

from datetime import date
from io import BytesIO

import matplotlib.pyplot as plt
import streamlit as st

from helpers import get_plant_ids, load_watering, open_conn

AMOUNT_LABEL = "Daudzums (ml)"

st.title("Laistīšanas žurnāls")
st.caption("Reģistrējiet laistīšanas notikumus. Padomdevējs tos ņem vērā, "
           "novērtējot auga stāvokli.")

plants = get_plant_ids()
if not plants:
    st.info("Vispirms pievienojiet augus sadaļā 'Augi'.")
    st.stop()

# Add new entry
with st.form("water_log", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    plant = c1.selectbox("Augs", plants)
    wdate = c2.date_input("Datums", value=date.today(), max_value=date.today())
    amount = c3.number_input(AMOUNT_LABEL, min_value=0, value=200, step=50)
    notes = st.text_input("Piezīmes", placeholder="neobligāti")

    if st.form_submit_button("Reģistrēt", type="primary"):
        conn = open_conn()
        conn.execute(
            "INSERT INTO watering_events (plant_id, date, amount_ml, notes) "
            "VALUES (?, ?, ?, ?)",
            (plant, wdate.isoformat(), float(amount), notes or None))
        conn.commit()
        conn.close()
        st.success(f"Reģistrēts: {plant} - {wdate} - {amount} ml")
        st.rerun()

# Entry history
st.subheader("Ieraksti")
df = load_watering()

if df.empty:
    st.info("Nav reģistrētu laistīšanas notikumu.")
    st.stop()

total_events = len(df)
total_amount = df["amount_ml"].fillna(0).sum()
last_date = df["date"].dropna().max()
if last_date is not None:
    last_date_text = last_date.strftime("%Y-%m-%d")
else:
    last_date_text = "nav datu"

c1, c2, c3 = st.columns(3)
c1.metric("Ieraksti", total_events)
c2.metric("Kopējais daudzums", f"{total_amount:.0f} ml")
c3.metric("Pēdējā laistīšana", last_date_text)

# Table
table = df[["plant_id", "date", "amount_ml", "notes"]].copy()
table["date"] = table["date"].dt.strftime("%Y-%m-%d")
table.columns = ["Augs", "Datums", AMOUNT_LABEL, "Piezīmes"]
st.dataframe(table, use_container_width=True, hide_index=True)

csv_text = "sep=;\n" + table.to_csv(index=False, sep=";")
csv_data = csv_text.encode("utf-8-sig")

chart_df = df[["date", "amount_ml"]].copy()
chart_df = chart_df.dropna(subset=["date"])
chart_df["date"] = chart_df["date"].dt.strftime("%Y-%m-%d")
chart_df["amount_ml"] = chart_df["amount_ml"].fillna(0)
chart_df = chart_df.groupby("date")["amount_ml"].sum().reset_index()
chart_df = chart_df.sort_values("date")

st.subheader("Laistīšanas dinamika")
display_chart = chart_df.set_index("date")[["amount_ml"]].copy()
display_chart.columns = [AMOUNT_LABEL]
st.bar_chart(display_chart, y_label=AMOUNT_LABEL, x_label="Datums")

chart_image = BytesIO()
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(chart_df["date"], chart_df["amount_ml"])
ax.set_title("Laistīšanas daudzums")
ax.set_xlabel("Datums")
ax.set_ylabel(AMOUNT_LABEL)
ax.grid(True, axis="y")
ax.tick_params(axis="x", labelrotation=35)
fig.tight_layout()
fig.savefig(chart_image, format="png", dpi=160)
plt.close(fig)
chart_image.seek(0)

st.subheader("Eksports")
e1, e2 = st.columns(2)
e1.download_button(
    "Lejupielādēt CSV",
    data=csv_data,
    file_name="laistisana.csv",
    mime="text/csv")
e2.download_button(
    "Lejupielādēt diagrammu",
    data=chart_image.getvalue(),
    file_name="laistisana_diagramma.png",
    mime="image/png")

# Delete by ID
st.subheader("Dzēst ierakstu")

# Get ready label for each entry: "Plant1 / 2026-04-15 / 200 ml"
ids = []
labels = {}
for _, row in df.iterrows():
    rid = int(row["id"])
    date_str = row["date"].strftime("%Y-%m-%d")

    if row["amount_ml"]:
        ml = int(row["amount_ml"])
    else:
        ml = 0

    ids.append(rid)
    labels[rid] = f"{row['plant_id']} / {date_str} / {ml} ml"

def show_record(i):
    return labels[i]

chosen = st.selectbox(
    "Izvēlieties ierakstu", ids, format_func=show_record)

if st.button("Dzēst"):
    conn = open_conn()
    conn.execute("DELETE FROM watering_events WHERE id=?", (int(chosen),))
    conn.commit()
    conn.close()
    st.warning("Dzēsts.")
    st.rerun()
