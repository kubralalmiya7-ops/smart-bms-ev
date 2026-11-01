import streamlit as st
import pandas as pd
import numpy as np

# -----------------------------------
# PAGE CONFIGURATION
# -----------------------------------

st.set_page_config(
    page_title="Smart BMS | Electric Vehicles",
    page_icon="🔋",
    layout="wide"
)

# -----------------------------------
# CUSTOM DASHBOARD DESIGN
# -----------------------------------

st.markdown("""
<style>

.stApp {
    background-color: #101923;
    color: #F2F5F8;
}

/* Main headings */
h1, h2, h3 {
    color: #FFFFFF !important;
}

/* General text visibility */
p, label, .stMarkdown {
    color: #EAF0F6;
}

/* Battery parameter numbers */
[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 30px !important;
    font-weight: bold !important;
}

/* Battery parameter labels */
[data-testid="stMetricLabel"] {
    color: #BFD0DF !important;
    font-size: 15px !important;
}

/* Metric cards */
[data-testid="stMetric"] {
    background-color: #1C2A38;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #40566B;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #172431;
}

/* Information boxes */
div[data-testid="stAlert"] {
    border-radius: 10px;
}

/* Captions */
.stCaption {
    color: #BFD0DF !important;
}

/* Slider text */
.stSlider label {
    color: #FFFFFF !important;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------------
# DASHBOARD TITLE
# -----------------------------------

st.title("🔋 SMART BATTERY MANAGEMENT SYSTEM")

st.caption(
    "Electric Vehicle Battery Monitoring and Safety Dashboard"
)

st.info(
    "DEMO MODE: All readings displayed are simulated. "
    "They are not measurements from a physical battery."
)

# -----------------------------------
# BATTERY OPERATING CONDITION SIMULATION
# -----------------------------------

st.sidebar.title("⚙️ Battery Simulation")

st.sidebar.write("Select an operating condition.")

scenario = st.sidebar.selectbox(
    "Select Battery Condition",
    [
        "Normal Condition",
        "Overvoltage",
        "Undervoltage",
        "Overcurrent",
        "Overtemperature",
        "Multiple Faults"
    ]
)

# Preset simulated battery readings

scenarios = {
    "Normal Condition": {
        "voltage": 48.2,
        "current": 5.4,
        "temperature": 29,
        "soc": 82
    },

    "Overvoltage": {
        "voltage": 56.5,
        "current": 5.4,
        "temperature": 29,
        "soc": 82
    },

    "Undervoltage": {
        "voltage": 38.5,
        "current": 5.4,
        "temperature": 29,
        "soc": 25
    },

    "Overcurrent": {
        "voltage": 48.2,
        "current": 27.0,
        "temperature": 29,
        "soc": 82
    },

    "Overtemperature": {
        "voltage": 48.2,
        "current": 5.4,
        "temperature": 58,
        "soc": 82
    },

    "Multiple Faults": {
        "voltage": 57.0,
        "current": 28.0,
        "temperature": 58,
        "soc": 18
    }
}

# Load the selected scenario

selected_data = scenarios[scenario]

voltage = selected_data["voltage"]
current = selected_data["current"]
temperature = selected_data["temperature"]
soc = selected_data["soc"]

st.sidebar.success("Selected: " + scenario)

# -----------------------------------
# SAFETY MONITORING LOGIC
# -----------------------------------

alerts = []

if voltage < 42:
    alerts.append("Undervoltage detected!")

if voltage > 54:
    alerts.append("Overvoltage detected!")

if current > 20:
    alerts.append("Overcurrent detected!")

if temperature > 45:
    alerts.append("High battery temperature detected!")

if (
    temperature >= 55
    or voltage < 40
    or voltage > 56
    or current >= 25
):
    battery_status = "CRITICAL"

elif alerts:
    battery_status = "WARNING"

else:
    battery_status = "NORMAL"

# -----------------------------------
# BATTERY OVERVIEW
# -----------------------------------

st.divider()

st.subheader("🔋 Battery Overview")

col1, col2 = st.columns([1, 2])
# BATTERY CHARGE DISPLAY

with col1:

    st.markdown("### Battery Charge")

    st.markdown(
        f"<h1 style='color:#25C987; font-size:48px;'>{soc}%</h1>",
        unsafe_allow_html=True
    )

    st.progress(soc / 100)

    st.caption("State of Charge (SoC)")

    if soc >= 70:
        st.success("Battery charge level: High")
    elif soc >= 30:
        st.warning("Battery charge level: Moderate")
    else:
        st.error("Battery charge level: Low")

# BATTERY PARAMETERS

with col2:

    st.markdown("### Battery Parameters")

    a, b, c = st.columns(3)

    a.metric(
        "Voltage",
        f"{voltage:.1f} V"
    )

    b.metric(
        "Current",
        f"{current:.1f} A"
    )

    c.metric(
        "Temperature",
        f"{temperature} °C"
    )

    st.markdown("### Overall Battery Condition")

    if battery_status == "CRITICAL":

        st.error(
            "🔴 CRITICAL — Immediate attention required"
        )

    elif battery_status == "WARNING":

        st.warning(
            "🟠 WARNING — Abnormal battery condition"
        )

    else:

        st.success(
            "🟢 NORMAL — Parameters within demo limits"
        )

# -----------------------------------
# SAFETY MONITORING
# -----------------------------------

st.divider()

st.subheader("🛡️ Battery Safety Monitoring")

if alerts:

    for alert in alerts:
        st.error("⚠️ " + alert)

else:

    st.success(
        "✅ No abnormal conditions detected."
    )

# -----------------------------------
# BATTERY PARAMETER ANALYSIS
# -----------------------------------

st.divider()

st.subheader("📊 Battery Parameter Analysis")

time = np.arange(1, 21)

voltage_data = voltage + np.sin(time / 2) * 0.5

current_data = current + np.cos(time / 3) * 0.7

temperature_data = temperature + np.sin(time / 4) * 2

graph_data = pd.DataFrame({
    "Voltage (V)": voltage_data,
    "Current (A)": current_data,
    "Temperature (°C)": temperature_data
}, index=time)

graph_data.index.name = "Simulation Step"

st.markdown("**Voltage Variation**")

st.line_chart(
    graph_data[["Voltage (V)"]]
)

st.markdown("**Current Variation**")

st.line_chart(
    graph_data[["Current (A)"]]
)

st.markdown("**Temperature Variation**")

st.line_chart(
    graph_data[["Temperature (°C)"]]
)

# -----------------------------------
# SYSTEM INFORMATION
# -----------------------------------

st.divider()

st.subheader("💻 System Information")

info1, info2, info3 = st.columns(3)

info1.metric(
    "Monitoring Mode",
    "Simulation"
)

info2.metric(
    "Battery Status",
    battery_status
)

info3.metric(
    "Safety Alerts",
    len(alerts)
)

# -----------------------------------
# FOOTER
# -----------------------------------

st.divider()

st.caption(
    "Smart BMS Project | Software Prototype | Version 1.1"
)

st.caption(
    "Note: Demo thresholds are illustrative only. "
    "They are not validated battery protection limits."
)
