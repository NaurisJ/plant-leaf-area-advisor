# Plants - plant management (add, edit, delete)

import pandas as pd
import streamlit as st

from helpers import load_measurements, open_conn
from measure_leaf_area import ensure_plant, list_plants, list_species

st.title("Augi")

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
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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

conn.close()
