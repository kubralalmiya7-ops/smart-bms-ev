import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

try:
    from streamlit_autorefresh import st_autorefresh
    AUTO_REFRESH_AVAILABLE = True
except ImportError:
    AUTO_REFRESH_AVAILABLE = False

# =========================================================
# SMART EV BATTERY MANAGEMENT SYSTEM - VERSION 4.5
# Stability, Cell Monitoring, Balancing and Fault Recovery
# =========================================================

st.set_page_config(
    page_title="Smart EV BMS | V4.5",
    page_icon="🔋",
    layout="wide"
)

# ----------------------- CONSTANTS --------------------------
SERIES_CELLS = 13
PARALLEL_CELLS = 4

CELL_MIN = 3.0
CELL_MAX = 4.2

PACK_MIN = 39.0
PACK_MAX = 54.6
PACK_NOMINAL = 46.8

CAPACITY_AH = 10.0
INTERNAL_RESISTANCE = 0.08

AMBIENT_TEMP = 25.0
THERMAL_CAPACITY = 500.0
COOLING_COEFFICIENT = 1.5

TEMP_WARNING = 45.0
TEMP_WARNING_CLEAR = 42.0
TEMP_CRITICAL = 55.0
TEMP_CRITICAL_CLEAR = 48.0

CURRENT_WARNING = 20.0
CURRENT_CRITICAL = 25.0

VOLTAGE_LOW_WARNING = 42.0
VOLTAGE_LOW_CRITICAL = 39.0
VOLTAGE_HIGH_WARNING = 53.0
VOLTAGE_HIGH_CRITICAL = 54.6

CELL_IMBALANCE_WARNING = 0.050
CELL_IMBALANCE_CRITICAL = 0.100
WEAK_CELL_WARNING = 3.10
WEAK_CELL_CRITICAL = 3.00

BALANCING_RATE = 0.0015
SIMULATION_DT = 5.0

# ----------------------- SESSION STATE ----------------------

defaults = {
    "soc": 80.0,
    "temperature": 25.0,
    "pack_voltage": 46.8,
    "current": 0.0,
    "effective_current": 0.0,
    "mode": "Manual Fault Testing",
    "protection": "NORMAL",
    "faults": [],
    "event_log": [],
    "cell_log": [],
    "cell_voltages": np.full(SERIES_CELLS, 3.6),
    "balance_adjustments": np.zeros(SERIES_CELLS),
    "cell_condition": "Normal cells",
    "balancing_active": False,
    "simulation_count": 0,
    "time_history": [],
    "voltage_history": [],
    "current_history": [],
    "temperature_history": [],
    "soc_history": [],
    "power_history": [],
    "energy_kwh": 0.0,
    "peak_temperature": 25.0,
    "last_weak_cells": [],
    "last_protection": "NORMAL",
    "last_balance_log": False,
    "initialized": True
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ----------------------- FUNCTIONS -------------------------

def log_event(message, category="System"):
    """Avoid consecutive duplicate events."""
    now = datetime.now().strftime("%H:%M:%:%S")
    # Correct timestamp formatting
    now = datetime.now().strftime("%H:%M:%S")

    entry = {
        "Time": now,
        "Category": category,
        "Event": message
    }

    if (
        not st.session_state.event_log
        or st.session_state.event_log[-1]["Event"] != message
    ):
        st.session_state.event_log.insert(0, entry)

    st.session_state.event_log = st.session_state.event_log[:100]


def reset_system():
    st.session_state.soc = 80.0
    st.session_state.temperature = 25.0
    st.session_state.pack_voltage = 46.8
    st.session_state.current = 0.0
    st.session_state.effective_current = 0.0
    st.session_state.protection = "NORMAL"
    st.session_state.faults = []
    st.session_state.event_log = []
    st.session_state.cell_log = []
    st.session_state.cell_voltages = np.full(SERIES_CELLS, 3.6)
    st.session_state.balance_adjustments = np.zeros(SERIES_CELLS)
    st.session_state.balancing_active = False
    st.session_state.simulation_count = 0
    st.session_state.time_history = []
    st.session_state.voltage_history = []
    st.session_state.current_history = []
    st.session_state.temperature_history = []
    st.session_state.soc_history = []
    st.session_state.power_history = []
    st.session_state.energy_kwh = 0.0
    st.session_state.peak_temperature = 25.0
    st.session_state.last_weak_cells = []
    st.session_state.last_protection = "NORMAL"
    st.session_state.last_balance_log = False
    log_event("System reset to default parameters")


def generate_cells(pack_voltage, condition):
    """
    Rebuild cell voltages from a stable base each time.
    Fault offsets are not accumulated between refreshes.
    """

    avg = pack_voltage / SERIES_CELLS

    # Fixed, repeatable healthy-cell variation
    base_offsets = np.array([
        0.003, -0.004, 0.005, -0.002, 0.001,
        -0.005, 0.004, -0.001, 0.002, -0.003,
        0.005, -0.002, -0.003
    ])

    offsets = base_offsets.copy()

    if condition == "Cell imbalance":
        offsets[5] += 0.075
        offsets[10] -= 0.055

    elif condition == "Weak cell":
        # Intentionally inject a weak cell below warning level
        target_voltage = 2.95
        offsets[3] = target_voltage - avg

    elif condition == "Multiple cell imbalance":
        offsets[1] += 0.090
        offsets[4] -= 0.080
        offsets[8] += 0.065
        offsets[11] -= 0.070

    elif condition == "High cell":
        offsets[7] += 0.180

    # Add separately stored balancing adjustments
    offsets += st.session_state.balance_adjustments

    # Keep healthy scenarios close to the pack voltage sum.
    voltages = avg + offsets

    # Weak cell scenario is intentionally a fault simulation.
    if condition == "Weak cell":
        voltages[3] = target_voltage
        other_indices = [i for i in range(SERIES_CELLS) if i != 3]
        required_sum = pack_voltage - target_voltage
        other_avg = required_sum / len(other_indices)
        for i in other_indices:
            voltages[i] = other_avg + base_offsets[i] * 0.3

    voltages = np.clip(voltages, CELL_MIN, CELL_MAX)

    st.session_state.cell_voltages = voltages
    st.session_state.pack_voltage = pack_voltage

    return voltages


def update_balancing(cells, enabled=True):
    """Simulate passive balancing by reducing high-cell values over time."""

    if not enabled:
        st.session_state.balancing_active = False
        return

    delta = float(np.max(cells) - np.min(cells))
    active = delta >= CELL_IMBALANCE_WARNING

    st.session_state.balancing_active = active

    if active:
        mean_voltage = np.mean(cells)

        for i in range(SERIES_CELLS):
            if cells[i] > mean_voltage + 0.020:
                st.session_state.balance_adjustments[i] -= BALANCING_RATE

        # Limit balancing adjustment to prevent runaway
        st.session_state.balance_adjustments = np.clip(
            st.session_state.balance_adjustments, -0.15, 0.0
        )


def evaluate_protection(voltage, requested_current, temperature, cells):
    """One protection evaluation per simulation step."""

    faults = []

    # Pack voltage protection
    if voltage <= VOLTAGE_LOW_CRITICAL:
        faults.append("Critical low pack voltage")
    elif voltage < VOLTAGE_LOW_WARNING:
        faults.append("Low pack voltage warning")

    if voltage >= VOLTAGE_HIGH_CRITICAL:
        faults.append("Critical high pack voltage")
    elif voltage > VOLTAGE_HIGH_WARNING:
        faults.append("High pack voltage warning")

    # Current protection
    if abs(requested_current) >= CURRENT_CRITICAL:
        faults.append("Critical overcurrent")
    elif abs(requested_current) >= CURRENT_WARNING:
        faults.append("Current warning")

    # Temperature protection
    if temperature >= TEMP_CRITICAL:
        faults.append("Critical temperature")
    elif temperature >= TEMP_WARNING:
        faults.append("High temperature warning")

    # Cell monitoring
    imbalance = float(np.max(cells) - np.min(cells)

    if imbalance >= CELL_IMBALANCE_CRITICAL:
        faults.append("Critical cell imbalance")
    elif imbalance >= CELL_IMBALANCE_WARNING:
        faults.append("Cell imbalance warning")

    weak_cells = [
        i + 1 for i, v in enumerate(cells)
        if v < WEAK_CELL_WARNING
    ]

    critical_weak = [
        i + 1 for i, v in enumerate(cells)
        if v <= WEAK_CELL_CRITICAL
    ]

    if weak_cells:
        faults.append("Weak cell detected")

    # Select protection state
    critical = (
        voltage <= VOLTAGE_LOW_CRITICAL
        or voltage >= VOLTAGE_HIGH_CRITICAL
        or abs(requested_current) >= CURRENT_CRITICAL
        or temperature >= TEMP_CRITICAL
        or bool(critical_weak)
        or imbalance >= CELL_IMBALANCE_CRITICAL
    )

    warning = bool(faults)

    if critical:
        state = "CRITICAL"
    elif warning:
        state = "WARNING"
    else:
        state = "NORMAL"

    # Transition-based event logging
    if state != st.session_state.last_protection:
        log_event(
            f"Protection state changed: {st.session_state.last_protection} → {state}",
            "Protection"
        )
        st.session_state.last_protection = state

    current_weak = weak_cells

    if current_weak != st.session_state.last_weak_cells:
        if current_weak:
            log_event(
                "Weak cell(s) detected: " +
                ", ".join(f"Cell {c}" for c in current_weak),
                "Cell Monitoring"
            )
        elif st.session_state.last_weak_cells:
            log_event("Weak-cell warning cleared", "Cell Monitoring")

        st.session_state.last_weak_cells = current_weak.copy()

    return state, faults, weak_cells, imbalance


def apply_protection(requested_current, state):
    if state == "CRITICAL":
        return 0.0
    elif state == "WARNING":
        return requested_current * 0.5
    return requested_current


def simulation_step(voltage, requested_current, temperature, condition):
    """Advance simulation once."""

    cells = generate_cells(voltage, condition)

    state, faults, weak_cells, imbalance = evaluate_protection(
        voltage, requested_current, temperature, cells
    )

    effective_current = apply_protection(requested_current, state)

    # Update SoC by Coulomb counting
    st.session_state.soc -= (
        effective_current * SIMULATION_DT / 3600 / CAPACITY_AH * 100
    )
    st.session_state.soc = float(np.clip(st.session_state.soc, 0, 100))

    # Simple electrical and thermal estimates
    power = voltage * effective_current

    heat_generated = effective_current ** 2 * INTERNAL_RESISTANCE
    cooling = COOLING_COEFFICIENT * (temperature - AMBIENT_TEMP)

    temperature_change = (
        heat_generated - cooling
    ) * SIMULATION_DT / THERMAL_CAPACITY

    if condition == "Normal cells":
        temperature = temperature + temperature_change

    temperature = float(np.clip(temperature, 15, 75))

    st.session_state.temperature = temperature
    st.session_state.effective_current = effective_current
    st.session_state.protection = state
    st.session_state.faults = faults
    st.session_state.peak_temperature = max(
        st.session_state.peak_temperature, temperature
    )

    # Balancing update uses this step's cell readings.
    update_balancing(cells)

    if st.session_state.balancing_active != st.session_state.last_balance_log:
        log_event(
            "Cell balancing activated" if st.session_state.balancing_active
            else "Cell balancing stopped",
            "Balancing"
        )
        st.session_state.last_balance_log = st.session_state.balancing_active

    st.session_state.simulation_count += 1

    st.session_state.time_history.append(st.session_state.simulation_count)
    st.session_state.voltage_history.append(voltage)
    st.session_state.current_history.append(effective_current)
    st.session_state.temperature_history.append(temperature)
    st.session_state.soc_history.append(st.session_state.soc)
    st.session_state.power_history.append(power)

    # Energy estimate: kWh
    st.session_state.energy_kwh += (
        power * SIMULATION_DT / 3600 / 1000
    )

    # Keep chart history bounded
    for key in [
        "time_history", "voltage_history", "current_history",
        "temperature_history", "soc_history", "power_history"
    ]:
        st.session_state[key] = st.session_state[key][-100:]

    st.session_state.cell_log.append({
        "Step": st.session_state.simulation_count,
        "Cell ΔV (V)": round(imbalance, 4),
        "Weak Cells": ", ".join(map(str, weak_cells)) if weak_cells else "None",
        "Balancing": "Active" if st.session_state.balancing_active else "Inactive"
    })

    st.session_state.cell_log = st.session_state.cell_log[-100:]

    return voltage, effective_current, temperature, cells, state, faults


# ----------------------- HEADER ----------------------------

st.title("🔋 Smart EV Battery Management System")
st.caption("Version 4.5 | Stability, Cell Monitoring & Intelligent Protection")

st.info(
    "Software simulation prototype. All displayed values are simulated, "
    "not obtained from physical battery sensors."
)

# ----------------------- SIDEBAR --------------------------

st.sidebar.header("⚙️ Simulation Controls")

mode = st.sidebar.radio(
    "Operating Mode",
    ["Manual Fault Testing", "Automatic Simulation"]
)

condition = st.sidebar.selectbox(
    "Cell Condition",
    [
        "Normal cells",
        "Cell imbalance",
        "Weak cell",
        "Multiple cell imbalance",
        "High cell"
    ]
)

st.sidebar.caption("13-series / 4-parallel lithium-ion battery model")

if mode == "Manual Fault Testing":
    pack_voltage = st.sidebar.slider(
        "Pack Voltage (V)", 39.0, 54.6, 46.8, 0.1
    )
    requested_current = st.sidebar.slider(
        "Requested Current (A)", -30.0, 30.0, 5.0, 0.5
    )
    temperature = st.sidebar.slider(
        "Battery Temperature (°C)", 15.0, 70.0, 25.0, 0.5
    )

    st.sidebar.caption("Negative current = charging. Positive = discharging.")

    advance = st.sidebar.button("▶ Advance Simulation Step", use_container_width=True)

else:
    driving_scenario = st.sidebar.selectbox(
        "Driving / Charging Scenario",
        ["Idle", "Driving - Low Load", "Driving - High Load", "Charging"]
    )

    auto_currents = {
        "Idle": 0.0,
        "Driving - Low Load": 5.0,
        "Driving - High Load": 15.0,
        "Charging": -5.0
    }

    requested_current = auto_currents[driving_scenario]
    pack_voltage = st.session_state.pack_voltage
    temperature = st.session_state.temperature
    advance = True

    if AUTO_REFRESH_AVAILABLE:
        st_autorefresh(interval=2000, key="v45refresh")

st.sidebar.divider()

if st.sidebar.button("🔄 Reset System", use_container_width=True):
    reset_system()
    st.rerun()

st.sidebar.markdown("### Protection Thresholds")
st.sidebar.write(f"Temperature Warning: **{TEMP_WARNING}°C**")
st.sidebar.write(f"Temperature Critical: **{TEMP_CRITICAL}°C**")
st.sidebar.write(f"Current Warning: **{CURRENT_WARNING} A**")
st.sidebar.write(f"Current Critical: **{CURRENT_CRITICAL} A**")
st.sidebar.write(f"Cell Imbalance Warning: **{CELL_IMBALANCE_WARNING:.3f} V**")

# ----------------------- SIMULATION ------------------------

if mode == "Manual Fault Testing":
    if advance:
        (
            pack_voltage,
            effective_current,
            temperature,
            cells,
            protection,
            faults
        ) = simulation_step(
            pack_voltage,
            requested_current,
            temperature,
            condition
        )
else:
    (
        pack_voltage,
        effective_current,
        temperature,
        cells,
        protection,
        faults
    ) = simulation_step(
        pack_voltage,
        requested_current,
        temperature,
        condition
    )

cells = st.session_state.cell_voltages

# Always display current session values
protection = st.session_state.protection
effective_current = st.session_state.effective_current
temperature = st.session_state.temperature
pack_voltage = st.session_state.pack_voltage

# ----------------------- TOP METRICS ----------------------

st.subheader("Battery Overview")

m1, m2, m3, m4 = st.columns(4)

m1.metric("State of Charge", f"{st.session_state.soc:.1f}%")
m2.metric("Pack Voltage", f"{pack_voltage:.2f} V")
m3.metric("Battery Current", f"{effective_current:.2f} A")
m4.metric("Temperature", f"{temperature:.1f} °C")

# ----------------------- PROTECTION STATUS ---------------

if protection == "CRITICAL":
    st.error("🚨 CRITICAL — Safety shutdown active")
elif protection == "WARNING":
    st.warning("⚠️ WARNING — Battery protection active")
else:
    st.success("✅ NORMAL — No active critical fault")

st.write("**Requested Current:**", f"{requested_current:.2f} A")
st.write("**Effective Current after Protection:**", f"{effective_current:.2f} A")

if faults:
    st.write("**Active Faults:**")
    for fault in faults:
        st.warning(fault)
else:
    st.write("No active faults detected.")

# ----------------------- POWER / ENERGY --------------------

power = pack_voltage * effective_current

c1, c2, c3, c4 = st.columns(4)

c1.metric("Power", f"{power:.2f} W")
c2.metric("Energy (Simulated)", f"{st.session_state.energy_kwh:.4f} kWh")
c3.metric("Peak Temperature", f"{st.session_state.peak_temperature:.1f} °C")
c4.metric(
    "Pack Condition",
    "Shutdown" if protection == "CRITICAL"
    else "Warning" if protection == "WARNING"
    else "Normal"
)

# ----------------------- CELL MONITORING ------------------

st.divider()
st.subheader("🔬 Cell-Level Monitoring")

cell_minimum = float(np.min(cells))
cell_maximum = float(np.max(cells))
cell_delta = cell_maximum - cell_minimum
mean_cell = float(np.mean(cells))

a, b, c, d = st.columns(4)

a.metric("Minimum Cell Voltage", f"{cell_minimum:.3f} V")
b.metric("Maximum Cell Voltage", f"{cell_maximum:.3f} V")
c.metric("Cell Voltage Difference (ΔV)", f"{cell_delta:.3f} V")
d.metric("Average Cell Voltage", f"{mean_cell:.3f} V")

if cell_delta >= CELL_IMBALANCE_CRITICAL:
    st.error("Critical cell imbalance detected")
elif cell_delta >= CELL_IMBALANCE_WARNING:
    st.warning("Cell imbalance detected")
else:
    st.success("Cell voltage balance within simulated normal range")

if st.session_state.balancing_active:
    st.info("⚖️ Passive cell balancing simulation: ACTIVE")
else:
    st.write("⚖️ Passive cell balancing simulation: Inactive")

# ----------------------- CELL GRID -------------------------

st.markdown("### Individual Cell Readings")

cell_cols = st.columns(4)

for i, voltage in enumerate(cells):
    with cell_cols[i % 4]:
        if voltage <= CELL_MIN:
            st.error(f"Cell {i+1}: {voltage:.3f} V — CRITICAL")
        elif voltage < WEAK_CELL_WARNING:
            st.warning(f"Cell {i+1}: {voltage:.3f} V — WEAK")
        elif voltage > 4.15:
            st.warning(f"Cell {i+1}: {voltage:.3f} V — HIGH")
        else:
            st.success(f"Cell {i+1}: {voltage:.3f} V")

# ----------------------- CELL CHART -----------------------

cell_df = pd.DataFrame({
    "Cell": [f"Cell {i+1}" for i in range(SERIES_CELLS)],
    "Voltage": cells
})

fig_cells = go.Figure()

fig_cells.add_trace(go.Bar(
    x=cell_df["Cell"],
    y=cell_df["Voltage"],
    name="Cell Voltage"
))

fig_cells.add_hline(
    y=WEAK_CELL_WARNING,
    line_dash="dash",
    annotation_text="Weak Cell Threshold"
)

fig_cells.add_hline(
    y=4.15,
    line_dash="dash",
    annotation_text="High Cell Threshold"
)

fig_cells.update_layout(
    title="13-Series Cell Voltage Distribution",
    yaxis_title="Voltage (V)",
    yaxis_range=[2.8, 4.3],
    height=400
)

st.plotly_chart(fig_cells, use_container_width=True)

# ----------------------- PERFORMANCE CHARTS -------------

st.divider()
st.subheader("📊 Battery Parameter Analysis")

if st.session_state.time_history:

    chart_df = pd.DataFrame({
        "Step": st.session_state.time_history,
        "Voltage": st.session_state.voltage_history,
        "Current": st.session_state.current_history,
        "Temperature": st.session_state.temperature_history,
        "SoC": st.session_state.soc_history,
        "Power": st.session_state.power_history
    })

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Voltage", "Current", "Temperature", "Power", "SoC"
    ])

    with tab1:
        st.line_chart(chart_df.set_index("Step")["Voltage"])

    with tab2:
        st.line_chart(chart_df.set_index("Step")["Current"])

    with tab3:
        st.line_chart(chart_df.set_index("Step")["Temperature"])

    with tab4:
        st.line_chart(chart_df.set_index("Step")["Power"])

    with tab5:
        st.line_chart(chart_df.set_index("Step")["SoC"])

else:
    st.info("Advance the simulation to generate parameter history.")

# ----------------------- FAULT / EVENT LOG -------------

st.divider()
st.subheader("📋 Protection & Event Logs")

if st.session_state.event_log:
    st.dataframe(
        pd.DataFrame(st.session_state.event_log),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No events logged yet.")

st.subheader("Cell Monitoring History")

if st.session_state.cell_log:
    st.dataframe(
        pd.DataFrame(st.session_state.cell_log),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Cell monitoring records will appear after simulation steps.")

# ----------------------- DOWNLOAD REPORTS ----------------

st.divider()
st.subheader("📥 Export Simulation Data")

if st.session_state.time_history:
    history_df = pd.DataFrame({
        "Step": st.session_state.time_history,
        "Voltage_V": st.session_state.voltage_history,
        "Current_A": st.session_state.current_history,
        "Temperature_C": st.session_state.temperature_history,
        "SoC_Percent": st.session_state.soc_history,
        "Power_W": st.session_state.power_history
    })

    st.download_button(
        "Download Parameter History CSV",
        history_df.to_csv(index=False),
        "bms_parameter_history.csv",
        "text/csv"
    )

if st.session_state.cell_log:
    cell_history_df = pd.DataFrame(st.session_state.cell_log)

    st.download_button(
        "Download Cell Monitoring CSV",
        cell_history_df.to_csv(index=False),
        "bms_cell_history.csv",
        "text/csv"
    )

if st.session_state.event_log:
    event_df = pd.DataFrame(st.session_state.event_log)

    st.download_button(
        "Download Fault Event Log CSV",
        event_df.to_csv(index=False),
        "bms_fault_log.csv",
        "text/csv"
    )

# ----------------------- SYSTEM INFORMATION -------------

st.divider()
with st.expander("ℹ️ System Information"):
    st.write("**Project:** Smart Battery Management in Electric Vehicles")
    st.write("**Dashboard Version:** 4.5")
    st.write("**Battery Model:** Lithium-ion")
    st.write("**Pack Configuration:** 13S4P")
    st.write("**Nominal Voltage:** 46.8 V")
    st.write("**Maximum Voltage:** 54.6 V")
    st.write("**Minimum Voltage:** 39.0 V")
    st.write("**Nominal Capacity:** 10 Ah")
    st.write("**Cells Monitored in Series:** 13")
    st.write("**Parallel Cells per Group:** 4")
    st.write("**Monitoring:** Voltage, current, temperature, SoC and cell imbalance")
    st.write("**Protection:** Warning, current limiting, critical shutdown")
    st.write("**Balancing:** Simulated passive balancing")
    st.write("**SoH:** Not calculated (requires battery capacity test data)")

st.caption(
    "V4.5 | Software-only prototype. Cell balancing, protection and battery "
    "parameters are simulated and are not connected to physical sensors."
)
