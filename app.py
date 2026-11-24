# ==============================================================

st.header("🧾 Cell Fault History")

if st.session_state.cell_fault_history:

    cell_fault_df = pd.DataFrame(
        st.session_state.cell_fault_history
    )

    st.dataframe(
        cell_fault_df.tail(100),
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇ Download Cell Fault History CSV",
        data=cell_fault_df.to_csv(index=False),
        file_name="smart_bms_v4_4_cell_fault_history.csv",
        mime="text/csv"
    )

else:

    st.info("No cell fault events recorded.")

# ==============================================================
# 33. DOWNLOAD DATA
# ==============================================================

st.header("💾 Export Simulation Data")

if st.session_state.performance_history:

    export_df = pd.DataFrame(
        st.session_state.performance_history
    )

    st.download_button(
        "⬇ Download Battery Performance CSV",
        data=export_df.to_csv(index=False),
        file_name="smart_bms_v4_4_performance.csv",
        mime="text/csv"
    )

if st.session_state.thermal_history:

    thermal_export_df = pd.DataFrame(
        st.session_state.thermal_history
    )

    st.download_button(
        "⬇ Download Thermal History CSV",
        data=thermal_export_df.to_csv(index=False),
        file_name="smart_bms_v4_4_thermal_history.csv",
        mime="text/csv"
    )

st.download_button(
    "⬇ Download Cell Voltage CSV",
    data=cell_df.to_csv(index=False),
    file_name="smart_bms_v4_4_cell_voltages.csv",
    mime="text/csv"
)

# ==============================================================
# 34. SYSTEM INFORMATION
# ==============================================================

st.header("ℹ️ System Information")

system_info = {
    "Application": "Smart EV Battery Management System",
    "Version": "4.4 Virtual Simulation Edition",
    "New Module": "Cell Monitoring & Intelligent Balancing",
    "Battery Configuration": "13S4P Lithium-Ion",
    "Series Cell Groups": SERIES_CELLS,
    "Parallel Cells per Group": PARALLEL_CELLS,
    "Nominal Cell Voltage": f"{CELL_NOMINAL_VOLTAGE:.2f} V",
    "Nominal Pack Voltage": f"{PACK_NOMINAL_VOLTAGE:.2f} V",
    "Nominal Pack Capacity": f"{CAPACITY_AH:.2f} Ah",
    "Pack Internal Resistance": f"{INTERNAL_RESISTANCE:.3f} Ohm",
    "Simulation Mode": mode,
    "Cell Scenario": st.session_state.cell_scenario,
    "Cell Balancing": "Simulated",
    "Protection": "Warning / Critical / Hysteresis",
    "Hardware Connection": "Wokwi MQTT command bridge (publish on button click)",
    "Data Type": "Simulated"
}

st.json(system_info)

# ==============================================================
# 35. DISCLAIMER
# ==============================================================

st.divider()

st.caption(
    "Smart EV BMS V4.4 Virtual Simulation Edition | Academic Simulation Prototype. "
    "All battery, cell, protection, thermal, and balancing data "
    "are simulated. This application is not connected to a real "
    "battery pack or battery sensors and is not intended for real "
    "battery protection or safety control."
)

# ==============================================================
# END OF SMART EV BMS V4.4 VIRTUAL SIMULATION EDITION
# ==============================================================
