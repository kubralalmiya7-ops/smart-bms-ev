import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Smart BMS | EV Dashboard",
    page_icon="🔋",
    layout="wide"
)

# ==========================================
# CUSTOM CSS
# ==========================================

st.markdown("""
<style>

.stApp {
    background: #0B1420;
    color: #EAF2F8;
}

header {
    background: transparent !important;
}

h1, h2, h3, p, label {
    color: #EAF2F8 !important;
}

[data-testid="stSidebar"] {
    background: #111F2D;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

[data-testid="stMetric"] {
    background: #172838;
    padding: 16px;
    border-radius: 12px;
    border: 1px solid #2B4357;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 25px !important;
    font-weight: bold;
}

[data-testid="stMetricLabel"] {
    color: #B9CDDD !important;
}

div[data-testid="stAlert"] {
    border-radius: 12px;
}

hr {
    border-color: #2B4357;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# BATTERY SIMULATION DATA
# ==========================================

scenarios = {
    "Normal Condition": [48.2, 5.4, 29, 82],
    "Overvoltage": [56.5, 5.4, 29, 82],
    "Undervoltage": [38.5, 5.4, 29, 25],
    "Overcurrent": [48.2, 27.0, 29, 82],
    "Overtemperature": [48.2, 5.4, 58, 82],
    "Multiple Faults": [57.0, 28.0, 58, 18]
}


# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.title("🔋 SMART BMS")

st.sidebar.caption("Battery simulation control")

scenario = st.sidebar.selectbox(
    "Select Operating Condition",
    list(scenarios.keys())
)

voltage, current, temperature, soc = scenarios[scenario]

st.sidebar.divider()

st.sidebar.markdown("### Battery Information")
st.sidebar.write("Battery Type: Lithium-ion")
st.sidebar.write("Nominal Voltage: 48 V")
st.sidebar.write("Monitoring: Simulated")
st.sidebar.write("System: EV Battery")

st.sidebar.info(
    "Select a condition to observe changes "
    "in battery parameters and safety alerts."
)


# ==========================================
# FAULT DETECTION
# ==========================================

alerts = []

if voltage < 42:
    alerts.append("Undervoltage detected")

if voltage > 54:
    alerts.append("Overvoltage detected")

if current > 20:
    alerts.append("Overcurrent detected")

if temperature > 45:
    alerts.append("Overtemperature detected")

if (
    temperature >= 55
    or voltage < 40
    or voltage > 56
    or current >= 25
):
    status = "CRITICAL"
elif alerts:
    status = "WARNING"
else:
    status = "NORMAL"


# ==========================================
# HEADER
# ==========================================

st.markdown(
    "<h1 style='margin-bottom:0;'>🔋 SMART BATTERY MANAGEMENT SYSTEM</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<p style='color:#8FAFC6 !important;'>"
    "Electric Vehicle Battery Monitoring & Safety Control Centre"
    "</p>",
    unsafe_allow_html=True
)

left, right = st.columns([3, 1])

with left:
    st.caption("BATTERY MONITORING DASHBOARD")

with right:
    if status == "NORMAL":
        st.success("● SYSTEM NORMAL")
    elif status == "WARNING":
        st.warning("● SYSTEM WARNING")
    else:
        st.error("● CRITICAL ALERT")

st.info(
    "SIMULATION MODE — All displayed readings are simulated "
    "and are not obtained from a physical battery."
)

st.divider()


# ==========================================
# TOP BATTERY INDICATORS
# ==========================================

st.subheader("⚡ Battery Performance Indicators")

g1, g2, g3 = st.columns(3)

# Voltage Gauge

with g1:
    st.markdown("### Voltage")
    st.metric(
        "Battery Voltage",
        f"{voltage:.1f} V",
        help="Illustrative voltage reading"
    )

    st.progress(
        min(max(voltage / 60, 0.0), 1.0),
        text="Voltage level"
    )

# Current Gauge

with g2:
    st.markdown("### Current")
    st.metric(
        "Battery Current",
        f"{current:.1f} A",
        help="Illustrative current reading"
    )

    st.progress(
        min(max(current / 35, 0.0), 1.0),
        text="Current level"
    )

# Temperature Gauge

with g3:
    st.markdown("### Temperature")
    st.metric(
        "Battery Temperature",
        f"{temperature} °C",
        help="Illustrative temperature reading"
    )

    st.progress(
        min(max(temperature / 70, 0.0), 1.0),
        text="Temperature level"
    )


st.divider()


# ==========================================
# BATTERY CHARGE AND HEALTH
# ==========================================

st.subheader("🔋 Battery Status Overview")

b1, b2 = st.columns([1, 2])

with b1:

    st.markdown("### State of Charge")

    st.markdown(
        f"""
        <div style="
            background:#172838;
            border:1px solid #2B4357;
            padding:22px;
            border-radius:15px;
            text-align:center;
        ">
        <div style="
            font-size:46px;
            font-weight:bold;
            color:#25C987;
        ">
        {soc}%
        </div>
        <div style="color:#B9CDDD;">
        BATTERY CHARGE
        </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.progress(soc / 100)

with b2:

    st.markdown("### Battery Operating Condition")

    st.metric("Operating Mode", scenario)

    if status == "NORMAL":
        st.success(
            "Battery is operating within the "
            "illustrative demo limits."
        )

    elif status == "WARNING":
        st.warning(
            "An abnormal battery parameter has been detected."
        )

    else:
        st.error(
            "Critical battery condition detected. "
            "Immediate attention is required."
        )


st.divider()


# ==========================================
# PERFORMANCE GRAPH
# ==========================================

st.subheader("📈 Battery Performance Analysis")

st.caption(
    "Illustrative parameter trends across simulation steps"
)

time = np.arange(1, 31)

voltage_data = voltage + np.sin(time / 3) * 0.7
current_data = current + np.cos(time / 4) * 1.0
temperature_data = temperature + np.sin(time / 5) * 2

chart_data = pd.DataFrame({
    "Voltage (V)": voltage_data,
    "Current (A)": current_data,
    "Temperature (°C)": temperature_data
})

st.line_chart(
    chart_data,
    x_label="Simulation Step",
    y_label="Parameter Value"
)


# ==========================================
# SAFETY MONITORING
# ==========================================

st.divider()

st.subheader("🛡️ Battery Safety Monitoring")

s1, s2 = st.columns([2, 1])

with s1:

    if alerts:

        for alert in alerts:
            st.error("⚠️ " + alert)

    else:

        st.success("✓ No abnormal conditions detected.")


with s2:

    st.metric("Detected Faults", len(alerts))

    st.metric("Safety Status", status)


# ==========================================
# SYSTEM INFORMATION
# ==========================================

st.divider()

st.subheader("💻 System Information")

i1, i2, i3, i4 = st.columns(4)

i1.metric("Battery Type", "Li-ion")
i2.metric("Nominal Voltage", "48 V")
i3.metric("Monitoring Mode", "Simulation")
i4.metric("Operating Status", status)


# ==========================================
# FOOTER
# ==========================================

st.divider()

st.caption(
    "SMART BMS | Electric Vehicle Battery Monitoring Project | Version 2.0"
)

st.caption(
    "Academic software prototype. Simulation values and "
    "thresholds are illustrative, not validated protection settings."
)
