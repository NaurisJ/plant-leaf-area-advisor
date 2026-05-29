# Watering - watering journal

from datetime import date
from io import BytesIO

import matplotlib.pyplot as plt
import pandas as pd
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

# Edit or delete entries
st.subheader("Laistīšanas ierakstu pārvaldība")
st.caption(
    "Labojiet ierakstus tieši tabulā. Atzīmējiet 'Dzēst', ja rinda "
    "jāizņem, un pēc tam saglabājiet izmaiņas.")

rows = []
for _, row in df.iterrows():
    if pd.notna(row["date"]):
        date_value = row["date"].date()
    else:
        date_value = date.today()

    plant_value = row["plant_id"]
    if pd.isna(plant_value):
        plant_value = plants[0]
    else:
        plant_value = str(plant_value)

    amount_value = row["amount_ml"]
    if pd.isna(amount_value):
        amount_value = 0.0
    else:
        amount_value = float(amount_value)

    notes_value = row["notes"]
    if pd.isna(notes_value):
        notes_value = ""
    else:
        notes_value = str(notes_value)

    rows.append({
        "Dzēst": False,
        "ID": int(row["id"]),
        "Augs": plant_value,
        "Datums": date_value,
        AMOUNT_LABEL: amount_value,
        "Piezīmes": notes_value,
    })

watering_table = pd.DataFrame(rows)

search_text = st.text_input(
    "Meklēt laistīšanas ierakstos",
    placeholder="Augs, datums vai piezīmes")

visible_watering = watering_table.copy()
search_text = search_text.strip().lower()
if search_text:
    search_values = (
        visible_watering["Augs"].astype(str) + " " +
        visible_watering["Datums"].astype(str) + " " +
        visible_watering["Piezīmes"].astype(str))
    visible_watering = visible_watering[
        search_values.str.lower().str.contains(search_text, na=False)]

if visible_watering.empty:
    st.info("Pēc meklēšanas nav atrasts neviens laistīšanas ieraksts.")
else:
    st.caption(
        f"Rādīti {len(visible_watering)} no "
        f"{len(watering_table)} laistīšanas ierakstiem.")

    edited_watering = st.data_editor(
        visible_watering,
        use_container_width=True,
        hide_index=True,
        height=360,
        disabled=["ID"],
        column_config={
            "Dzēst": st.column_config.CheckboxColumn("Dzēst"),
            "Augs": st.column_config.SelectboxColumn(
                "Augs", options=plants),
            "Datums": st.column_config.DateColumn(
                "Datums", format="YYYY-MM-DD"),
            AMOUNT_LABEL: st.column_config.NumberColumn(
                AMOUNT_LABEL, min_value=0.0, step=50.0,
                format="%.0f"),
            "Piezīmes": st.column_config.TextColumn("Piezīmes"),
        },
        key="watering_editor")

    if st.button("Saglabāt laistīšanas izmaiņas", type="primary"):
        conn = open_conn()
        delete_ids = []

        for _, row in edited_watering.iterrows():
            watering_id = int(row["ID"])

            if row["Dzēst"]:
                delete_ids.append(watering_id)
            else:
                plant_value = row["Augs"]
                if pd.isna(plant_value):
                    plant_value = plants[0]
                else:
                    plant_value = str(plant_value)

                date_value = pd.to_datetime(row["Datums"], errors="coerce")
                if pd.notna(date_value):
                    final_date = date_value.date().isoformat()
                else:
                    final_date = date.today().isoformat()

                amount_value = row[AMOUNT_LABEL]
                if pd.notna(amount_value):
                    final_amount = float(amount_value)
                else:
                    final_amount = 0.0

                notes_value = row["Piezīmes"]
                if pd.isna(notes_value):
                    notes_value = None
                else:
                    notes_value = str(notes_value).strip() or None

                conn.execute(
                    "UPDATE watering_events "
                    "SET plant_id=?, date=?, amount_ml=?, notes=? "
                    "WHERE id=?",
                    (plant_value, final_date, final_amount,
                     notes_value, watering_id))

        if delete_ids:
            placeholders = ",".join(["?"] * len(delete_ids))
            conn.execute(
                f"DELETE FROM watering_events WHERE id IN ({placeholders})",
                delete_ids)

        conn.commit()
        conn.close()
        st.success("Laistīšanas izmaiņas saglabātas.")
        st.rerun()
