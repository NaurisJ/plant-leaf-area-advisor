# Plants - plant management (add, edit, delete)

from datetime import date

import pandas as pd
import streamlit as st

from helpers import load_measurements, open_conn
from measure_leaf_area import ensure_plant, list_plants, list_species

st.title("Augi")
st.caption(
    "Pārvaldiet sistēmā reģistrētos augus, to sugas un saistītos mērījumus.")

conn = open_conn()
plants = list_plants(conn)
species = list_species(conn)
df = load_measurements()

# Species list - "Latīņu nosaukums (parastais)"
species_labels = []
for s in species:
    if s["common_name"]:
        label = f"{s['latin_name']} ({s['common_name']})"
    else:
        label = s["latin_name"]
    species_labels.append(label)

# Existing plant table
if plants:
    st.subheader("Augu saraksts")
    rows = []
    for plant in plants:
        plant_id = plant["plant_id"]

        plant_measurements = df[df["plant_id"] == plant_id]
        measurement_count = len(plant_measurements)
        last_date = plant_measurements["date"].max()

        if pd.notna(last_date):
            last_date_text = last_date.strftime("%Y-%m-%d")
        else:
            last_date_text = "—"

        rows.append({
            "Nosaukums": plant["display_name"] or plant_id,
            "Suga": plant["species"] or "—",
            "Mērījumi": measurement_count,
            "Pēdējais": last_date_text,
        })
    plant_table = pd.DataFrame(rows)
    st.dataframe(plant_table, use_container_width=True, hide_index=True)

    csv_text = "sep=;\n" + plant_table.to_csv(index=False, sep=";")
    csv_data = csv_text.encode("utf-8-sig")

    st.download_button(
        "Lejupielādēt augu sarakstu",
        data=csv_data,
        file_name="augi.csv",
        mime="text/csv")
else:
    st.info("Nav reģistrētu augu.")

# Add new plant
st.subheader("Pievienot jaunu augu")
with st.form("add_plant", clear_on_submit=True):
    c1, c2 = st.columns(2)
    new_id = c1.text_input("Identifikators", placeholder="piem. Plant9")
    new_name = c2.text_input("Nosaukums (neobligāti)")

    if species_labels:
        sp_choice = st.selectbox("Suga", species_labels)
    else:
        sp_choice = None
        st.warning("Datubāzē nav sugu.")

    if st.form_submit_button("Pievienot", type="primary"):
        pid = new_id.strip()
        if not pid:
            st.error("Identifikators ir obligāts.")
        elif sp_choice is None:
            st.error("Nav pieejamas sugas.")
        else:
            sp_idx = species_labels.index(sp_choice)
            ensure_plant(
                conn, pid,
                display_name=new_name.strip() or None,
                species=species[sp_idx]["latin_name"])
            st.success(f"Pievienots: {pid}")
            st.rerun()

# edit or delete
if plants:
    st.subheader("Rediģēt vai dzēst")
    # Get labels ready for plant choice
    plant_labels = []
    for p in plants:
        plant_labels.append(p["display_name"] or p["plant_id"])

    def show_plant(i):
        return plant_labels[i]

    chosen_idx = st.selectbox(
        "Izvēlieties augu", range(len(plants)), format_func=show_plant)
    current = plants[chosen_idx]

    with st.form("edit_plant"):
        new_display = st.text_input(
            "Nosaukums", value=current["display_name"] or "")

        if species_labels:
            # Find existing species index from list
            cur_sp = current["species"] or ""
            sp_idx = 0
            for index, item in enumerate(species):
                if item["latin_name"] == cur_sp:
                    sp_idx = index
                    break
            edit_sp = st.selectbox("Suga", species_labels, index=sp_idx)
        else:
            edit_sp = None

        new_notes = st.text_area("Piezīmes", value=current["notes"] or "")

        c1, c2 = st.columns(2)
        save = c1.form_submit_button("Saglabāt", type="primary")
        delete = c2.form_submit_button("Dzēst augu un tā datus")

    if save:
        species_final = None
        if edit_sp and species_labels:
            sp_idx = species_labels.index(edit_sp)
            species_final = species[sp_idx]["latin_name"]
        conn.execute(
            "UPDATE plants SET display_name=?, species=?, notes=? "
            "WHERE plant_id=?",
            (new_display or None, species_final,
             new_notes or None, current["plant_id"]))
        conn.commit()
        st.success("Saglabāts.")
        st.rerun()

    if delete:
        # Delete all associating data
        conn.execute("DELETE FROM measurements WHERE plant_id=?",
                     (current["plant_id"],))
        conn.execute("DELETE FROM watering_events WHERE plant_id=?",
                     (current["plant_id"],))
        conn.execute("DELETE FROM plants WHERE plant_id=?",
                     (current["plant_id"],))
        conn.commit()
        st.warning(f"Dzēsts: {current['plant_id']}")
        st.rerun()

    st.subheader("Mērījumu pārvaldība")
    st.caption(
        "Šeit redzami visi saglabātie mērījumi. Lai atrastu konkrētu augu "
        "vai ierakstu, izmantojiet meklēšanas lauku.")

    plant_measurements = df.copy()
    plant_measurements = plant_measurements.sort_values(
        "date", ascending=False)

    if plant_measurements.empty:
        st.info("Nav saglabātu mērījumu.")
    else:
        st.caption(
            "Labojiet mērījumus tieši tabulā. Atzīmējiet 'Dzēst', ja rinda "
            "jāizņem. Vērtība 0 laukiem 'Lapotne cm²' un 'Ref. cm' nozīmē, "
            "ka kalibrācija nav norādīta.")

        rows = []
        for _, row in plant_measurements.iterrows():
            if pd.notna(row["date"]):
                date_value = row["date"].date()
            else:
                date_value = date.today()

            view_value = row["view"]
            if pd.isna(view_value):
                view_value = "unknown"
            else:
                view_value = str(view_value)

            filename_value = row["filename"]
            if pd.isna(filename_value):
                filename_value = ""
            else:
                filename_value = str(filename_value)

            leaf_pct = row["leaf_area_pct"]
            if pd.isna(leaf_pct):
                leaf_pct = 0.0
            else:
                leaf_pct = round(float(leaf_pct), 2)

            area_value = row["canopy_area_cm2"]
            if pd.isna(area_value):
                area_value = 0.0
            else:
                area_value = round(float(area_value), 1)

            calibration_value = row["calibration_cm"]
            if pd.isna(calibration_value):
                calibration_value = 0.0
            else:
                calibration_value = round(float(calibration_value), 1)

            notes_value = row["notes"]
            if pd.isna(notes_value):
                notes_value = ""
            else:
                notes_value = str(notes_value)

            rows.append({
                "Dzēst": False,
                "ID": int(row["id"]),
                "Augs": row["plant_id"],
                "Datums": date_value,
                "Skats": view_value,
                "Fails": filename_value,
                "Lapotne %": leaf_pct,
                "Lapotne cm²": area_value,
                "Ref. cm": calibration_value,
                "Piezīmes": notes_value,
            })

        measurement_table = pd.DataFrame(rows)

        search_text = st.text_input(
            "Meklēt mērījumos",
            placeholder="Datums, fails, skats vai piezīmes")

        visible_table = measurement_table.copy()
        search_text = search_text.strip().lower()
        if search_text:
            search_values = (
                visible_table["Augs"].astype(str) + " " +
                visible_table["Datums"].astype(str) + " " +
                visible_table["Skats"].astype(str) + " " +
                visible_table["Fails"].astype(str) + " " +
                visible_table["Piezīmes"].astype(str))
            visible_table = visible_table[
                search_values.str.lower().str.contains(search_text, na=False)]

        if visible_table.empty:
            st.info("Pēc meklēšanas nav atrasts neviens mērījums.")
        else:
            st.caption(
                f"Rādīti {len(visible_table)} no "
                f"{len(measurement_table)} mērījumiem.")
            edited_table = st.data_editor(
                visible_table,
                use_container_width=True,
                hide_index=True,
                height=420,
                disabled=["ID", "Augs", "Fails", "Lapotne %"],
                column_config={
                    "Dzēst": st.column_config.CheckboxColumn("Dzēst"),
                    "Datums": st.column_config.DateColumn(
                        "Datums", format="YYYY-MM-DD"),
                    "Skats": st.column_config.SelectboxColumn(
                        "Skats", options=["top", "front", "side", "unknown"]),
                    "Lapotne cm²": st.column_config.NumberColumn(
                        "Lapotne cm²", min_value=0.0, step=1.0,
                        format="%.1f"),
                    "Ref. cm": st.column_config.NumberColumn(
                        "Ref. cm", min_value=0.0, step=0.1,
                        format="%.1f"),
                    "Piezīmes": st.column_config.TextColumn("Piezīmes"),
                },
                key="measurement_editor_all")

            if st.button("Saglabāt mērījumu izmaiņas", type="primary"):
                delete_ids = []

                for _, row in edited_table.iterrows():
                    measurement_id = int(row["ID"])

                    if row["Dzēst"]:
                        delete_ids.append(measurement_id)
                    else:
                        date_value = pd.to_datetime(
                            row["Datums"], errors="coerce")
                        if pd.notna(date_value):
                            final_date = date_value.date().isoformat()
                        else:
                            final_date = None

                        view_value = row["Skats"]
                        if pd.isna(view_value):
                            view_value = "unknown"
                        else:
                            view_value = str(view_value).strip() or "unknown"

                        area_value = row["Lapotne cm²"]
                        if pd.notna(area_value) and float(area_value) > 0:
                            final_area = float(area_value)
                        else:
                            final_area = None

                        calibration_value = row["Ref. cm"]
                        if (pd.notna(calibration_value) and
                                float(calibration_value) > 0):
                            final_calibration = float(calibration_value)
                        else:
                            final_calibration = None

                        notes_value = row["Piezīmes"]
                        if pd.isna(notes_value):
                            notes_value = None
                        else:
                            notes_value = str(notes_value).strip() or None

                        if (final_area is not None or
                                final_calibration is not None):
                            calibration_object = "Manuāli labota kalibrācija"
                        else:
                            calibration_object = None

                        conn.execute(
                            "UPDATE measurements "
                            "SET date=?, view=?, canopy_area_cm2=?, "
                            "calibration_object=?, calibration_cm=?, notes=? "
                            "WHERE id=?",
                            (final_date, view_value, final_area,
                             calibration_object, final_calibration,
                             notes_value, measurement_id))

                if delete_ids:
                    placeholders = ",".join(["?"] * len(delete_ids))
                    conn.execute(
                        f"DELETE FROM measurements WHERE id IN ({placeholders})",
                        delete_ids)

                conn.commit()
                st.success("Mērījumu izmaiņas saglabātas.")
                st.rerun()

conn.close()
