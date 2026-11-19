# ==============================================================
# SMART EV BATTERY MANAGEMENT SYSTEM
# Version 4.4 Virtual Simulation Edition
# Cell-Level Monitoring & Intelligent Balancing
# Reconstructed integrated simulation application
# ==============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ==============================================================
# 1. PAGE CONFIGURATION
# ==============================================================

st.set_page_config(
    page_title="Smart EV BMS V4.4 Virtual Simulation Edition",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================
# 2. CUSTOM DESIGN
# ==============================================================

st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    [data-testid="stMetric"] {
        background-color: #171d27;
        padding: 15px;
        border: 1px solid #263245;
        border-radius: 12px;
    }
    div[data-testid="stMetricLabel"] {
        color: #aab8c9;
    }
    div[data-testid="stMetricValue"] {
        color: #f3f6fa;
    }
    .status-normal {
        background-color: #123a2a;
        color: #7dffb2;
        padding: 12px;
        border-radius: 10px;
        font-weight: bold;
    }
    .status-warning {
        background-color: #493517;
        color: #ffd166;
        padding: 12px;
        border-radius: 10px;
        font-weight: bold;
    }
    .status-critical {
        background-color: #4a2025;
        color: #ff7777;
        padding: 12px;
        border-radius: 10px;
        font-weight: bold;
    }
    .small-note {
        color: #9ca8b8;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================
# 3. BATTERY CONFIGURATION
# ==============================================================

SERIES_CELLS = 13
PARALLEL_CELLS = 4

CELL_NOMINAL_VOLTAGE = 3.6
CELL_MIN_VOLTAGE = 3.0
CELL_MAX_VOLTAGE = 4.2

PACK_NOMINAL_VOLTAGE = SERIES_CELLS * CELL_NOMINAL_VOLTAGE
PACK_MIN_VOLTAGE = SERIES_CELLS * CELL_MIN_VOLTAGE
PACK_MAX_VOLTAGE = SERIES_CELLS * CELL_MAX_VOLTAGE

CAPACITY_AH = 10.0
INTERNAL_RESISTANCE = 0.08

AMBIENT_TEMP = 25.0
THERMAL_CAPACITY = 500.0
COOLING_COEFFICIENT = 1.5

WARNING_TEMP_ON = 45.0
WARNING_TEMP_OFF = 42.0
CRITICAL_TEMP_ON = 55.0
CRITICAL_TEMP_OFF = 48.0

WARNING_VOLTAGE_LOW_ON = 42.0
WARNING_VOLTAGE_LOW_OFF = 43.0
WARNING_VOLTAGE_HIGH_ON = 53.0
WARNING_VOLTAGE_HIGH_OFF = 52.0

CRITICAL_VOLTAGE_LOW_ON = 39.0
CRITICAL_VOLTAGE_LOW_OFF = 40.5
CRITICAL_VOLTAGE_HIGH_ON = 54.6
CRITICAL_VOLTAGE_HIGH_OFF = 53.5

WARNING_CURRENT_ON = 20.0
WARNING_CURRENT_OFF = 18.0
CRITICAL_CURRENT_ON = 25.0
CRITICAL_CURRENT_OFF = 22.0

# Cell imbalance thresholds
CELL_IMBALANCE_WARNING = 0.050
CELL_IMBALANCE_CRITICAL = 0.100

# Weak cell detection
WEAK_CELL_WARNING_VOLTAGE = 3.10
WEAK_CELL_CRITICAL_VOLTAGE = 3.00

# Cell balancing simulation
BALANCING_START_DIFFERENCE = 0.020
BALANCING_RATE = 0.0015

# ==============================================================
# 4. SESSION STATE INITIALIZATION
# ==============================================================

def initialize_state():

    defaults = {
        "soc": 80.0,
        "temperature": 25.0,
        "pack_voltage": 46.8,
        "requested_current": 0.0,
        "effective_current": 0.0,

        "peak_temperature": 25.0,
        "heating_rate": 0.0,
        "cooling_power": 0.0,

        "energy_discharged": 0.0,
        "energy_charged": 0.0,
        "consumed_capacity": 0.0,

        "simulation_time": 0,
        "protection": {
            "temp_warning": False,
            "temp_critical": False,
            "voltage_low_warning": False,
            "voltage_high_warning": False,
            "voltage_low_critical": False,
            "voltage_high_critical": False,
            "current_warning": False,
            "current_critical": False,
        },

        "cell_offsets": np.zeros(SERIES_CELLS),
        "balance_adjustments": np.zeros(SERIES_CELLS),
        "logged_weak_cells": [],
        "cell_voltages": np.ones(SERIES_CELLS) * 3.6,
        "cell_balancing_active": False,
        "balancing_count": 0,
        "balancing_history": [],
        "cell_fault_history": [],

        "fault_log": [],
        "performance_history": [],
        "thermal_history": [],
        "previous_temperature": 25.0,

        "last_fault_state": "NORMAL",
        "last_cell_state": "NORMAL",

        "manual_voltage": 46.8,
        "manual_current": 15.0,
        "manual_temperature": 25.0,

        "auto_scenario": "Driving - Low Load",
        "cell_scenario": "Normal cells",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Generate initial slight cell variation
    if "cells_initialized" not in st.session_state:
        offsets = np.random.uniform(-0.012, 0.012, SERIES_CELLS)
        offsets -= np.mean(offsets)
        st.session_state.cell_offsets = offsets
        st.session_state.cells_initialized = True

initialize_state()

# ==============================================================
# 5. UTILITY FUNCTIONS
# ==============================================================

def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_fault_event(event, details, severity="INFO"):
    st.session_state.fault_log.append({
        "Time": timestamp(),
        "Event": event,
        "Details": details,
        "Severity": severity
    })
    st.session_state.fault_log = st.session_state.fault_log[-300:]


def add_cell_event(event, details, severity="INFO"):
    st.session_state.cell_fault_history.append({
        "Time": timestamp(),
        "Event": event,
        "Details": details,
        "Severity": severity
    })
    st.session_state.cell_fault_history = st.session_state.cell_fault_history[-300:]


def clamp(value, low, high):
    return max(low, min(high, value))


def pack_ocv_from_soc(soc):
    """
    Approximate pack open-circuit voltage.
    This is a simplified educational model, not a chemistry-specific
    calibrated lithium-ion voltage curve.
    """
    cell_ocv = 3.0 + (soc / 100.0) * 1.2
    return cell_ocv * SERIES_CELLS


def get_protection_state():
    p = st.session_state.protection

    critical = (
        p["temp_critical"]
        or p["voltage_low_critical"]
        or p["voltage_high_critical"]
        or p["current_critical"]
    )

    warning = (
        p["temp_warning"]
        or p["voltage_low_warning"]
        or p["voltage_high_warning"]
        or p["current_warning"]
    )

    if critical:
        return "CRITICAL"
    if warning:
        return "WARNING"
    return "NORMAL"


def get_protection_action():
    state = get_protection_state()

    if state == "CRITICAL":
        return "Critical Shutdown — Load Disabled"

    if state == "WARNING":
        return "Warning — Load Reduced"

    if abs(st.session_state.effective_current -
           st.session_state.requested_current) > 0.01:
        return "Recovery Mode — Load Restoring Gradually"

    return "Normal Control — Load Restored"


def get_cell_state():
    voltages = st.session_state.cell_voltages
    difference = float(np.max(voltages) - np.min(voltages))
    minimum = float(np.min(voltages))

    if minimum <= WEAK_CELL_CRITICAL_VOLTAGE:
        return "CRITICAL"

    if difference >= CELL_IMBALANCE_CRITICAL:
        return "CRITICAL"

    if minimum < WEAK_CELL_WARNING_VOLTAGE:
        return "WARNING"

    if difference >= CELL_IMBALANCE_WARNING:
        return "WARNING"

    return "NORMAL"

# ==============================================================
# 6. PROTECTION SYSTEM WITH HYSTERESIS
# ==============================================================

def update_protection(voltage, current, temperature):

    p = st.session_state.protection
    events = []

    # ---------------- TEMP WARNING ----------------
    if not p["temp_warning"] and temperature >= WARNING_TEMP_ON:
        p["temp_warning"] = True
        events.append(("High Temperature Warning", "Temperature warning activated", "WARNING"))

    elif p["temp_warning"] and temperature <= WARNING_TEMP_OFF:
        p["temp_warning"] = False
        events.append(("High Temperature Warning", "Temperature warning recovered", "INFO"))

    # ---------------- TEMP CRITICAL ----------------
    if not p["temp_critical"] and temperature >= CRITICAL_TEMP_ON:
        p["temp_critical"] = True
        events.append(("Critical Temperature", "Critical temperature shutdown activated", "CRITICAL"))

    elif p["temp_critical"] and temperature <= CRITICAL_TEMP_OFF:
        p["temp_critical"] = False
        events.append(("Critical Temperature", "Critical temperature recovered", "INFO"))

    # ---------------- LOW VOLTAGE WARNING ----------------
    if not p["voltage_low_warning"] and voltage <= WARNING_VOLTAGE_LOW_ON:
        p["voltage_low_warning"] = True
        events.append(("Low Voltage Warning", "Low pack voltage warning activated", "WARNING"))

    elif p["voltage_low_warning"] and voltage >= WARNING_VOLTAGE_LOW_OFF:
        p["voltage_low_warning"] = False
        events.append(("Low Voltage Warning", "Low pack voltage warning recovered", "INFO"))

    # ---------------- HIGH VOLTAGE WARNING ----------------
    if not p["voltage_high_warning"] and voltage >= WARNING_VOLTAGE_HIGH_ON:
        p["voltage_high_warning"] = True
        events.append(("High Voltage Warning", "High pack voltage warning activated", "WARNING"))

    elif p["voltage_high_warning"] and voltage <= WARNING_VOLTAGE_HIGH_OFF:
        p["voltage_high_warning"] = False
        events.append(("High Voltage Warning", "High pack voltage warning recovered", "INFO"))

    # ---------------- LOW VOLTAGE CRITICAL ----------------
    if not p["voltage_low_critical"] and voltage <= CRITICAL_VOLTAGE_LOW_ON:
        p["voltage_low_critical"] = True
        events.append(("Critical Low Voltage", "Critical low voltage shutdown activated", "CRITICAL"))

    elif p["voltage_low_critical"] and voltage >= CRITICAL_VOLTAGE_LOW_OFF:
        p["voltage_low_critical"] = False
        events.append(("Critical Low Voltage", "Critical low voltage recovered", "INFO"))

    # ---------------- HIGH VOLTAGE CRITICAL ----------------
    if not p["voltage_high_critical"] and voltage >= CRITICAL_VOLTAGE_HIGH_ON:
        p["voltage_high_critical"] = True
        events.append(("Critical High Voltage", "Critical high voltage shutdown activated", "CRITICAL"))

    elif p["voltage_high_critical"] and voltage <= CRITICAL_VOLTAGE_HIGH_OFF:
        p["voltage_high_critical"] = False
        events.append(("Critical High Voltage", "Critical high voltage recovered", "INFO"))

    # ---------------- CURRENT WARNING ----------------
    if not p["current_warning"] and abs(current) >= WARNING_CURRENT_ON:
        p["current_warning"] = True
        events.append(("High Current Warning", "Current warning activated", "WARNING"))

    elif p["current_warning"] and abs(current) <= WARNING_CURRENT_OFF:
        p["current_warning"] = False
        events.append(("High Current Warning", "Current warning recovered", "INFO"))

    # ---------------- CURRENT CRITICAL ----------------
    if not p["current_critical"] and abs(current) >= CRITICAL_CURRENT_ON:
        p["current_critical"] = True
        events.append(("Critical Current", "Critical current protection activated", "CRITICAL"))

    elif p["current_critical"] and abs(current) <= CRITICAL_CURRENT_OFF:
        p["current_critical"] = False
        events.append(("Critical Current", "Critical current protection recovered", "INFO"))

    # Record transition events
    for event, details, severity in events:
        add_fault_event(event, details, severity)

    return get_protection_state()

# ==============================================================
# 7. CELL VOLTAGE MODEL
# ==============================================================

def generate_cell_voltages(pack_voltage, scenario="Normal cells"):
    """Generate repeatable cell readings without accumulating scenario offsets."""
    average_cell_voltage = pack_voltage / SERIES_CELLS
    base_offsets = np.array([
        0.003, -0.004, 0.005, -0.002, 0.001, -0.005, 0.004,
        -0.001, 0.002, -0.003, 0.005, -0.002, -0.003
    ], dtype=float)
    offsets = base_offsets.copy()

    if scenario == "Cell imbalance":
        offsets[5] += 0.075
        offsets[10] -= 0.055
    elif scenario == "Weak cell":
        # Fault injection is applied to cell 4, then the remaining cell groups
        # share the rest of the pack voltage to keep the pack sum coherent.
        weak_voltage = 3.05
        other_indices = [i for i in range(SERIES_CELLS) if i != 3]
        other_offsets = base_offsets[other_indices].copy()
        other_offsets -= np.mean(other_offsets)
        remaining_average = (pack_voltage - weak_voltage) / len(other_indices)
        voltages = np.full(SERIES_CELLS, remaining_average, dtype=float)
        voltages[other_indices] += other_offsets
        voltages[3] = weak_voltage
    elif scenario == "Multiple cell imbalance":
        offsets[1] += 0.090
        offsets[4] -= 0.080
        offsets[8] += 0.065
        offsets[11] -= 0.070
    elif scenario == "High cell":
        offsets[7] += 0.180

    if scenario != "Weak cell":
        offsets -= np.mean(offsets)
        voltages = average_cell_voltage + offsets

    # Balancing offsets are stored separately from scenario injection so the
    # selected fault does not grow on every refresh.
    voltages += st.session_state.balance_adjustments
    voltages = np.clip(voltages, CELL_MIN_VOLTAGE, CELL_MAX_VOLTAGE)

    st.session_state.cell_voltages = voltages
    st.session_state.cell_offsets = offsets.copy()
    return voltages

# 8. CELL BALANCING MODEL
# ==============================================================

def perform_cell_balancing():
    """Apply small, persistent simulated reductions to high-voltage cells."""
    voltages = st.session_state.cell_voltages.copy()
    average_voltage = float(np.mean(voltages))
    difference = float(np.max(voltages) - np.min(voltages))
    eligible_cells = np.where(voltages > average_voltage + BALANCING_START_DIFFERENCE)[0]
    active = difference >= CELL_IMBALANCE_WARNING and len(eligible_cells) > 0
    st.session_state.cell_balancing_active = active

    if active:
        for index in eligible_cells:
            st.session_state.balance_adjustments[index] -= BALANCING_RATE
        st.session_state.balance_adjustments = np.clip(
            st.session_state.balance_adjustments, -0.12, 0.0
        )
        # Reapply adjustments to the current generated readings.
        voltages = np.clip(
            voltages - BALANCING_RATE * np.isin(np.arange(SERIES_CELLS), eligible_cells),
            CELL_MIN_VOLTAGE, CELL_MAX_VOLTAGE
        )
        st.session_state.balancing_count += 1
        st.session_state.balancing_history = st.session_state.balancing_history[-300:]
        selected = ", ".join(f"C{i+1:02d}" for i in eligible_cells)
        # Keep balancing history readable: log only status transitions or every
        # 10th active step rather than every auto-refresh.
        if (not st.session_state.balancing_history
                or st.session_state.balancing_history[-1]["Status"] != "BALANCING ACTIVE"
                or st.session_state.balancing_count % 10 == 0):
            st.session_state.balancing_history.append({
                "Time": timestamp(), "Status": "BALANCING ACTIVE",
                "Cells Selected": selected,
                "Voltage Difference (V)": difference,
                "Average Voltage (V)": average_voltage
            })
    else:
        if (not st.session_state.balancing_history
                or st.session_state.balancing_history[-1]["Status"] != "BALANCING INACTIVE"):
            st.session_state.balancing_history.append({
                "Time": timestamp(), "Status": "BALANCING INACTIVE",
                "Cells Selected": "None",
                "Voltage Difference (V)": difference,
                "Average Voltage (V)": average_voltage
            })

    st.session_state.cell_voltages = np.clip(voltages, CELL_MIN_VOLTAGE, CELL_MAX_VOLTAGE)
    return active

# 9. CELL FAULT DETECTION
# ==============================================================

def update_cell_protection():
    """Log cell-level status changes and individual weak-cell transitions."""
    voltages = st.session_state.cell_voltages
    maximum = float(np.max(voltages))
    minimum = float(np.min(voltages))
    difference = maximum - minimum
    cell_state = get_cell_state()
    previous_state = st.session_state.last_cell_state

    if cell_state != previous_state:
        if cell_state == "WARNING":
            add_cell_event("Cell Imbalance / Weak Cell Warning",
                          f"Cell warning detected. ΔV={difference:.3f} V, min={minimum:.3f} V", "WARNING")
        elif cell_state == "CRITICAL":
            add_cell_event("Critical Cell Condition",
                          f"Critical cell condition. ΔV={difference:.3f} V, min={minimum:.3f} V", "CRITICAL")
        else:
            add_cell_event("Cell Condition Recovered", "Cell voltage condition returned to normal", "INFO")
        st.session_state.last_cell_state = cell_state

    weak_now = [i + 1 for i, v in enumerate(voltages) if v < WEAK_CELL_WARNING_VOLTAGE]
    weak_before = st.session_state.logged_weak_cells
    for cell_num in weak_now:
        if cell_num not in weak_before:
            v = float(voltages[cell_num - 1])
            severity = "CRITICAL" if v <= WEAK_CELL_CRITICAL_VOLTAGE else "WARNING"
            add_cell_event(f"Weak Cell C{cell_num:02d}", f"Cell voltage is {v:.3f} V", severity)
    for cell_num in weak_before:
        if cell_num not in weak_now:
            add_cell_event(f"Weak Cell C{cell_num:02d} Recovered", "Cell voltage returned above weak-cell threshold", "INFO")
    st.session_state.logged_weak_cells = weak_now
    return cell_state

# 10. SIMULATION ENGINE
# ==============================================================

def simulation_step(requested_current, duration_seconds=2):
    """Advance the virtual pack by one time step using protected current."""
    requested_current = float(requested_current)
    st.session_state.requested_current = requested_current
    old_temp = st.session_state.temperature

    # First determine pack protection from the current pack conditions.
    pack_voltage = st.session_state.pack_voltage
    update_protection(pack_voltage, requested_current, old_temp)
    state = get_protection_state()
    target_current = (0.0 if state == "CRITICAL" else
                      requested_current * 0.5 if state == "WARNING" else requested_current)

    # Gradual restoration when protection has cleared.
    if state == "NORMAL":
        difference = target_current - st.session_state.effective_current
        if abs(difference) <= 1.0:
            st.session_state.effective_current = target_current
        else:
            st.session_state.effective_current += 1.0 if difference > 0 else -1.0
    else:
        st.session_state.effective_current = target_current

    current = float(st.session_state.effective_current)
    # SoC and thermal calculations use the effective, protected load.
    soc_change = current * duration_seconds / (3600.0 * CAPACITY_AH) * 100.0
    st.session_state.soc = clamp(st.session_state.soc - soc_change, 0.0, 100.0)
    st.session_state.consumed_capacity += max(current, 0.0) * duration_seconds / 3600.0

    ocv = pack_ocv_from_soc(st.session_state.soc)
    pack_voltage = clamp(ocv - current * INTERNAL_RESISTANCE, PACK_MIN_VOLTAGE, PACK_MAX_VOLTAGE)
    st.session_state.pack_voltage = pack_voltage

    heat_generated = current ** 2 * INTERNAL_RESISTANCE
    cooling = COOLING_COEFFICIENT * (st.session_state.temperature - AMBIENT_TEMP)
    net_heat = heat_generated - cooling
    temp_change = net_heat * duration_seconds / THERMAL_CAPACITY
    st.session_state.temperature = clamp(st.session_state.temperature + temp_change, AMBIENT_TEMP, 80.0)
    st.session_state.heating_rate = (st.session_state.temperature - old_temp) / duration_seconds
    st.session_state.peak_temperature = max(st.session_state.peak_temperature, st.session_state.temperature)
    st.session_state.cooling_power = max(0.0, COOLING_COEFFICIENT * (st.session_state.temperature - AMBIENT_TEMP))

    # Evaluate pack protection once more against updated estimates, then act
    # immediately on any newly triggered critical state.
    update_protection(st.session_state.pack_voltage, current, st.session_state.temperature)
    final_state = get_protection_state()
    if final_state == "CRITICAL":
        st.session_state.effective_current = 0.0
    elif final_state == "WARNING":
        st.session_state.effective_current = requested_current * 0.5

    # Generate cell readings, balancing, then cell-protection checks.
    generate_cell_voltages(st.session_state.pack_voltage, st.session_state.cell_scenario)
    perform_cell_balancing()
    cell_state = update_cell_protection()
    if cell_state == "CRITICAL":
        st.session_state.effective_current = 0.0
    elif cell_state == "WARNING" and final_state == "NORMAL":
        st.session_state.effective_current = requested_current * 0.5

    power = st.session_state.pack_voltage * st.session_state.effective_current
    if power >= 0:
        st.session_state.energy_discharged += power * duration_seconds / 3600.0
    else:
        st.session_state.energy_charged += abs(power) * duration_seconds / 3600.0

    st.session_state.simulation_time += duration_seconds
    st.session_state.performance_history.append({
        "Time (s)": st.session_state.simulation_time,
        "Voltage (V)": st.session_state.pack_voltage,
        "Current (A)": st.session_state.effective_current,
        "Requested Current (A)": requested_current,
        "Temperature (°C)": st.session_state.temperature,
        "Power (W)": power,
        "SoC (%)": st.session_state.soc
    })
    st.session_state.thermal_history.append({
        "Time (s)": st.session_state.simulation_time,
        "Temperature (°C)": st.session_state.temperature,
        "Heating Rate (°C/s)": st.session_state.heating_rate,
        "Cooling Power (W)": st.session_state.cooling_power
    })

# 11. MANUAL SIMULATION ADVANCE
# ==============================================================

def manual_simulation_step():
    """Advance a 10-second manual test using entered voltage/current/temp."""
    duration_seconds = 10.0
    requested = float(st.session_state.manual_current)
    voltage = float(st.session_state.manual_voltage)
    temperature = float(st.session_state.manual_temperature)
    st.session_state.requested_current = requested
    st.session_state.pack_voltage = voltage
    st.session_state.temperature = temperature

    update_protection(voltage, requested, temperature)
    state = get_protection_state()
    target = (0.0 if state == "CRITICAL" else
              requested * 0.5 if state == "WARNING" else requested)
    if state == "NORMAL":
        difference = target - st.session_state.effective_current
        if abs(difference) <= 1.0:
            st.session_state.effective_current = target
        else:
            st.session_state.effective_current += 1.0 if difference > 0 else -1.0
    else:
        st.session_state.effective_current = target

    effective = float(st.session_state.effective_current)
    st.session_state.soc = clamp(
        st.session_state.soc - effective * duration_seconds / (3600.0 * CAPACITY_AH) * 100.0,
        0.0, 100.0
    )
    st.session_state.consumed_capacity += max(effective, 0.0) * duration_seconds / 3600.0
    st.session_state.heating_rate = 0.0
    st.session_state.peak_temperature = max(st.session_state.peak_temperature, temperature)
    st.session_state.cooling_power = max(0.0, COOLING_COEFFICIENT * (temperature - AMBIENT_TEMP))

    generate_cell_voltages(voltage, st.session_state.cell_scenario)
    perform_cell_balancing()
    cell_state = update_cell_protection()
    if cell_state == "CRITICAL":
        st.session_state.effective_current = 0.0
    elif cell_state == "WARNING" and state == "NORMAL":
        st.session_state.effective_current = requested * 0.5

    power = voltage * st.session_state.effective_current
    if power >= 0:
        st.session_state.energy_discharged += power * duration_seconds / 3600.0
    else:
        st.session_state.energy_charged += abs(power) * duration_seconds / 3600.0

    st.session_state.simulation_time += 10
    st.session_state.performance_history.append({
        "Time (s)": st.session_state.simulation_time,
        "Voltage (V)": voltage,
        "Current (A)": st.session_state.effective_current,
        "Requested Current (A)": requested,
        "Temperature (°C)": temperature,
        "Power (W)": power,
        "SoC (%)": st.session_state.soc
    })
    st.session_state.thermal_history.append({
        "Time (s)": st.session_state.simulation_time,
        "Temperature (°C)": temperature,
        "Heating Rate (°C/s)": 0.0,
        "Cooling Power (W)": st.session_state.cooling_power
    })

# 12. RESET SYSTEM
# ==============================================================

def reset_system():

    keys_to_delete = list(st.session_state.keys())

    for key in keys_to_delete:
        del st.session_state[key]

    initialize_state()

# ==============================================================
# 13. SIDEBAR
# ==============================================================

st.sidebar.title("🔋 Smart EV BMS")
st.sidebar.caption("Version 4.4 Virtual Simulation Edition | Cell Monitoring & Balancing")

mode = st.sidebar.radio(
    "Operating Mode",
    ["Automatic Simulation", "Manual Fault Testing"]
)

st.sidebar.divider()

st.sidebar.subheader("Cell Simulation Scenario")

cell_scenario = st.sidebar.selectbox(
    "Cell Condition",
    [
        "Normal cells",
        "Cell imbalance",
        "Weak cell",
        "Multiple cell imbalance",
        "High cell"
    ],
    index=[
        "Normal cells",
        "Cell imbalance",
        "Weak cell",
        "Multiple cell imbalance",
        "High cell"
    ].index(st.session_state.cell_scenario)
)

st.session_state.cell_scenario = cell_scenario

st.sidebar.caption(
    "Cell conditions are simulated. No physical battery sensors are connected."
)

st.sidebar.divider()

if st.sidebar.button("🔄 Reset System", use_container_width=True):
    reset_system()
    st.rerun()

# ==============================================================
# 14. AUTOMATIC SIMULATION CONTROLS
# ==============================================================

if mode == "Automatic Simulation":

    st.sidebar.subheader("Automatic Simulation")

    scenario = st.sidebar.selectbox(
        "Driving Scenario",
        [
            "Idle",
            "Driving - Low Load",
            "Driving - High Load",
            "Charging"
        ],
        index=[
            "Idle",
            "Driving - Low Load",
            "Driving - High Load",
            "Charging"
        ].index(st.session_state.auto_scenario)
    )

    st.session_state.auto_scenario = scenario

    scenario_currents = {
        "Idle": 0.0,
        "Driving - Low Load": 5.0,
        "Driving - High Load": 15.0,
        "Charging": -5.0
    }

    current = scenario_currents[scenario]

    st_autorefresh(
        interval=2000,
        key="auto_refresh"
    )

    simulation_step(current, duration_seconds=2)

# ==============================================================
# 15. MANUAL FAULT TESTING CONTROLS
# ==============================================================

else:

    st.sidebar.subheader("Manual Fault Testing")

    st.session_state.manual_voltage = st.sidebar.slider(
        "Pack Voltage (V)",
        min_value=39.0,
        max_value=54.6,
        value=float(st.session_state.manual_voltage),
        step=0.1
    )

    st.session_state.manual_current = st.sidebar.slider(
        "Requested Current (A)",
        min_value=-30.0,
        max_value=30.0,
        value=float(st.session_state.manual_current),
        step=0.5
    )

    st.session_state.manual_temperature = st.sidebar.slider(
        "Battery Temperature (°C)",
        min_value=15.0,
        max_value=70.0,
        value=float(st.session_state.manual_temperature),
        step=0.5
    )

    st.sidebar.caption(
        "Manual mode lets you test faults. "
        "The entered temperature is held for the test."
    )

    if st.sidebar.button(
        "▶ Advance Manual Simulation (10 sec)",
        use_container_width=True
    ):
        manual_simulation_step()
        st.rerun()

# ==============================================================
# 16. HEADER
# ==============================================================

st.title("🔋 Smart EV Battery Management System")

st.markdown(
    "**V4.4 — Cell-Level Monitoring & Intelligent Balancing**"
)

st.caption(
    "Simulation prototype | 13S4P lithium-ion pack | "
    "Automatic simulation and manual fault testing"
)

st.divider()

# ==============================================================
# 17. STATUS SUMMARY
# ==============================================================

protection_state = get_protection_state()
cell_state = get_cell_state()
protection_action = get_protection_action()

if protection_state == "NORMAL":
    st.markdown(
        '<div class="status-normal">🟢 SYSTEM NORMAL — '
        'NO ACTIVE PACK FAULT</div>',
        unsafe_allow_html=True
    )

elif protection_state == "WARNING":
    st.markdown(
        '<div class="status-warning">🟠 WARNING — '
        'LOAD REDUCTION ACTIVE</div>',
        unsafe_allow_html=True
    )

else:
    st.markdown(
        '<div class="status-critical">🔴 CRITICAL — '
        'SIMULATED LOAD SHUTDOWN</div>',
        unsafe_allow_html=True
    )

st.write("")

if cell_state == "NORMAL":
    st.success("Cell Monitoring: Normal voltage distribution")
elif cell_state == "WARNING":
    st.warning("Cell Monitoring: Imbalance or weak cell warning")
else:
    st.error("Cell Monitoring: Critical cell condition")

st.info(f"**Safety Action:** {protection_action}")

# ==============================================================
# 18. BATTERY OVERVIEW
# ==============================================================

st.header("🔋 Battery Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "State of Charge",
    f"{st.session_state.soc:.1f}%"
)

c2.metric(
    "Pack Voltage",
    f"{st.session_state.pack_voltage:.2f} V"
)

c3.metric(
    "Battery Current",
    f"{st.session_state.effective_current:.2f} A"
)

c4.metric(
    "Temperature",
    f"{st.session_state.temperature:.1f} °C"
)

c5, c6, c7, c8 = st.columns(4)

c5.metric(
    "Requested Current",
    f"{st.session_state.requested_current:.2f} A"
)

c6.metric(
    "Effective Current",
    f"{st.session_state.effective_current:.2f} A"
)

c7.metric(
    "Peak Temperature",
    f"{st.session_state.peak_temperature:.2f} °C"
)

c8.metric(
    "Heating Rate",
    f"{st.session_state.heating_rate:.3f} °C/s"
)

# ==============================================================
# 19. BATTERY PARAMETER GAUGES
# ==============================================================

st.header("📊 Battery Parameter Analysis")

def make_gauge(title, value, minimum, maximum, unit, thresholds=None):

    steps = []

    if title == "Voltage":
        steps = [
            {"range": [minimum, 42.0], "color": "#572c30"},
            {"range": [42.0, 43.0], "color": "#6a4b24"},
            {"range": [43.0, 52.0], "color": "#174b39"},
            {"range": [52.0, 53.0], "color": "#6a4b24"},
            {"range": [53.0, maximum], "color": "#572c30"}
        ]

    elif title == "Current":
        steps = [
            {"range": [minimum, 18.0], "color": "#174b39"},
            {"range": [18.0, 20.0], "color": "#6a4b24"},
            {"range": [20.0, 25.0], "color": "#572c30"},
            {"range": [25.0, maximum], "color": "#712c34"}
        ]

    elif title == "Temperature":
        steps = [
            {"range": [minimum, 42.0], "color": "#174b39"},
            {"range": [42.0, 45.0], "color": "#6a4b24"},
            {"range": [45.0, 55.0], "color": "#805023"},
            {"range": [55.0, maximum], "color": "#712c34"}
        ]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": f" {unit}"},
        title={"text": title},
        gauge={
            "axis": {"range": [minimum, maximum]},
            "bar": {"color": "#60a5fa"},
            "steps": steps
        }
    ))

    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=50, b=15),
        template="plotly_dark"
    )

    return fig

g1, g2, g3 = st.columns(3)

with g1:
    st.plotly_chart(
        make_gauge(
            "Voltage",
            st.session_state.pack_voltage,
            PACK_MIN_VOLTAGE,
            PACK_MAX_VOLTAGE,
            "V"
        ),
        use_container_width=True
    )

with g2:
    st.plotly_chart(
        make_gauge(
            "Current",
            abs(st.session_state.effective_current),
            0,
            30,
            "A"
        ),
        use_container_width=True
    )

with g3:
    st.plotly_chart(
        make_gauge(
            "Temperature",
            st.session_state.temperature,
            15,
            70,
            "°C"
        ),
        use_container_width=True
    )

# ==============================================================
# 20. BATTERY CAPACITY ANALYSIS
# ==============================================================

st.header("🔌 Battery Capacity Analysis")

remaining_capacity = CAPACITY_AH * st.session_state.soc / 100.0

capacity_consumed = (
    CAPACITY_AH - remaining_capacity
)

cap1, cap2, cap3 = st.columns(3)

cap1.metric("Rated Capacity", f"{CAPACITY_AH:.2f} Ah")
cap2.metric("Remaining Capacity", f"{remaining_capacity:.2f} Ah")
cap3.metric("Consumed Capacity", f"{capacity_consumed:.2f} Ah")

capacity_fig = go.Figure(
    data=[
        go.Pie(
            labels=["Remaining", "Consumed"],
            values=[remaining_capacity, capacity_consumed],
            hole=0.65
        )
    ]
)

capacity_fig.update_layout(
    title="Battery Capacity Distribution",
    template="plotly_dark",
    height=320
)

st.plotly_chart(capacity_fig, use_container_width=True)

# ==============================================================
# 21. POWER & ENERGY ANALYSIS
# ==============================================================

st.header("⚡ Power & Energy Analysis")

instantaneous_power = (
    st.session_state.pack_voltage
    * st.session_state.effective_current
)

p1, p2, p3 = st.columns(3)

p1.metric(
    "Instantaneous Power",
    f"{instantaneous_power:.2f} W"
)

p2.metric(
    "Energy Discharged",
    f"{st.session_state.energy_discharged:.4f} Wh"
)

p3.metric(
    "Energy Charged",
    f"{st.session_state.energy_charged:.4f} Wh"
)

# ==============================================================
# 22. ADVANCED THERMAL MANAGEMENT
# ==============================================================

st.header("🌡️ Advanced Thermal Management")

thermal_state = (
    "CRITICAL"
    if st.session_state.temperature >= CRITICAL_TEMP_ON
    else "WARNING"
    if st.session_state.temperature >= WARNING_TEMP_ON
    else "NORMAL"
)

th1, th2, th3 = st.columns(3)

th1.metric("Thermal State", thermal_state)
th2.metric("Peak Temperature", f"{st.session_state.peak_temperature:.2f} °C")
th3.metric("Cooling Power (Estimated)", f"{st.session_state.cooling_power:.2f} W")

st.caption(
    "Cooling power is a model estimate of heat removal, not a physical measurement."
)

if st.session_state.thermal_history:

    thermal_df = pd.DataFrame(st.session_state.thermal_history)

    fig_thermal = go.Figure()

    fig_thermal.add_trace(go.Scatter(
        x=thermal_df["Time (s)"],
        y=thermal_df["Temperature (°C)"],
        mode="lines",
        name="Temperature"
    ))

    fig_thermal.add_hline(
        y=WARNING_TEMP_ON,
        line_dash="dash",
        annotation_text="Warning 45°C"
    )

    fig_thermal.add_hline(
        y=CRITICAL_TEMP_ON,
        line_dash="dash",
        annotation_text="Critical 55°C"
    )

    fig_thermal.update_layout(
        title="Thermal History",
        xaxis_title="Simulation Time (s)",
        yaxis_title="Temperature (°C)",
        template="plotly_dark"
    )

    st.plotly_chart(fig_thermal, use_container_width=True)

# ==============================================================
# 23. INTELLIGENT PROTECTION SYSTEM
# ==============================================================

st.header("🛡️ Intelligent Protection System")

p = st.session_state.protection

protection_rows = [
    ("Low Voltage Warning", p["voltage_low_warning"], "42.0 V", "43.0 V", "Warning"),
    ("Critical Low Voltage", p["voltage_low_critical"], "39.0 V", "40.5 V", "Shutdown"),
    ("High Voltage Warning", p["voltage_high_warning"], "53.0 V", "52.0 V", "Warning"),
    ("Critical High Voltage", p["voltage_high_critical"], "54.6 V", "53.5 V", "Shutdown"),
    ("High Current Warning", p["current_warning"], "20.0 A", "18.0 A", "Load reduction"),
    ("Critical Current", p["current_critical"], "25.0 A", "22.0 A", "Shutdown"),
    ("High Temperature Warning", p["temp_warning"], "45.0°C", "42.0°C", "Load reduction"),
    ("Critical Temperature", p["temp_critical"], "55.0°C", "48.0°C", "Shutdown"),
]

protection_df = pd.DataFrame(
    protection_rows,
    columns=[
        "Protection",
        "Active",
        "Trigger",
        "Recovery",
        "Action"
    ]
)

st.dataframe(
    protection_df,
    use_container_width=True,
    hide_index=True
)

# ==============================================================
# 24. CELL-LEVEL MONITORING — NEW V4.4
# ==============================================================

st.header("🔬 Cell-Level Voltage Monitoring")
st.caption(
    "13 series cell groups monitored in simulation. "
    "Each group represents 4 parallel cells."
)

cell_voltages = st.session_state.cell_voltages

cell_df = pd.DataFrame({
    "Cell Group": [f"C{i+1:02d}" for i in range(SERIES_CELLS)],
    "Voltage (V)": np.round(cell_voltages, 3),
    "Status": [
        "Critical"
        if value <= WEAK_CELL_CRITICAL_VOLTAGE
        else "Weak"
        if value < WEAK_CELL_WARNING_VOLTAGE
        else "High"
        if value > CELL_NOMINAL_VOLTAGE + 0.12
        else "Normal"
        for value in cell_voltages
    ]
})

# Display individual cell voltage cards
for start in range(0, SERIES_CELLS, 4):

    group = st.columns(4)

    for j, col in enumerate(group):

        index = start + j

        if index >= SERIES_CELLS:
            continue

        voltage = cell_voltages[index]

        if voltage <= WEAK_CELL_CRITICAL_VOLTAGE:
            color = "🔴"
        elif voltage < WEAK_CELL_WARNING_VOLTAGE:
            color = "🟠"
        elif voltage >= CELL_NOMINAL_VOLTAGE + 0.12:
            color = "🟡"
        else:
            color = "🟢"

        with col:
            st.metric(
                f"{color} Cell C{index+1:02d}",
                f"{voltage:.3f} V"
            )

# ==============================================================
# 25. CELL VOLTAGE DISTRIBUTION
# ==============================================================

st.subheader("Cell Voltage Distribution")

cell_fig = go.Figure()

bar_colors = [
    "#ef4444"
    if voltage <= WEAK_CELL_CRITICAL_VOLTAGE
    else "#f59e0b"
    if voltage < WEAK_CELL_WARNING_VOLTAGE
    else "#22c55e"
    if voltage < CELL_NOMINAL_VOLTAGE + 0.12
    else "#60a5fa"
    for voltage in cell_voltages
]

cell_fig.add_trace(go.Bar(
    x=cell_df["Cell Group"],
    y=cell_df["Voltage (V)"],
    marker_color=bar_colors,
    text=np.round(cell_voltages, 3),
    textposition="outside",
    name="Cell Voltage"
))

cell_fig.add_hline(
    y=CELL_NOMINAL_VOLTAGE,
    line_dash="dash",
    annotation_text="Nominal Cell Voltage 3.6 V"
)

cell_fig.add_hline(
    y=WEAK_CELL_WARNING_VOLTAGE,
    line_dash="dot",
    annotation_text="Weak Cell Warning 3.1 V"
)

cell_fig.update_layout(
    template="plotly_dark",
    xaxis_title="Cell Group",
    yaxis_title="Voltage (V)",
    height=420
)

st.plotly_chart(cell_fig, use_container_width=True)

st.dataframe(
    cell_df,
    use_container_width=True,
    hide_index=True
)

# ==============================================================
# 26. CELL IMBALANCE ANALYSIS
# ==============================================================

st.subheader("Cell Imbalance Analysis")

cell_average = float(np.mean(cell_voltages))
cell_maximum = float(np.max(cell_voltages))
cell_minimum = float(np.min(cell_voltages))
cell_difference = cell_maximum - cell_minimum

max_cell_index = int(np.argmax(cell_voltages))
min_cell_index = int(np.argmin(cell_voltages))

imb1, imb2, imb3, imb4 = st.columns(4)

imb1.metric("Average Cell Voltage", f"{cell_average:.3f} V")
imb2.metric("Highest Cell", f"C{max_cell_index+1:02d} · {cell_maximum:.3f} V")
imb3.metric("Lowest Cell", f"C{min_cell_index+1:02d} · {cell_minimum:.3f} V")
imb4.metric("Voltage Difference (ΔV)", f"{cell_difference:.3f} V")

if cell_difference >= CELL_IMBALANCE_CRITICAL:
    st.error(
        f"CRITICAL CELL IMBALANCE: ΔV = {cell_difference:.3f} V"
    )

elif cell_difference >= CELL_IMBALANCE_WARNING:
    st.warning(
        f"CELL IMBALANCE WARNING: ΔV = {cell_difference:.3f} V"
    )

else:
    st.success(
        f"Cell voltage difference is within the simulated normal range "
        f"(ΔV = {cell_difference:.3f} V)."
    )

# ==============================================================
# 27. WEAK CELL IDENTIFICATION
# ==============================================================

st.subheader("Weak Cell Identification")

weak_cells = cell_df[
    cell_df["Voltage (V)"] < WEAK_CELL_WARNING_VOLTAGE
]

critical_cells = cell_df[
    cell_df["Voltage (V)"] <= WEAK_CELL_CRITICAL_VOLTAGE
]

if len(critical_cells) > 0:

    st.error(
        "Critical low-voltage cells detected: "
        + ", ".join(critical_cells["Cell Group"].tolist())
    )

elif len(weak_cells) > 0:

    st.warning(
        "Weak cells detected: "
        + ", ".join(weak_cells["Cell Group"].tolist())
    )

else:

    st.success("No weak cells detected.")

# ==============================================================
# 28. INTELLIGENT CELL BALANCING
# ==============================================================

st.header("⚖️ Intelligent Cell Balancing")

balancing_active = st.session_state.cell_balancing_active

bal1, bal2, bal3 = st.columns(3)

bal1.metric(
    "Balancing Status",
    "ACTIVE" if balancing_active else "INACTIVE"
)

bal2.metric(
    "Cells Selected",
    (
        ", ".join(
            [
                f"C{i+1:02d}"
                for i, v in enumerate(cell_voltages)
                if v > cell_average + BALANCING_START_DIFFERENCE
            ]
        )
        or "None"
    )
)

bal3.metric(
    "Balancing Events / Steps",
    st.session_state.balancing_count
)

if balancing_active:
    st.info(
        "Simulated balancing is active. Selected higher-voltage cells "
        "are being gradually reduced in the model."
    )
else:
    st.info(
        "Balancing is inactive. Cell voltages are within the "
        "simulated balancing activation range."
    )

st.caption(
    "This balancing model adjusts simulated cell-voltage offsets. "
    "It is not a real resistor circuit, balancing current measurement, "
    "or physical battery balancing."
)

# ==============================================================
# 29. CELL BALANCING HISTORY
# ==============================================================

st.subheader("Cell Balancing History")

if st.session_state.balancing_history:

    balancing_df = pd.DataFrame(
        st.session_state.balancing_history
    )

    st.dataframe(
        balancing_df.tail(50),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("Cell balancing history will appear after simulation steps.")

# ==============================================================
# 30. BATTERY PERFORMANCE HISTORY
# ==============================================================

st.header("📈 Battery Performance History")

if st.session_state.performance_history:

    performance_df = pd.DataFrame(
        st.session_state.performance_history
    )

    tabs = st.tabs([
        "Voltage",
        "Current",
        "Temperature",
        "Power",
        "SoC"
    ])

    with tabs[0]:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=performance_df["Time (s)"],
            y=performance_df["Voltage (V)"],
            mode="lines",
            name="Pack Voltage"
        ))

        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Time (s)",
            yaxis_title="Voltage (V)"
        )

        st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=performance_df["Time (s)"],
            y=performance_df["Current (A)"],
            mode="lines",
            name="Effective Current"
        ))

        fig.add_trace(go.Scatter(
            x=performance_df["Time (s)"],
            y=performance_df["Requested Current (A)"],
            mode="lines",
            name="Requested Current"
        ))

        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Time (s)",
            yaxis_title="Current (A)"
        )

        st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=performance_df["Time (s)"],
            y=performance_df["Temperature (°C)"],
            mode="lines",
            name="Temperature"
        ))

        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Time (s)",
            yaxis_title="Temperature (°C)"
        )

        st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=performance_df["Time (s)"],
            y=performance_df["Power (W)"],
            mode="lines",
            name="Power"
        ))

        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Time (s)",
            yaxis_title="Power (W)"
        )

        st.plotly_chart(fig, use_container_width=True)

    with tabs[4]:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=performance_df["Time (s)"],
            y=performance_df["SoC (%)"],
            mode="lines",
            name="State of Charge"
        ))

        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Time (s)",
            yaxis_title="SoC (%)"
        )

        st.plotly_chart(fig, use_container_width=True)

else:

    st.info("Performance history will be generated during simulation.")

# ==============================================================
# 31. FAULT EVENT & RECOVERY LOG
# ==============================================================

st.header("📝 Fault Event & Recovery Log")

if st.session_state.fault_log:

    fault_df = pd.DataFrame(st.session_state.fault_log)

    st.dataframe(
        fault_df.tail(100),
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "⬇ Download Pack Fault Log CSV",
        data=fault_df.to_csv(index=False),
        file_name="smart_bms_v4_4_pack_fault_log.csv",
        mime="text/csv"
    )

else:

    st.info("No pack protection events recorded.")

# ==============================================================
# 32. CELL FAULT HISTORY
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
    "Hardware Connection": "Not connected",
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
