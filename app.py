import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Smart EV Battery Management System",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# 2. PROFESSIONAL DASHBOARD STYLE
# =========================================================

st.markdown("""
<style>
.stApp {
    background: #0B1120;
    color: #E5E7EB;
}
[data-testid="stSidebar"] {
    background: #111827;
}
.block-container {
    max-width: 1500px;
    padding-top: 1.5rem;
}
h1, h2, h3, h4 {
    color: #F8FAFC !important;
}
p, label, span {
    color: #D1D5DB;
}
[data-testid="stMetric"] {
    background: #172235;
    border: 1px solid #29384D;
    border-radius: 12px;
    padding: 14px;
}
[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}
[data-testid="stMetricLabel"] {
    color: #CBD5E1 !important;
}
hr {
    border-color: #29384D;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# 3. BATTERY MODEL SPECIFICATIONS
# =========================================================

N_SERIES = 13
N_PARALLEL = 4

CELL_NOMINAL_VOLTAGE = 3.6
CELL_MIN_VOLTAGE = 3.0
CELL_MAX_VOLTAGE = 4.2

NOMINAL_VOLTAGE = N_SERIES * CELL_NOMINAL_VOLTAGE
MIN_PACK_VOLTAGE = N_SERIES * CELL_MIN_VOLTAGE
MAX_PACK_VOLTAGE = N_SERIES * CELL_MAX_VOLTAGE

DEFAULT_CAPACITY_AH = 10.0

# Illustrative pack-level internal resistance.
# Replace with a measured or datasheet value when available.
PACK_RESISTANCE = 0.08

# Simulation thermal model parameters.
THERMAL_CAPACITY = 500.0
COOLING_COEFFICIENT = 1.5
AMBIENT_TEMPERATURE = 25.0

# Demonstration protection thresholds.
VOLTAGE_WARNING_LOW = 42.0
VOLTAGE_WARNING_HIGH = 53.0
CURRENT_WARNING = 20.0
TEMPERATURE_WARNING = 45.0

VOLTAGE_CRITICAL_LOW = MIN_PACK_VOLTAGE
VOLTAGE_CRITICAL_HIGH = MAX_PACK_VOLTAGE
CURRENT_CRITICAL = 25.0
TEMPERATURE_CRITICAL = 55.0

TIME_STEP = 2.0  # seconds

# =========================================================
# 4. SESSION STATE INITIALIZATION
# =========================================================

defaults = {
    "soc": 82.0,
    "temperature": 29.0,
    "voltage": 48.2,
    "sim_seconds": 0.0,
    "history": [],
    "fault_history": [],
    "last_faults": [],
    "simulation_started": False,
    "capacity_ah": DEFAULT_CAPACITY_AH,
    "initial_soc": 82.0
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =========================================================
# 5. BATTERY MATHEMATICAL MODEL
# =========================================================

def calculate_ocv(soc):
    """
    Simplified illustrative 13S lithium-ion
    open-circuit voltage curve.

    This is not a substitute for a cell manufacturer's
    voltage-versus-SoC discharge curve.
    """

    soc_points = np.array(
        [0, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
        dtype=float
    )

    cell_voltage_points = np.array(
        [3.00, 3.25, 3.45, 3.55, 3.62, 3.67,
         3.72, 3.78, 3.85, 3.95, 4.08, 4.15, 4.20],
        dtype=float
    )

    cell_ocv = np.interp(
        np.clip(soc, 0, 100),
        soc_points,
        cell_voltage_points
    )

    return cell_ocv * N_SERIES


def calculate_soc(previous_soc, current, elapsed_seconds, capacity):
    """
    Coulomb counting.

    Positive current = discharging.
    Negative current = charging.
    """

    if capacity <= 0:
        return previous_soc

    consumed_ah = current * elapsed_seconds / 3600.0

    new_soc = previous_soc - (
        consumed_ah / capacity
    ) * 100.0

    return float(np.clip(new_soc, 0, 100))


def calculate_terminal_voltage(soc, current):
    """
    Simplified terminal voltage model:
    Terminal voltage = OCV - I*R

    Positive current means discharge.
    """

    ocv = calculate_ocv(soc)

    terminal_voltage = (
        ocv - current * PACK_RESISTANCE
    )

    return float(
        np.clip(
            terminal_voltage,
            0,
            MAX_PACK_VOLTAGE + 2
        )
    )


def calculate_temperature(previous_temp, current, elapsed_seconds):
    """
    Simplified thermal model:
    Heat generation = I^2 * R
    Cooling depends on difference from ambient temperature.
    """

    heat_generation = (
        current ** 2
    ) * PACK_RESISTANCE

    heat_loss = (
        COOLING_COEFFICIENT
        * (previous_temp - AMBIENT_TEMPERATURE)
    )

    temperature_change = (
        (heat_generation - heat_loss)
        * elapsed_seconds
        / THERMAL_CAPACITY
    )

    return float(
        np.clip(
            previous_temp + temperature_change,
            AMBIENT_TEMPERATURE,
            100
        )
    )


# =========================================================
# 6. FAULT DETECTION
# =========================================================

def detect_faults(voltage, current, temperature):

    faults = []

    if voltage > VOLTAGE_CRITICAL_HIGH:
        faults.append({
            "parameter": "Voltage",
            "message": "Overvoltage detected",
            "severity": "CRITICAL",
            "value": voltage
        })

    elif voltage < VOLTAGE_CRITICAL_LOW:
        faults.append({
            "parameter": "Voltage",
            "message": "Undervoltage detected",
            "severity": "CRITICAL",
            "value": voltage
        })

    elif voltage > VOLTAGE_WARNING_HIGH:
        faults.append({
            "parameter": "Voltage",
            "message": "High voltage warning",
            "severity": "WARNING",
            "value": voltage
        })

    elif voltage < VOLTAGE_WARNING_LOW:
        faults.append({
            "parameter": "Voltage",
            "message": "Low voltage warning",
            "severity": "WARNING",
            "value": voltage
        })

    if abs(current) > CURRENT_CRITICAL:
        faults.append({
            "parameter": "Current",
            "message": "Critical overcurrent detected",
            "severity": "CRITICAL",
            "value": current
        })

    elif abs(current) > CURRENT_WARNING:
        faults.append({
            "parameter": "Current",
            "message": "High current warning",
            "severity": "WARNING",
            "value": current
        })

    if temperature >= TEMPERATURE_CRITICAL:
        faults.append({
            "parameter": "Temperature",
            "message": "Critical overtemperature detected",
            "severity": "CRITICAL",
            "value": temperature
        })

    elif temperature >= TEMPERATURE_WARNING:
        faults.append({
            "parameter": "Temperature",
            "message": "High temperature warning",
            "severity": "WARNING",
            "value": temperature
        })

    return faults


# =========================================================
# 7. GAUGE CREATION
# =========================================================

def create_gauge(title, value, unit, minimum, maximum,
                 warning_low=None, warning_high=None,
                 critical_low=None, critical_high=None):

    warning_low = minimum if warning_low is None else warning_low
    warning_high = maximum if warning_high is None else warning_high
    critical_low = minimum if critical_low is None else critical_low
    critical_high = maximum if critical_high is None else critical_high

    if value < critical_low or value > critical_high:
        color = "#EF4444"
    elif value < warning_low or value > warning_high:
        color = "#F59E0B"
    else:
        color = "#22C55E"

    display_value = float(
        np.clip(value, minimum, maximum)
    )

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=display_value,
            number={
                "suffix": f" {unit}",
                "font": {"size": 27, "color": "white"}
            },
            title={
                "text": title,
                "font": {"size": 16, "color": "#CBD5E1"}
            },
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [minimum, maximum],
                    "tickcolor": "#94A3B8"
                },
                "bar": {
                    "color": color,
                    "thickness": 0.27
                },
                "bgcolor": "#172235",
                "borderwidth": 0,
                "steps": [{
                    "range": [minimum, maximum],
                    "color": "#263449"
                }]
            }
        )
    )

    fig.update_layout(
        height=245,
        margin=dict(l=25, r=25, t=55, b=5),
        paper_bgcolor="#111827",
        font={"color": "white"}
    )

    return fig


# =========================================================
# 8. HEADER
# =========================================================

st.markdown("""
<h1 style="text-align:center;color:#38BDF8;">
SMART EV BATTERY MANAGEMENT SYSTEM
</h1>
<p style="text-align:center;color:#94A3B8;">
Intelligent Monitoring | Battery Analytics | Fault Detection
</p>
""", unsafe_allow_html=True)

st.info(
    "VERSION 4.0 | Simulation prototype. "
    "No physical battery or Arduino is connected yet."
)

# =========================================================
# 9. SIDEBAR CONTROLS
# =========================================================

st.sidebar.title("BATTERY CONTROL PANEL")

mode = st.sidebar.radio(
    "Operating Mode",
    ["Automatic Simulation", "Manual Fault Testing"]
)

capacity = st.sidebar.number_input(
    "Rated Battery Capacity (Ah)",
    min_value=1.0,
    max_value=100.0,
    value=float(st.session_state.capacity_ah),
    step=1.0
)

if capacity != st.session_state.capacity_ah:
    st.session_state.capacity_ah = capacity

if st.sidebar.button("Reset Battery Simulation", use_container_width=True):
    st.session_state.soc = st.session_state.initial_soc
    st.session_state.temperature = 29.0
    st.session_state.voltage = calculate_terminal_voltage(
        st.session_state.soc, 0
    )
    st.session_state.sim_seconds = 0.0
    st.session_state.history = []
    st.session_state.fault_history = []
    st.session_state.last_faults = []
    st.rerun()

st.sidebar.divider()

# =========================================================
# 10. AUTOMATIC OR MANUAL OPERATION
# =========================================================

if mode == "Automatic Simulation":

    st.sidebar.subheader("Automatic Battery Operation")

    operation = st.sidebar.selectbox(
        "Select operating condition",
        [
            "Idle",
            "Driving - Low Load",
            "Driving - High Load",
            "Charging"
        ]
    )

    automatic_run = st.sidebar.toggle(
        "Start Automatic Simulation",
        value=False
    )

    if operation == "Idle":
        operating_current = 0.0

    elif operation == "Driving - Low Load":
        operating_current = 5.0

    elif operation == "Driving - High Load":
        operating_current = 15.0

    else:
        operating_current = -5.0

    if automatic_run:
        st_autorefresh(
            interval=2000,
            limit=None,
            key="battery_auto_refresh"
        )

    if automatic_run:
        st.session_state.soc = calculate_soc(
            st.session_state.soc,
            operating_current,
            TIME_STEP,
            capacity
        )

        st.session_state.temperature = calculate_temperature(
            st.session_state.temperature,
            operating_current,
            TIME_STEP
        )

        st.session_state.voltage = calculate_terminal_voltage(
            st.session_state.soc,
            operating_current
        )

        st.session_state.sim_seconds += TIME_STEP

    voltage = st.session_state.voltage
    current = operating_current
    temperature = st.session_state.temperature
    soc = st.session_state.soc

    st.sidebar.caption(
        "Automatic mode advances the simulated battery every 2 seconds."
    )

else:

    st.sidebar.subheader("Manual Fault Testing")

    manual_voltage = st.sidebar.slider(
        "Battery Voltage (V)",
        min_value=0.0,
        max_value=60.0,
        value=float(
            np.clip(st.session_state.voltage, 0, 60)
        ),
        step=0.5
    )

    manual_current = st.sidebar.slider(
        "Battery Current (A)",
        min_value=-30.0,
        max_value=35.0,
        value=5.0,
        step=0.5,
        help="Positive = discharge; negative = charging."
    )

    manual_temperature = st.sidebar.slider(
        "Battery Temperature (°C)",
        min_value=0.0,
        max_value=80.0,
        value=float(
            np.clip(st.session_state.temperature, 0, 80)
        ),
        step=1.0
    )

    voltage = manual_voltage
    current = manual_current
    temperature = manual_temperature

    soc = st.session_state.soc

    st.sidebar.caption(
        "Manual mode changes the displayed sensor readings "
        "for fault testing. It does not represent a physical battery."
    )

# =========================================================
# 11. UPDATE SOC IN MANUAL MODE
# =========================================================

if mode == "Manual Fault Testing":

    if st.button("Advance Manual Simulation by 10 Seconds"):

        st.session_state.soc = calculate_soc(
            st.session_state.soc,
            current,
            10.0,
            capacity
        )

        st.session_state.sim_seconds += 10.0

        st.session_state.temperature = temperature
        st.session_state.voltage = voltage

        st.rerun()

# =========================================================
# 12. BATTERY CALCULATIONS
# =========================================================

remaining_ah = capacity * soc / 100.0
consumed_ah = capacity - remaining_ah

nominal_energy_wh = NOMINAL_VOLTAGE * capacity
remaining_energy_wh = nominal_energy_wh * soc / 100.0

if current > 0:
    operating_status = "DISCHARGING"
elif current < 0:
    operating_status = "CHARGING"
else:
    operating_status = "IDLE"

# =========================================================
# 13. FAULT STATUS AND EVENT HISTORY
# =========================================================

faults = detect_faults(
    voltage,
    current,
    temperature
)

fault_names = [
    f["message"] for f in faults
]

for fault in faults:
    event_key = (
        fault["parameter"],
        fault["message"]
    )

    if event_key not in st.session_state.last_faults:

        st.session_state.fault_history.append({
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Parameter": fault["parameter"],
            "Event": fault["message"],
            "Severity": fault["severity"],
            "Value": round(fault["value"], 2)
        })

st.session_state.last_faults = [
    (f["parameter"], f["message"]) for f in faults
]

if any(f["severity"] == "CRITICAL" for f in faults):
    system_status = "CRITICAL FAULT"
    system_color = "#EF4444"

elif faults:
    system_status = "WARNING"
    system_color = "#F59E0B"

else:
    system_status = "NORMAL"
    system_color = "#22C55E"

# =========================================================
# 14. SAVE PERFORMANCE HISTORY
# =========================================================

if mode == "Automatic Simulation" and automatic_run:

    if (
        not st.session_state.history
        or st.session_state.history[-1]["Time (s)"]
        != st.session_state.sim_seconds
    ):
        st.session_state.history.append({
            "Time (s)": st.session_state.sim_seconds,
            "Voltage (V)": voltage,
            "Current (A)": current,
            "Temperature (°C)": temperature,
            "SoC (%)": soc
        })

elif mode == "Manual Fault Testing":

    if st.button("Record Manual Reading"):

        st.session_state.history.append({
            "Time (s)": st.session_state.sim_seconds,
            "Voltage (V)": voltage,
            "Current (A)": current,
            "Temperature (°C)": temperature,
            "SoC (%)": soc
        })

# Keep only the latest 150 readings.
st.session_state.history = st.session_state.history[-150:]
st.session_state.fault_history = st.session_state.fault_history[-100:]

# =========================================================
# 15. SYSTEM STATUS
# =========================================================

st.markdown("### SYSTEM STATUS")

st.markdown(
    f"""
    <div style="
        background:#172235;
        border:1px solid {system_color};
        border-left:6px solid {system_color};
        padding:18px;
        border-radius:12px;
        text-align:center;
    ">
        <h2 style="color:{system_color};margin:0;">
            {system_status}
        </h2>
        <p style="margin:5px 0;">
            Operating Mode: {mode}
            &nbsp; | &nbsp;
            Battery Condition: {operating_status}
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# =========================================================
# 16. BATTERY GAUGES
# =========================================================

st.markdown("### LIVE BATTERY PARAMETERS")

g1, g2, g3 = st.columns(3)

with g1:
    st.plotly_chart(
        create_gauge(
            "BATTERY VOLTAGE",
            voltage,
            "V",
            0,
            60,
            VOLTAGE_WARNING_LOW,
            VOLTAGE_WARNING_HIGH,
            VOLTAGE_CRITICAL_LOW,
            VOLTAGE_CRITICAL_HIGH
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

with g2:
    st.plotly_chart(
        create_gauge(
            "BATTERY CURRENT",
            abs(current),
            "A",
            0,
            35,
            0,
            CURRENT_WARNING,
            0,
            CURRENT_CRITICAL
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

with g3:
    st.plotly_chart(
        create_gauge(
            "BATTERY TEMPERATURE",
            temperature,
            "°C",
            0,
            80,
            0,
            TEMPERATURE_WARNING,
            0,
            TEMPERATURE_CRITICAL
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

st.divider()

# =========================================================
# 17. STATE OF CHARGE AND CAPACITY
# =========================================================

st.markdown("### BATTERY CAPACITY ANALYSIS")

c1, c2 = st.columns([1, 2])

with c1:

    soc_fig = go.Figure(
        go.Pie(
            values=[soc, 100 - soc],
            hole=0.75,
            marker={
                "colors": ["#22C55E", "#263449"]
            },
            textinfo="none"
        )
    )

    soc_fig.update_layout(
        height=250,
        showlegend=False,
        paper_bgcolor="#0B1120",
        margin=dict(l=5, r=5, t=5, b=5),
        annotations=[{
            "text": f"<b>{soc:.1f}%</b><br>SoC",
            "showarrow": False,
            "font": {"size": 25, "color": "white"}
        }]
    )

    st.plotly_chart(
        soc_fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )

with c2:

    st.metric("Rated Capacity", f"{capacity:.2f} Ah")
    st.metric("Remaining Capacity", f"{remaining_ah:.2f} Ah")
    st.metric("Consumed Capacity", f"{consumed_ah:.2f} Ah")
    st.metric("Estimated Remaining Energy", f"{remaining_energy_wh:.1f} Wh")

    st.progress(soc / 100.0)

    st.caption(
        f"Nominal energy reference: {nominal_energy_wh:.1f} Wh"
    )

# =========================================================
# 18. PERFORMANCE GRAPHS
# ====================================================
