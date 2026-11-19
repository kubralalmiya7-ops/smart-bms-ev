# VERSION 4.3 - INTELLIGENT PROTECTION & FAULT RECOVERY
# Software simulation only. Not real battery protection hardware.
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Smart EV BMS V4.3",
    page_icon="🔋",
    layout="wide"
)

# ============================================================
# 2. DASHBOARD STYLE
# ============================================================

st.markdown("""
<style>
.stApp {
    background-color: #0b1120;
    color: #e8eef7;
}
[data-testid="stSidebar"] {
    background-color: #111a2b;
}
.metric-card {
    background-color: #162236;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #26364e;
}
.status-normal {
    background-color: #12382b;
    color: #4ade80;
    padding: 12px;
    border-radius: 10px;
    font-weight: bold;
}
.status-warning {
    background-color: #463416;
    color: #fbbf24;
    padding: 12px;
    border-radius: 10px;
    font-weight: bold;
}
.status-critical {
    background-color: #4a1e26;
    color: #fb7185;
    padding: 12px;
    border-radius: 10px;
    font-weight: bold;
}
.small-info {
    color: #9fb0c8;
    font-size: 13px;
}
h1, h2, h3 {
    color: #eaf2ff;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. BATTERY SPECIFICATIONS
# ============================================================

PACK_SERIES = 13
PACK_PARALLEL = 4

CELL_NOMINAL_V = 3.6
CELL_MIN_V = 3.0
CELL_MAX_V = 4.2

PACK_NOMINAL_V = PACK_SERIES * CELL_NOMINAL_V
PACK_MIN_V = PACK_SERIES * CELL_MIN_V
PACK_MAX_V = PACK_SERIES * CELL_MAX_V

DEFAULT_CAPACITY_AH = 10.0
INTERNAL_RESISTANCE = 0.08

AMBIENT_TEMP = 25.0
THERMAL_CAPACITY = 500.0
COOLING_COEFF = 1.5

# Voltage thresholds
VOLTAGE_LOW_WARNING = 42.0
VOLTAGE_LOW_RECOVERY = 43.0

VOLTAGE_HIGH_WARNING = 53.0
VOLTAGE_HIGH_RECOVERY = 52.0

VOLTAGE_LOW_CRITICAL = PACK_MIN_V
VOLTAGE_LOW_CRITICAL_RECOVERY = 40.5

VOLTAGE_HIGH_CRITICAL = PACK_MAX_V
VOLTAGE_HIGH_CRITICAL_RECOVERY = 53.5

# Current thresholds (discharge current magnitude)
CURRENT_WARNING = 20.0
CURRENT_WARNING_RECOVERY = 18.0

CURRENT_CRITICAL = 25.0
CURRENT_CRITICAL_RECOVERY = 22.0

# Thermal thresholds
TEMP_WARNING = 45.0
TEMP_WARNING_RECOVERY = 42.0

TEMP_CRITICAL = 55.0
TEMP_CRITICAL_RECOVERY = 48.0

# Protection / restoration
WARNING_LOAD_FACTOR = 0.50
LOAD_RESTORE_STEP_A = 1.0  # Maximum increase per simulation step
SIMULATION_STEP_SECONDS = 2.0

# ============================================================
# 4. SESSION STATE INITIALIZATION
# ============================================================

defaults = {
    "soc": 80.0,
    "temperature": 25.0,
    "voltage": PACK_NOMINAL_V,
    "current": 0.0,
    "requested_current": 0.0,
    "effective_current": 0.0,
    "capacity_ah": DEFAULT_CAPACITY_AH,
    "discharged_energy_wh": 0.0,
    "charged_energy_wh": 0.0,
    "peak_temperature": 25.0,
    "heating_rate": 0.0,
    "cooling_power": 0.0,
    "thermal_state": "Normal",
    "safety_action": "Normal operation",
    "system_mode": "Automatic Simulation",
    "fault_flags": {},
    "fault_history": [],
    "performance_history": [],
    "thermal_history": [],
    "last_faults": [],
    "previous_temperature": 25.0,
    "last_tick_time": None,
    "last_effective_current": 0.0,
    "simulation_elapsed": 0,
    "recovery_mode": False,
    "recovery_target": 0.0,
    "reset_requested": False,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value

# ============================================================
# 5. UTILITY FUNCTIONS
# ============================================================

def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_event(event, severity, action, details=""):
    entry = {
        "Timestamp": timestamp(),
        "Event": event,
        "Severity": severity,
        "Action": action,
        "Details": details
    }

    st.session_state.fault_history.insert(0, entry)

    # Keep the latest 500 entries
    st.session_state.fault_history = st.session_state.fault_history[:500]


def add_performance_record():
    st.session_state.performance_history.append({
        "Timestamp": timestamp(),
        "Voltage (V)": round(st.session_state.voltage, 2),
        "Current (A)": round(st.session_state.current, 2),
        "Requested Current (A)": round(st.session_state.requested_current, 2),
        "Effective Current (A)": round(st.session_state.effective_current, 2),
        "Temperature (°C)": round(st.session_state.temperature, 2),
        "SoC (%)": round(st.session_state.soc, 2),
        "Power (W)": round(st.session_state.voltage * st.session_state.current, 2),
        "Thermal State": st.session_state.thermal_state,
        "Safety Action": st.session_state.safety_action,
    })

    st.session_state.performance_history = \
        st.session_state.performance_history[-1000:]


def add_thermal_record():
    st.session_state.thermal_history.append({
        "Timestamp": timestamp(),
        "Temperature (°C)": round(st.session_state.temperature, 2),
        "Heating Rate (°C/min)": round(st.session_state.heating_rate, 2),
        "Cooling Power (W)": round(st.session_state.cooling_power, 2),
        "Thermal State": st.session_state.thermal_state,
    })

    st.session_state.thermal_history = \
        st.session_state.thermal_history[-1000:]


def reset_simulation():
    for key, value in defaults.items():
        st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value

    st.session_state["reset_requested"] = True

# ============================================================
# 6. BATTERY MODEL
# ============================================================

def calculate_ocv(soc):
    """
    Illustrative pack open-circuit-voltage approximation.
    Not a measured Li-ion voltage/SOC lookup table.
    """
    soc = np.clip(soc, 0, 100)

    cell_ocv = 3.0 + (soc / 100.0) * 1.2
    return cell_ocv * PACK_SERIES


def calculate_voltage(soc, current):
    """
    Simplified terminal voltage:
    V_terminal = OCV - I*R
    Positive current represents discharge.
    """
    voltage = calculate_ocv(soc) - (current * INTERNAL_RESISTANCE)

    return float(np.clip(voltage, PACK_MIN_V, PACK_MAX_V))


def calculate_soc(soc, current, elapsed_seconds, capacity_ah):
    """
    Coulomb counting.
    Positive current = discharge.
    Negative current = charging.
    """
    if capacity_ah <= 0:
        return soc

    change = current * elapsed_seconds / (3600 * capacity_ah) * 100.0
    new_soc = soc - change

    return float(np.clip(new_soc, 0.0, 100.0))


def calculate_temperature(temp, current, elapsed_seconds):
    """
    Simplified thermal model:
    Heat generated = I^2 * R
    Cooling = coefficient * (temperature - ambient)
    """
    heat_generation = (current ** 2) * INTERNAL_RESISTANCE
    heat_loss = COOLING_COEFF * (temp - AMBIENT_TEMP)

    net_heat = heat_generation - heat_loss

    temp_change = net_heat * elapsed_seconds / THERMAL_CAPACITY

    new_temp = temp + temp_change

    return float(max(AMBIENT_TEMP, new_temp))


# ============================================================
# 7. INTELLIGENT HYSTERESIS PROTECTION
# ============================================================

def update_fault_flag(name, active_condition, recovery_condition):
    """
    Fault activates when active_condition is true.
    Once active, it remains active until recovery_condition is true.
    """
    flags = st.session_state.fault_flags
    was_active = flags.get(name, False)

    if not was_active and active_condition:
        flags[name] = True
        return "activated"

    if was_active and recovery_condition:
        flags[name] = False
        return "recovered"

    flags[name] = was_active
    return None


def update_protection():
    v = st.session_state.voltage
    i = abs(st.session_state.requested_current)
    t = st.session_state.temperature

    transitions = []

    # Thermal warning
    result = update_fault_flag(
        "High Temperature Warning",
        t >= TEMP_WARNING,
        t <= TEMP_WARNING_RECOVERY
    )
    if result:
        transitions.append(("High Temperature Warning", result))

    # Thermal critical
    result = update_fault_flag(
        "Critical Temperature",
        t >= TEMP_CRITICAL,
        t <= TEMP_CRITICAL_RECOVERY
    )
    if result:
        transitions.append(("Critical Temperature", result))

    # Low voltage warning
    result = update_fault_flag(
        "Low Voltage Warning",
        v <= VOLTAGE_LOW_WARNING,
        v >= VOLTAGE_LOW_RECOVERY
    )
    if result:
        transitions.append(("Low Voltage Warning", result))

    # Low voltage critical
    result = update_fault_flag(
        "Critical Low Voltage",
        v <= VOLTAGE_LOW_CRITICAL,
        v >= VOLTAGE_LOW_CRITICAL_RECOVERY
    )
    if result:
        transitions.append(("Critical Low Voltage", result))

    # High voltage warning
    result = update_fault_flag(
        "High Voltage Warning",
        v >= VOLTAGE_HIGH_WARNING,
        v <= VOLTAGE_HIGH_RECOVERY
    )
    if result:
        transitions.append(("High Voltage Warning", result))

    # High voltage critical
    result = update_fault_flag(
        "Critical High Voltage",
        v >= VOLTAGE_HIGH_CRITICAL,
        v <= VOLTAGE_HIGH_CRITICAL_RECOVERY
    )
    if result:
        transitions.append(("Critical High Voltage", result))

    # Current warning
    result = update_fault_flag(
        "High Current Warning",
        i >= CURRENT_WARNING,
        i <= CURRENT_WARNING_RECOVERY
    )
    if result:
        transitions.append(("High Current Warning", result))

    # Current critical
    result = update_fault_flag(
        "Critical Overcurrent",
        i >= CURRENT_CRITICAL,
        i <= CURRENT_CRITICAL_RECOVERY
    )
    if result:
        transitions.append(("Critical Overcurrent", result))

    # Heating rate warning
    result = update_fault_flag(
        "Rapid Temperature Rise",
        st.session_state.heating_rate >= 5.0,
        st.session_state.heating_rate <= 2.0
    )
    if result:
        transitions.append(("Rapid Temperature Rise", result))

    # Record transitions
    for fault_name, state in transitions:
        if state == "activated":
            add_event(
                fault_name,
                "Warning",
                "Fault detected",
                "Protection logic activated"
            )
        elif state == "recovered":
            add_event(
                fault_name,
                "Recovery",
                "Fault cleared",
                "Recovery threshold satisfied"
            )

    return transitions

# ============================================================
# 8. FAULT SEVERITY PRIORITY
# ============================================================

CRITICAL_FAULTS = [
    "Critical Temperature",
    "Critical Low Voltage",
    "Critical High Voltage",
    "Critical Overcurrent",
]

WARNING_FAULTS = [
    "High Temperature Warning",
    "Low Voltage Warning",
    "High Voltage Warning",
    "High Current Warning",
    "Rapid Temperature Rise",
]


def get_system_severity():
    active = st.session_state.fault_flags

    critical_active = [f for f in CRITICAL_FAULTS if active.get(f, False)]
    warning_active = [f for f in WARNING_FAULTS if active.get(f, False)]

    # Critical always has the highest priority
    if critical_active:
        return "CRITICAL", critical_active

    if warning_active:
        return "WARNING", warning_active

    return "NORMAL", []


def get_protection_action(requested_current):
    """
    Protection logic and controlled load recovery.

    Critical:
        Load is set to zero.

    Warning:
        Load is reduced to 50%.

    Normal:
        Current can recover gradually, limited by LOAD_RESTORE_STEP_A
        per simulation step.
    """
    severity, active_faults = get_system_severity()

    previous_effective = st.session_state.effective_current
    recovery_active = False

    if severity == "CRITICAL":
        effective_current = 0.0
        action = "CRITICAL SHUTDOWN — LOAD DISABLED"

        st.session_state.recovery_mode = False

    elif severity == "WARNING":
        effective_current = requested_current * WARNING_LOAD_FACTOR
        action = "WARNING — LOAD REDUCED"

        st.session_state.recovery_mode = False

    else:
        # Gradual restoration toward requested load
        delta = requested_current - previous_effective

        if abs(delta) > LOAD_RESTORE_STEP_A:
            effective_current = previous_effective + \
                np.sign(delta) * LOAD_RESTORE_STEP_A
            recovery_active = True
        else:
            effective_current = requested_current

        if recovery_active:
            action = "NORMAL — CONTROLLED LOAD RESTORATION"
            st.session_state.recovery_mode = True
        else:
            action = "NORMAL OPERATION"
            st.session_state.recovery_mode = False

    st.session_state.effective_current = float(effective_current)

    st.session_state.safety_action = action

    return severity, active_faults, effective_current, action

# ============================================================
# 9. GAUGE CREATION
# ============================================================

def make_gauge(title, value, minimum, maximum, unit, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": unit, "font": {"color": "#eaf2ff"}},
        title={"text": title, "font": {"color": "#eaf2ff"}},
        gauge={
            "axis": {
                "range": [minimum, maximum],
                "tickfont": {"color": "#9fb0c8"}
            },
            "bar": {"color": color},
            "bgcolor": "#162236",
            "borderwidth": 1,
            "bordercolor": "#26364e",
        }
    ))

    fig.update_layout(
        height=260,
        paper_bgcolor="#0b1120",
        font_color="#eaf2ff",
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig


# ============================================================
# 10. LINE CHART FUNCTION
# ============================================================

def make_line_chart(data, x, y, title, ylabel):
    if data.empty:
        st.info("Data will appear after the simulation begins.")
        return

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=data[x],
        y=data[y],
        mode="lines",
        name=y,
        line=dict(width=2)
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title=ylabel,
        paper_bgcolor="#0b1120",
        plot_bgcolor="#111a2b",
        font_color="#eaf2ff",
        height=350,
        margin=dict(l=40, r=20, t=50, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 11. DASHBOARD HEADER
# ============================================================

st.title("🔋 Smart EV Battery Management System")
st.caption("Version 4.3 | Intelligent Protection & Fault Recovery")

st.markdown("""
<div class="small-info">
Software-based EV battery simulation. Values are model-generated
or manually entered for testing; they are not real battery measurements.
</div>
""", unsafe_allow_html=True)

st.divider()

# ============================================================
# 12. SIDEBAR CONTROLS
# ============================================================

st.sidebar.title("⚙️ Simulation Controls")

mode = st.sidebar.radio(
    "Operating Mode",
    ["Automatic Simulation", "Manual Fault Testing"],
    key="mode_selector"
)

st.session_state.system_mode = mode

capacity = st.sidebar.number_input(
    "Battery Capacity (Ah)",
    min_value=1.0,
    max_value=100.0,
    value=float(st.session_state.capacity_ah),
    step=1.0
)

st.session_state.capacity_ah = capacity

if mode == "Automatic Simulation":
    scenario = st.sidebar.selectbox(
        "Simulation Scenario",
        [
            "Idle",
            "Driving - Low Load",
            "Driving - High Load",
            "Charging"
        ]
    )

    scenario_current = {
        "Idle": 0.0,
        "Driving - Low Load": 5.0,
        "Driving - High Load": 15.0,
        "Charging": -5.0
    }

    requested_current = scenario_current[scenario]

else:
    st.sidebar.caption("Manually set battery parameters to test faults.")

    manual_voltage = st.sidebar.slider(
        "Pack Voltage (V)",
        float(PACK_MIN_V),
        float(PACK_MAX_V),
        float(np.clip(st.session_state.voltage, PACK_MIN_V, PACK_MAX_V)),
        0.1
    )

    manual_current = st.sidebar.slider(
        "Requested Current (A)",
        -30.0,
        30.0,
        float(np.clip(st.session_state.requested_current, -30.0, 30.0)),
        0.5
    )

    manual_temperature = st.sidebar.slider(
        "Battery Temperature (°C)",
        15.0,
        70.0,
        float(np.clip(st.session_state.temperature, 15.0, 70.0)),
        0.5
    )

    requested_current = manual_current

    st.sidebar.info(
        "Press Advance Simulation to apply the selected values "
        "for one 10-second test step."
    )

advance_manual = False

if mode == "Manual Fault Testing":
    advance_manual = st.sidebar.button(
        "▶ Advance Manual Simulation (10 sec)",
        use_container_width=True
    )

if st.sidebar.button("🔄 Reset Simulation", use_container_width=True):
    reset_simulation()
    st.rerun()

# ============================================================
# 13. SIMULATION UPDATE
# ============================================================

def simulation_step(requested_current, elapsed_seconds):
    """
    A simulation step:
    1. Apply requested operating condition.
    2. Update voltage based on SOC and current.
    3. Evaluate fault conditions.
    4. Apply safety logic.
    5. Update SOC, thermal behavior, energy and history.
    """

    old_temp = st.session_state.temperature

    st.session_state.requested_current = float(requested_current)

    # Preliminary voltage estimate
    st.session_state.voltage = calculate_voltage(
        st.session_state.soc,
        requested_current
    )

    # Estimate heating from requested current
    estimated_temp = calculate_temperature(
        old_temp,
        requested_current,
        elapsed_seconds
    )

    st.session_state.temperature = estimated_temp

    # Heating rate
    temp_delta = estimated_temp - old_temp

    if elapsed_seconds > 0:
        st.session_state.heating_rate = \
            (temp_delta / elapsed_seconds) * 60.0
    else:
        st.session_state.heating_rate = 0.0

    # Cooling power estimate
    st.session_state.cooling_power = max(
        0.0,
        COOLING_COEFF * (estimated_temp - AMBIENT_TEMP)
    )

    st.session_state.peak_temperature = max(
        st.session_state.peak_temperature,
        estimated_temp
    )

    # Update voltage with new SOC after this step
    # Initial protection evaluation uses current voltage and temperature
    update_protection()

    severity, active_faults, effective_current, action = \
        get_protection_action(requested_current)

    # Update SOC using protected current
    st.session_state.soc = calculate_soc(
        st.session_state.soc,
        effective_current,
        elapsed_seconds,
        st.session_state.capacity_ah
    )

    # Recalculate terminal voltage based on SOC and effective current
    st.session_state.voltage = calculate_voltage(
        st.session_state.soc,
        effective_current
    )

    # Re-evaluate protection with final voltage
    update_protection()

    # Signed current:
    # positive = discharge; negative = charge
    st.session_state.current = effective_current

    power = st.session_state.voltage * effective_current

    if power >= 0:
        st.session_state.discharged_energy_wh += \
            power * elapsed_seconds / 3600.0
    else:
        st.session_state.charged_energy_wh += \
            abs(power) * elapsed_seconds / 3600.0

    st.session_state.simulation_elapsed += elapsed_seconds

    # Thermal state label
    if st.session_state.fault_flags.get("Critical Temperature", False):
        st.session_state.thermal_state = "Critical"
    elif st.session_state.fault_flags.get("High Temperature Warning", False):
        st.session_state.thermal_state = "Warning"
    else:
        st.session_state.thermal_state = "Normal"

    # Record history
    add_performance_record()
    add_thermal_record()

# ============================================================
# 14. AUTOMATIC AND MANUAL MODE EXECUTION
# ============================================================

if mode == "Automatic Simulation":
    st_autorefresh(interval=2000, key="auto_refresh")

    simulation_step(
        requested_current,
        SIMULATION_STEP_SECONDS
    )

elif mode == "Manual Fault Testing" and advance_manual:
    # Use the selected manual values for a 10-second test
    st.session_state.voltage = manual_voltage
    st.session_state.temperature = manual_temperature
    st.session_state.requested_current = manual_current

    old_temp = st.session_state.temperature

    # Manual mode uses entered voltage and temperature as test inputs.
    st.session_state.heating_rate = 0.0

    st.session_state.cooling_power = max(
        0.0,
        COOLING_COEFF * (manual_temperature - AMBIENT_TEMP)
    )

    st.session_state.peak_temperature = max(
        st.session_state.peak_temperature,
        manual_temperature
    )

    update_protection()

    severity, faults, effective_current, action = \
        get_protection_action(manual_current)

    st.session_state.current = effective_current

    st.session_state.soc = calculate_soc(
        st.session_state.soc,
        effective_current,
        10.0,
        st.session_state.capacity_ah
    )

    # Preserve the manually selected voltage for this test step
    st.session_state.voltage = manual_voltage

    power = manual_voltage * effective_current

    if power >= 0:
        st.session_state.discharged_energy_wh += power * 10.0 / 3600.0
    else:
        st.session_state.charged_energy_wh += abs(power) * 10.0 / 3600.0

    st.session_state.simulation_elapsed += 10

    if st.session_state.fault_flags.get("Critical Temperature", False):
        st.session_state.thermal_state = "Critical"
    elif st.session_state.fault_flags.get("High Temperature Warning", False):
        st.session_state.thermal_state = "Warning"
    else:
        st.session_state.thermal_state = "Normal"

    add_performance_record()
    add_thermal_record()

# ============================================================
# 15. FAULT STATUS AND SYSTEM PRIORITY
# ============================================================

severity, active_faults = get_system_severity()

if severity == "CRITICAL":
    st.markdown(
        '<div class="status-critical">🚨 CRITICAL — PROTECTION ACTIVE</div>',
        unsafe_allow_html=True
    )
elif severity == "WARNING":
    st.markdown(
        '<div class="status-warning">⚠️ WARNING — LOAD REDUCTION ACTIVE</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown(
        '<div class="status-normal">✅ NORMAL — SYSTEM OPERATING</div>',
        unsafe_allow_html=True
    )

if active_faults:
    st.error("Active fault(s): " + ", ".join(active_faults))
else:
    st.success("No active faults detected.")

st.info(f"**Safety action:** {st.session_state.safety_action}")

if st.session_state.recovery_mode:
    st.warning(
        "Recovery mode: the simulated battery load is being restored gradually."
    )

# ============================================================
# 16. BATTERY OVERVIEW METRICS
# ============================================================

st.header("📊 Battery Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("State of Charge", f"{st.session_state.soc:.1f}%")
c2.metric("Pack Voltage", f"{st.session_state.voltage:.2f} V")
c3.metric("Battery Current", f"{st.session_state.current:.2f} A")
c4.metric("Temperature", f"{st.session_state.temperature:.2f} °C")

c5, c6, c7, c8 = st.columns(4

```python
)

c5.metric("Requested Current", f"{st.session_state.requested_current:.2f} A")
c6.metric("Effective Current", f"{st.session_state.effective_current:.2f} A")
c7.metric("Peak Temperature", f"{st.session_state.peak_temperature:.2f} °C")
c8.metric("Heating Rate", f"{st.session_state.heating_rate:.2f} °C/min")

# ============================================================
# 17. BATTERY GAUGES
# ============================================================

st.header("🎛️ Battery Parameter Gauges")

g1, g2, g3 = st.columns(3)

with g1:
    st.plotly_chart(
        make_gauge(
            "Voltage",
            st.session_state.voltage,
            PACK_MIN_V,
            PACK_MAX_V,
            " V",
            "#38bdf8"
        ),
        use_container_width=True
    )

with g2:
    st.plotly_chart(
        make_gauge(
            "Current Magnitude",
            abs(st.session_state.current),
            0,
            30,
            " A",
            "#a78bfa"
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
            " °C",
            "#fb923c"
        ),
        use_container_width=True
    )

# ============================================================
# 18. STATE OF CHARGE AND CAPACITY ANALYSIS
# ============================================================

st.header("🔋 Battery Capacity Analysis")

soc_col1, soc_col2 = st.columns([1, 1])

with soc_col1:
    soc_fig = go.Figure(go.Pie(
        labels=["Remaining", "Used"],
        values=[
            st.session_state.soc,
            100 - st.session_state.soc
        ],
        hole=0.65,
        marker=dict(colors=["#38bdf8", "#263449"]),
        textinfo="label+percent"
    ))

    soc_fig.update_layout(
        title="Battery SoC",
        paper_bgcolor="#0b1120",
        font_color="#eaf2ff",
        height=300,
        annotations=[{
            "text": f"{st.session_state.soc:.1f}%",
            "showarrow": False,
            "font": {"size": 25, "color": "#eaf2ff"}
        }]
    )

    st.plotly_chart(soc_fig, use_container_width=True)

with soc_col2:
    remaining_capacity = (
        st.session_state.capacity_ah * st.session_state.soc / 100.0
    )

    used_capacity = (
        st.session_state.capacity_ah - remaining_capacity
    )

    st.metric("Rated Capacity", f"{st.session_state.capacity_ah:.2f} Ah")
    st.metric("Remaining Capacity", f"{remaining_capacity:.2f} Ah")
    st.metric("Consumed Capacity", f"{used_capacity:.2f} Ah")

    st.caption(
        "SoC is estimated by coulomb counting from the initial "
        "SoC and simulated current."
    )

    st.caption(
        "SoH is not calculated. Actual SoH requires capacity-test "
        "or validated battery data."
    )

# ============================================================
# 19. POWER AND ENERGY ANALYSIS
# ============================================================

st.header("⚡ Power & Energy Analysis")

power = st.session_state.voltage * st.session_state.current

p1, p2, p3 = st.columns(3)

p1.metric("Instantaneous Power", f"{power:.2f} W")
p2.metric("Energy Discharged", f"{st.session_state.discharged_energy_wh:.3f} Wh")
p3.metric("Energy Charged", f"{st.session_state.charged_energy_wh:.3f} Wh")

st.caption(
    "Positive power indicates discharge. Negative power indicates charging."
)

# ============================================================
# 20. THERMAL MANAGEMENT
# ============================================================

st.header("🌡️ Advanced Thermal Management")

t1, t2, t3, t4 = st.columns(4)

t1.metric("Thermal State", st.session_state.thermal_state)
t2.metric("Peak Temperature", f"{st.session_state.peak_temperature:.2f} °C")
t3.metric("Heating Rate", f"{st.session_state.heating_rate:.2f} °C/min")
t4.metric("Estimated Cooling Power", f"{st.session_state.cooling_power:.2f} W")

st.caption(
    "Cooling power is a modeled estimate of heat removal, "
    "not a measured cooling-system output."
)

# ============================================================
# 21. PROTECTION LOGIC DISPLAY
# ============================================================

st.header("🛡️ Intelligent Protection System")

protection_table = pd.DataFrame([
    {
        "Protection": "Low Voltage Warning",
        "Trigger": f"≤ {VOLTAGE_LOW_WARNING:.1f} V",
        "Recovery": f"≥ {VOLTAGE_LOW_RECOVERY:.1f} V",
        "Action": "Load reduction"
    },
    {
        "Protection": "Critical Low Voltage",
        "Trigger": f"≤ {VOLTAGE_LOW_CRITICAL:.1f} V",
        "Recovery": f"≥ {VOLTAGE_LOW_CRITICAL_RECOVERY:.1f} V",
        "Action": "Load shutdown"
    },
    {
        "Protection": "High Voltage Warning",
        "Trigger": f"≥ {VOLTAGE_HIGH_WARNING:.1f} V",
        "Recovery": f"≤ {VOLTAGE_HIGH_RECOVERY:.1f} V",
        "Action": "Load reduction"
    },
    {
        "Protection": "Critical High Voltage",
        "Trigger": f"≥ {VOLTAGE_HIGH_CRITICAL:.1f} V",
        "Recovery": f"≤ {VOLTAGE_HIGH_CRITICAL_RECOVERY:.1f} V",
        "Action": "Load shutdown"
    },
    {
        "Protection": "High Current Warning",
        "Trigger": f"≥ {CURRENT_WARNING:.1f} A",
        "Recovery": f"≤ {CURRENT_WARNING_RECOVERY:.1f} A",
        "Action": "Load reduction"
    },
    {
        "Protection": "Critical Overcurrent",
        "Trigger": f"≥ {CURRENT_CRITICAL:.1f} A",
        "Recovery": f"≤ {CURRENT_CRITICAL_RECOVERY:.1f} A",
        "Action": "Load shutdown"
    },
    {
        "Protection": "Temperature Warning",
        "Trigger": f"≥ {TEMP_WARNING:.1f} °C",
        "Recovery": f"≤ {TEMP_WARNING_RECOVERY:.1f} °C",
        "Action": "Load reduction"
    },
    {
        "Protection": "Critical Temperature",
        "Trigger": f"≥ {TEMP_CRITICAL:.1f} °C",
        "Recovery": f"≤ {TEMP_CRITICAL_RECOVERY:.1f} °C",
        "Action": "Load shutdown"
    },
])

st.dataframe(protection_table, use_container_width=True, hide_index=True)

# ============================================================
# 22. PERFORMANCE GRAPHS
# ============================================================

st.header("📈 Battery Performance History")

performance_df = pd.DataFrame(st.session_state.performance_history)

if not performance_df.empty:

    voltage_chart, current_chart = st.columns(2)

    with voltage_chart:
        make_line_chart(
            performance_df,
            "Timestamp",
            "Voltage (V)",
            "Voltage Variation",
            "Voltage (V)"
        )

    with current_chart:
        make_line_chart(
            performance_df,
            "Timestamp",
            "Current (A)",
            "Current Variation",
            "Current (A)"
        )

    temp_chart, power_chart = st.columns(2)

    with temp_chart:
        make_line_chart(
            performance_df,
            "Timestamp",
            "Temperature (°C)",
            "Temperature Variation",
            "Temperature (°C)"
        )

    with power_chart:
        make_line_chart(
            performance_df,
            "Timestamp",
            "Power (W)",
            "Power Variation",
            "Power (W)"
        )

    soc_chart, load_chart = st.columns(2)

    with soc_chart:
        make_line_chart(
            performance_df,
            "Timestamp",
            "SoC (%)",
            "State of Charge Variation",
            "SoC (%)"
        )

    with load_chart:
        make_line_chart(
            performance_df,
            "Timestamp",
            "Effective Current (A)",
            "Protected Load Variation",
            "Effective Current (A)"
        )

else:
    st.info("Performance graphs will populate as the simulation runs.")

# ============================================================
# 23. THERMAL HISTORY GRAPHS
# ============================================================

st.header("🌡️ Thermal History & Analysis")

thermal_df = pd.DataFrame(st.session_state.thermal_history)

if not thermal_df.empty:

    th1, th2 = st.columns(2)

    with th1:
        make_line_chart(
            thermal_df,
            "Timestamp",
            "Temperature (°C)",
            "Thermal History",
            "Temperature (°C)"
        )

    with th2:
        make_line_chart(
            thermal_df,
            "Timestamp",
        "Heating Rate (°C/min)",
            "Heating / Cooling Rate",
            "°C/min"
        )

    th3, th4 = st.columns(2)

    with th3:
        make_line_chart(
            thermal_df,
            "Timestamp",
            "Cooling Power (W)",
            "Estimated Cooling Power",
            "Cooling Power (W)"
        )

    with th4:
        st.subheader("Thermal Safety State")

        state_counts = thermal_df["Thermal State"].value_counts()

        thermal_pie = go.Figure(go.Pie(
            labels=state_counts.index,
            values=state_counts.values,
            hole=0.5
        ))

        thermal_pie.update_layout(
            paper_bgcolor="#0b1120",
            font_color="#eaf2ff",
            height=320
        )

        st.plotly_chart(thermal_pie, use_container_width=True)

else:
    st.info("Thermal history will appear after simulation steps.")

# ============================================================
# 24. FAULT EVENT LOG
# ============================================================

st.header("📋 Fault Event & Recovery Log")

fault_df = pd.DataFrame(st.session_state.fault_history)

if not fault_df.empty:
    st.dataframe(
        fault_df,
        use_container_width=True,
        hide_index=True
    )

    fault_csv = fault_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download Fault & Recovery Log CSV",
        data=fault_csv,
        file_name="smart_bms_v4_3_fault_log.csv",
        mime="text/csv"
    )

else:
    st.info(
        "No fault transitions recorded yet. "
        "Test warning, critical and recovery conditions in Manual Fault Testing."
    )

# ============================================================
# 25. PERFORMANCE DATA EXPORT
# ============================================================

st.header("💾 Performance Data Export")

if not performance_df.empty:

    performance_csv = performance_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download Performance Data CSV",
        data=performance_csv,
        file_name="smart_bms_v4_3_performance.csv",
        mime="text/csv"
    )

if not thermal_df.empty:

    thermal_csv = thermal_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download Thermal History CSV",
        data=thermal_csv,
        file_name="smart_bms_v4_3_thermal_history.csv",
        mime="text/csv"
    )

# ============================================================
# 26. SYSTEM INFORMATION
# ============================================================

st.header("ℹ️ System Information")

info1, info2 = st.columns(2)

with info1:
    st.markdown("### Battery Configuration")
    st.write(f"- Battery type: Lithium-ion (modeled)")
    st.write(f"- Configuration: {PACK_SERIES}S{PACK_PARALLEL}P")
    st.write(f"- Nominal pack voltage: {PACK_NOMINAL_V:.1f} V")
    st.write(f"- Pack voltage range: {PACK_MIN_V:.1f}–{PACK_MAX_V:.1f} V")
    st.write(f"- Nominal capacity: {st.session_state.capacity_ah:.1f} Ah")
    st.write(f"- Internal resistance: {INTERNAL_RESISTANCE:.3f} Ω")

with info2:
    st.markdown("### Software Configuration")
    st.write("- Version: 4.3")
    st.write("- Mode: Software simulation")
    st.write("- SoC: Coulomb counting")
    st.write("- Voltage: Simplified OCV/internal resistance model")
    st.write("- Thermal: Simplified I²R heat/cooling model")
    st.write("- Protection: Thresholds + hysteresis")
    st.write("- Recovery: Controlled simulated load restoration")
    st.write("- Fault priority: Critical > Warning > Normal")

st.caption(
    "SoH is not implemented. No real battery measurements, "
    "sensor data or hardware contactor are connected. "
    "The model is intended for academic demonstration."
)

# ============================================================
# 27. FOOTER
# ============================================================

st.divider()

st.markdown("""
<div style="text-align:center; color:#8fa3bd;">
Smart EV Battery Management System — V4.3<br>
Intelligent Protection & Fault Recovery<br>
Academic Software Simulation Prototype
</div>
""", unsafe_allow_html=True)
