# Watering - watering journal

from datetime import date

import streamlit as st

from helpers import get_plant_ids, load_watering, open_conn

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
    amount = c3.number_input("Daudzums (ml)", min_value=0, value=200, step=50)
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

# Table
table = df[["plant_id", "date", "amount_ml", "notes"]].copy()
table["date"] = table["date"].dt.strftime("%Y-%m-%d")
table.columns = ["Augs", "Datums", "Daudzums (ml)", "Piezīmes"]
st.dataframe(table, use_container_width=True, hide_index=True)

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
