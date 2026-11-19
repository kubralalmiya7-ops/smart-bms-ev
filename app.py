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
# 2. DASHBOARD STYLE
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
PACK_RESISTANCE = 0.08

# Thermal model assumptions (illustrative)
THERMAL_CAPACITY = 500.0       # J/°C
COOLING_COEFFICIENT = 1.5      # W/°C
AMBIENT_TEMPERATURE = 25.0      # °C

# Battery warning/critical thresholds (illustrative)
VOLTAGE_WARNING_LOW = 42.0
VOLTAGE_WARNING_HIGH = 53.0
CURRENT_WARNING = 20.0
TEMPERATURE_WARNING = 45.0

VOLTAGE_CRITICAL_LOW = MIN_PACK_VOLTAGE
VOLTAGE_CRITICAL_HIGH = MAX_PACK_VOLTAGE
CURRENT_CRITICAL = 25.0
TEMPERATURE_CRITICAL = 55.0

TIME_STEP = 2.0  # seconds

# Simulated thermal load-control factors
WARNING_LOAD_FACTOR = 0.50       # Reduce requested current to 50%
CRITICAL_DISCHARGE_LIMIT = 0.0   # Simulate discharge load shutdown
CRITICAL_CHARGE_LIMIT = 0.0      # Simulate charging shutdown

# =========================================================
# 4. SESSION STATE
# =========================================================

defaults = {
    "soc": 82.0,
    "temperature": 29.0,
    "voltage": 48.2,
    "sim_seconds": 0.0,
    "history": [],
    "thermal_history": [],
    "fault_history": [],
    "last_faults": [],
    "capacity_ah": DEFAULT_CAPACITY_AH,
    "initial_soc": 82.0,
    "discharged_energy_wh": 0.0,
    "charged_energy_wh": 0.0,
    "peak_temperature": 29.0,
    "heating_rate": 0.0,
    "cooling_power_w": 0.0,
    "thermal_state": "NORMAL",
    "safety_action": "None",
    "last_effective_current": 0.0,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =========================================================
# 5. BATTERY MATHEMATICAL MODEL
# =========================================================

def calculate_ocv(soc):
    """Illustrative cell OCV vs SoC curve for a 13S pack."""

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

    return float(cell_ocv * N_SERIES)


def calculate_soc(previous_soc, current, elapsed_seconds, capacity):
    """Coulomb counting. Positive current means discharging."""

    if capacity <= 0:
        return float(previous_soc)

    consumed_ah = current * elapsed_seconds / 3600.0

    new_soc = previous_soc - (consumed_ah / capacity) * 100.0

    return float(np.clip(new_soc, 0, 100))


def calculate_terminal_voltage(soc, current):
    """Terminal voltage approximation: OCV - I*R."""

    ocv = calculate_ocv(soc)
    terminal_voltage = ocv - current * PACK_RESISTANCE

    return float(
        np.clip(terminal_voltage, 0, MAX_PACK_VOLTAGE + 2)
    )


def calculate_temperature(previous_temp, current, elapsed_seconds):
    """
    Lumped thermal model:
    I²R heating minus ambient cooling.
    """

    heat_generation = (current ** 2) * PACK_RESISTANCE

    heat_loss = COOLING_COEFFICIENT * (
        previous_temp - AMBIENT_TEMPERATURE
    )

    temperature_change = (
        (heat_generation - heat_loss)
        * elapsed_seconds
        / THERMAL_CAPACITY
    )

    new_temp = previous_temp + temperature_change

    return float(np.clip(new_temp, AMBIENT_TEMPERATURE, 100.0))


def calculate_cooling_power(temperature):
    """Estimated heat removal to ambient in watts."""

    return max(
        0.0,
        COOLING_COEFFICIENT
        * (temperature - AMBIENT_TEMPERATURE)
    )


def calculate_heating_rate(previous_temp, new_temp, elapsed_seconds):
    """Temperature rate in °C/min."""

    if elapsed_seconds <= 0:
        return 0.0

    return (new_temp - previous_temp) * 60.0 / elapsed_seconds


def accumulate_energy(voltage, current, elapsed_seconds):
    """Accumulate charge/discharge energy in Wh."""

    power_w = voltage * current
    energy_wh = power_w * elapsed_seconds / 3600.0

    if power_w > 0:
        st.session_state.discharged_energy_wh += energy_wh

    elif power_w < 0:
        st.session_state.charged_energy_wh += abs(energy_wh)

    return power_w


# =========================================================
# 6. THERMAL SAFETY AND SIMULATED LOAD REDUCTION
# =========================================================

def get_thermal_state(temperature):
    if temperature >= TEMPERATURE_CRITICAL:
        return "CRITICAL"
    elif temperature >= TEMPERATURE_WARNING:
        return "WARNING"
    return "NORMAL"


def apply_thermal_safety(requested_current, temperature):
    """
    Simulated safety control:
    Normal: requested current unchanged.
    Warning: current reduced to 50%.
    Critical: simulated charge/discharge current set to zero.

    This is a software demonstration, not real battery protection.
    """

    thermal_state = get_thermal_state(temperature)

    if thermal_state == "CRITICAL":

        if requested_current > 0:
            effective_current = CRITICAL_DISCHARGE_LIMIT
            action = "Critical temperature: simulated discharge shutdown"

        elif requested_current < 0:
            effective_current = CRITICAL_CHARGE_LIMIT
            action = "Critical temperature: simulated charging shutdown"

        else:
            effective_current = 0.0
            action = "Critical temperature: load remains off"

    elif thermal_state == "WARNING":

        effective_current = requested_current * WARNING_LOAD_FACTOR

        if requested_current > 0:
            action = "Warning temperature: simulated discharge load reduced"

        elif requested_current < 0:
            action = "Warning temperature: simulated charging current reduced"

        else:
            action = "Warning temperature: no load requested"

    else:

        effective_current = requested_current
        action = "Normal operation: no thermal load reduction"

    return float(effective_current), thermal_state, action


# =========================================================
# 7. FAULT DETECTION
# =========================================================

def detect_faults(voltage, current, temperature, heating_rate):

    faults = []

    # Voltage checks
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

    # Current checks
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

    # Temperature checks
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

    # Rapid temperature-rise warning (illustrative)
    if heating_rate >= 5.0:
        faults.append({
            "parameter": "Thermal Rate",
            "message": "Rapid temperature rise detected",
            "severity": "WARNING",
            "value": heating_rate
        })

    return faults


# =========================================================
# 8. GAUGE CREATION
# =========================================================

def create_gauge(
    title, value, unit, minimum, maximum,
    warning_low=None, warning_high=None,
    critical_low=None, critical_high=None
):

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

    display_value = float(np.clip(value, minimum, maximum))

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
# 9. LINE CHART
# =========================================================

def create_line_chart(
    df, x_column, y_column, title, y_label, line_color
):

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df[x_column],
            y=df[y_column],
            mode="lines+markers",
            line=dict(color=line_color, width=2),
            marker=dict(size=4),
            name=y_label
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Simulation Time (s)",
        yaxis_title=y_label,
        height=350,
        paper_bgcolor="#111827",
        plot_bgcolor="#172235",
        font=dict(color="#E5E7EB"),
        xaxis=dict(gridcolor="#29384D"),
        yaxis=dict(gridcolor="#29384D"),
        margin=dict(l=30, r=20, t=55, b=40)
    )

    return fig


# =========================================================
# 10. HEADER
# =========================================================

st.markdown("""
<h1 style="text-align:center;color:#38BDF8;">
SMART EV BATTERY MANAGEMENT SYSTEM
</h1>
<p style="text-align:center;color:#94A3B8;">
Intelligent Monitoring | Battery Analytics | Thermal Safety
</p>
""", unsafe_allow_html=True)

st.info(
    "VERSION 4.2 | Thermal Management & Safety Prototype | "
    "Simulated data only. No physical battery or Arduino is connected."
)

# =========================================================
# 11. SIDEBAR CONTROL PANEL
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

st.session_state.capacity_ah = capacity

if st.sidebar.button("Reset Battery Simulation", use_container_width=True):

    st.session_state.soc = st.session_state.initial_soc
    st.session_state.temperature = 29.0
    st.session_state.peak_temperature = 29.0
    st.session_state.voltage = calculate_terminal_voltage(
        st.session_state.soc, 0
    )
    st.session_state.sim_seconds = 0.0
    st.session_state.history = []
    st.session_state.thermal_history = []
    st.session_state.fault_history = []
    st.session_state.last_faults = []
    st.session_state.discharged_energy_wh = 0.0
    st.session_state.charged_energy_wh = 0.0
    st.session_state.heating_rate = 0.0
    st.session_state.cooling_power_w = 0.0
    st.session_state.thermal_state = "NORMAL"
    st.session_state.safety_action = "None"
    st.session_state.last_effective_current = 0.0

    st.rerun()

st.sidebar.divider()

# =========================================================
# 12. AUTOMATIC SIMULATION OR MANUAL TESTING
# =========================================================

automatic_run = False
requested_current = 0.0
effective_current = 0.0
manual_advance = False

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
        requested_current = 0.0

    elif operation == "Driving - Low Load":
        requested_current = 5.0

    elif operation == "Driving - High Load":
        requested_current = 15.0

    else:
        requested_current = -5.0

    # Apply safety action using the current battery temperature.
    effective_current, thermal_state, safety_action = apply_thermal_safety(
        requested_current,
        st.session_state.temperature
    )

    if automatic_run:

        st_autorefresh(
            interval=2000,
            limit=None,
            key="battery_auto_refresh"
        )

        previous_temp = st.session_state.temperature
        previous_soc = st.session_state.soc

        # Update SoC using the safety-adjusted current.
        st.session_state.soc = calculate_soc(
            previous_soc,
            effective_current,
            TIME_STEP,
            capacity
        )

        # Update temperature using the effective current.
        st.session_state.temperature = calculate_temperature(
            previous_temp,
            effective_current,
            TIME_STEP
        )

        st.session_state.heating_rate = calculate_heating_rate(
            previous_temp,
            st.session_state.temperature,
            TIME_STEP
        )

        st.session_state.peak_temperature = max(
            st.session_state.peak_temperature,
            st.session_state.temperature
        )

        st.session_state.cooling_power_w = calculate_cooling_power(
            st.session_state.temperature
        )

        st.session_state.voltage = calculate_terminal_voltage(
            st.session_state.soc,
            effective_current
        )

        # Track energy using safety-adjusted current.
        accumulate_energy(
            st.session_state.voltage,
            effective_current,
            TIME_STEP
        )

        st.session_state.sim_seconds += TIME_STEP

        st.session_state.thermal_state = get_thermal_state(
            st.session_state.temperature
        )

        st.session_state.safety_action = safety_action
        st.session_state.last_effective_current = effective_current

        # Save history on each simulation step.
        st.session_state.history.append({
            "Time (s)": st.session_state.sim_seconds,
            "Voltage (V)": st.session_state.voltage,
            "Requested Current (A)": requested_current,
            "Current (A)": effective_current,
            "Temperature (°C)": st.session_state.temperature,
            "SoC (%)": st.session_state.soc,
            "Power (W)": st.session_state.voltage * effective_current,
            "Heating Rate (°C/min)": st.session_state.heating_rate,
            "Cooling Power (W)": st.session_state.cooling_power_w,
            "Thermal State": st.session_state.thermal_state
        })

        st.session_state.thermal_history.append({
            "Time (s)": st.session_state.sim_seconds,
            "Temperature (°C)": st.session_state.temperature,
            "Heating Rate (°C/min)": st.session_state.heating_rate,
            "Cooling Power (W)": st.session_state.cooling_power_w,
            "Thermal State": st.session_state.thermal_state
        })

    voltage = st.session_state.voltage
    current = effective_current
    temperature = st.session_state.temperature
    soc = st.session_state.soc

    st.sidebar.caption(
        "Automatic simulation updates every 2 seconds. "
        "Thermal safety may reduce simulated current."
    )

else:

    st.sidebar.subheader("Manual Fault Testing")

    manual_voltage = st.sidebar.slider(
        "Battery Voltage (V)",
        min_value=0.0,
        max_value=60.0,
        value=float(np.clip(st.session_state.voltage, 0, 60)),
        step=0.5
    )

    manual_current = st.sidebar.slider(
        "Requested Battery Current (A)",
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
        value=float(np.clip(st.session_state.temperature, 0, 80)),
        step=1.0
    )

    # Safety response is evaluated at the manually selected temperature.
    effective_current, thermal_state, safety_action = apply_thermal_safety(
        manual_current,
        manual_temperature
    )

    voltage = manual_voltage
    current = effective_current
    temperature = manual_temperature
    soc = st.session_state.soc

    st.sidebar.caption(
        "Manual values are used for fault testing. "
        "The safety logic can modify the requested current."
    )

    manual_advance = st.sidebar.button(
        "Advance Manual Simulation by 10 Seconds"
    )

    if manual_advance:

        previous_temp = st.session_state.temperature
        previous_soc = st.session_state.soc

        st.session_state.soc = calculate_soc(
            previous_soc,
            effective_current,
            10.0,
            capacity
        )

        st.session_state.temperature = manual_temperature

        st.session_state.heating_rate = calculate_heating_rate(
            previous_temp,
            manual_temperature,
            10.0
        )

        st.session_state.peak_temperature = max(
            st.session_state.peak_temperature,
            manual_temperature
        )

        st.session_state.cooling_power_w = calculate_cooling_power(
            manual_temperature
        )

        st.session_state.voltage = manual_voltage

        accumulate_energy(
            manual_voltage,
            effective_current,
            10.0
        )

        st.session_state.sim_seconds += 10.0

        st.session_state.thermal_state = get_thermal_state(
            manual_temperature
        )

        st.session_state.safety_action = safety_action
        st.session_state.last_effective_current = effective_current

        st.session_state.history.append({
            "Time (s)": st.session_state.sim_seconds,
            "Voltage (V)": manual_voltage,
            "Requested Current (A)": manual_current,
            "Current (A)": effective_current,
            "Temperature (°C)": manual_temperature,
            "SoC (%)": st.session_state.soc,
            "Power (W)": manual_voltage * effective_current,
            "Heating Rate (°C/min)": st.session_state.heating_rate,
            "Cooling Power (W)": st.session_state.cooling_power_w,
            "Thermal State": st.session_state.thermal_state
        })

        st.session_state.thermal_history.append({
            "Time (s)": st.session_state.sim_seconds,
            "Temperature (°C)": manual_temperature,
            "Heating Rate (°C/min)": st.session_state.heating_rate,
            "Cooling Power (W)": st.session_state.cooling_power_w,
            "Thermal State": st.session_state.thermal_state
        })

        st.rerun()

# =========================================================
# 13. BATTERY CALCULATIONS
# =========================================================

soc = st.session_state.soc

remaining_ah = capacity * soc / 100.0
consumed_ah = capacity - remaining_ah

nominal_energy_wh = NOMINAL_VOLTAGE * capacity
remaining_energy_wh = nominal_energy_wh * soc / 100.0

power_w = voltage * current

if current > 0:
    operating_status = "DISCHARGING"
elif current < 0:
    operating_status = "CHARGING"
else:
    operating_status = "IDLE"

thermal_state = get_thermal_state(temperature)

# =========================================================
# 14. FAULT STATUS AND HISTORY
# =========================================================

faults = detect_faults(
    voltage,
    current,
    temperature,
    st.session_state.heating_rate
)

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

# Keep histories within limits.
st.session_state.history = st.session_state.history[-150:]
st.session_state.thermal_history = st.session_state.thermal_history[-150:]
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

if faults:

    st.markdown("### ACTIVE BATTERY ALERTS")

    for fault in faults:

        if fault["severity"] == "CRITICAL":
            st.error(
                f"🔴 {fault['message']} | {fault['value']:.2f}"
            )
        else:
            st.warning(
                f"🟠 {fault['message']} | {fault['value']:.2f}"
            )

else:
    st.success("No active battery faults detected.")

# =========================================================
# 16. THERMAL SAFETY STATUS
# =========================================================

st.markdown("### THERMAL MANAGEMENT & SAFETY")

if thermal_state == "CRITICAL":
    thermal_color = "#EF4444"
    st.error("CRITICAL THERMAL STATE")

elif thermal_state == "WARNING":
    thermal_color = "#F59E0B"
    st.warning("THERMAL WARNING")

else:
    thermal_color = "#22C55E"
    st.success("THERMAL CONDITION NORMAL")

st.markdown(
    f"""
    <div style="
        background:#172235;
        border:1px solid {thermal_color};
        border-left:6px solid {thermal_color};
        padding:16px;
        border-radius:12px;
    ">
        <h3 style="color:{thermal_color};margin:0;">
            Thermal State: {thermal_state}
        </h3>
        <p style="margin:6px 0;">
            Safety Action: {safety_action}
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# =========================================================
# 17. BATTERY GAUGES
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
# 18. BATTERY CAPACITY AND SOC
# =========================================================

st.markdown("### BATTERY CAPACITY ANALYSIS")

c1, c2 = st.columns([1, 2])

with c1:

    soc_fig = go.Figure(
        go.Pie(
            values=[soc, 100 - soc],
            hole=0.75,
            marker={"colors": ["#22C55E", "#263449"]},
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
# 19. POWER AND ENERGY ANALYSIS
# =========================================================

st.markdown("### ELECTRICAL POWER AND ENERGY ANALYSIS")

p1, p2, p3 = st.columns(3)

p1.metric(
    "Instantaneous Power",
    f"{power_w:.2f} W",
    help="Positive = discharge; negative = charging."
)

p2.metric(
    "Energy Discharged",
    f"{st.session_state.discharged_energy_wh:.4f} Wh"
)

p3.metric(
    "Energy Received",
    f"{st.session_state.charged_energy_wh:.4f} Wh"
)

st.caption(
    "Energy counters accumulate during automatic simulation "
    "and manual advance steps."
)

# =========================================================
# 20. ADVANCED THERMAL ANALYSIS
# =========================================================

st.markdown("### ADVANCED THERMAL ANALYSIS")

t1, t2, t3, t4 = st.columns(4)

t1.metric(
    "Current Temperature",
    f"{temperature:.2f} °C"
)

t2.metric(
    "Peak Temperature",
    f"{st.session_state.peak_temperature:.2f} °C"
)

t3.metric(
    "Heating / Cooling Rate",
    f"{st.session_state.heating_rate:.2f} °C/min"
)

t4.metric(
    "Estimated Cooling Power",
    f"{st.session_state.cooling_power_w:.2f} W"
)

st.caption(
    "Positive heating rate indicates temperature rise. "
    "Negative rate indicates cooling. Cooling power is a simplified "
    "estimate of heat dissipation to ambient."
)

# =========================================================
# 21. PERFORMANCE GRAPHS
# =========================================================

st.markdown("### BATTERY PERFORMANCE GRAPHS")

if st.session_state.history:

    df = pd.DataFrame(st.session_state.history)

    # Voltage graph
    st.plotly_chart(
        create_line_chart(
            df,
            "Time (s)",
            "Voltage (V)",
            "Battery Voltage vs Time",
            "Voltage (V)",
            "#38BDF8"
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # Current graph
    st.plotly_chart(
        create_line_chart(
            df,
            "Time (s)",
            "Current (A)",
            "Battery Current vs Time",
            "Current (A)",
            "#F59E0B"
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # Temperature graph
    st.plotly_chart(
        create_line_chart(
            df,
            "Time (s)",
            "Temperature (°C)",
            "Battery Temperature vs Time",
            "Temperature (°C)",
            "#EF4444"
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # Power graph
    st.plotly_chart(
        create_line_chart(
            df,
            "Time (s)",
            "Power (W)",
            "Battery Power vs Time",
            "Power (W)",
            "#22C55E"
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

else:

    st.info(
        "Start automatic simulation or advance manual simulation "
        "to generate performance graphs."
    )

# =========================================================
# 22. THERMAL HISTORY GRAPH
# =========================================================

st.markdown("### THERMAL HISTORY AND COOLING")

if st.session_state.thermal_history:

    thermal_df = pd.DataFrame(st.session_state.thermal_history)

    # Temperature trend
    st.plotly_chart(
        create_line_chart(
            thermal_df,
            "Time (s)",
            "Temperature (°C)",
            "Thermal Behaviour vs Time",
            "Temperature (°C)",
            "#FB7185"
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # Heating/cooling rate
    st.plotly_chart(
        create_line_chart(
            thermal_df,
            "Time (s)",
            "Heating Rate (°C/min)",
            "Heating and Cooling Rate vs Time",
            "Rate (°C/min)",
            "#A78BFA"
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

    # Cooling power
    st.plotly_chart(
        create_line_chart(
            thermal_df,
            "Time (s)",
            "Cooling Power (W)",
            "Estimated Heat Dissipation vs Time",
            "Cooling Power (W)",
            "#06B6D4"
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

    st.dataframe(
        thermal_df.tail(10),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "Thermal history will appear as the simulation advances."
    )

# =========================================================
# 23. FAULT EVENT HISTORY
# =========================================================

st.markdown("### FAULT EVENT HISTORY")

if st.session_state.fault_history:

    fault_df = pd.DataFrame(st.session_state.fault_history)

    st.dataframe(
        fault_df,
        use_container_width=True,
        hide_index=True
    )

    fault_csv = fault_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Fault History CSV",
        data=fault_csv,
        file_name="smart_bms_fault_history.csv",
        mime="text/csv"
    )

else:

    st.info("No fault events have been recorded.")

# =========================================================
# 24. PERFORMANCE DATA EXPORT
# =========================================================

st.markdown("### PERFORMANCE DATA EXPORT")

if st.session_state.history:

    export_df = pd.DataFrame(st.session_state.history)

    st.dataframe(
        export_df.tail(10),
        use_container_width=True,
        hide_index=True
    )

    performance_csv = export_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Performance Data CSV",
        data=performance_csv,
        file_name="smart_bms_performance_data.csv",
        mime="text/csv"
    )

else:

    st.info("Performance readings will appear here once recorded.")

# =========================================================
# 25. SYSTEM INFORMATION
# =========================================================

st.markdown("### SYSTEM INFORMATION")

s1, s2, s3 = st.columns(3)

s1.metric("Battery Configuration", f"{N_SERIES}S{N_PARALLEL}P")
s2.metric("Nominal Pack Voltage", f"{NOMINAL_VOLTAGE:.1f} V")
s3.metric("Simulation Time", f"{st.session_state.sim_seconds:.0f} s")

st.markdown("""
**Battery Model:** Illustrative lithium-ion pack

**Configuration:** 13S4P

**Nominal Cell Voltage:** 3.6 V

**Cell Voltage Range:** 3.0–4.2 V

**Nominal Pack Voltage:** 46.8 V

**Rated Capacity:** User configurable (default 10 Ah)

**SoC Estimation:** Coulomb Counting

**Voltage Model:** Simplified OCV and internal resistance

**Thermal Model:** I²R heating and ambient cooling

**Thermal Safety:** Normal, warning and critical states

**Simulated Safety Action:** Load reduction during warning and load shutdown at critical temperature

**SoH:** Not calculated; requires measured capacity test data

**Data Source:** Mathematical simulation and manual test inputs

**Hardware Status:** Not connected

**Safety Disclaimer:** This is a software simulation prototype. Model parameters and thresholds are illustrative, not validated protection settings. The simulated load reduction does not physically disconnect a battery. Do not use this software as a real battery safety controller.
""")

# =========================================================
# 26. FOOTER
# =========================================================

st.divider()

st.markdown("""
<p style="text-align:center;color:#64748B;">
Smart EV Battery Management System | Version 4.2 |
Advanced Thermal Management & Battery Safety
</p>
""", unsafe_allow_html=True)
