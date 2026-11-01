import streamlit as st
import pandas as pd
import numpy as np

# -----------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------

st.set_page_config(
    page_title="Smart BMS | Electric Vehicles",
    page_icon="🔋",
    layout="wide"
)

# -----------------------------------------
# 2. CUSTOM DASHBOARD DESIGN
# -----------------------------------------

st.markdown("""
<style>
.stApp {
    background-color: #101923;
    color: #F2F5F8;
}
[data-testid="stMetric"] {
    background-color: #1C2A38;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #304354;
}
h1, h2, h3 {
    color: #F2F5F8;
}
div[data-testid="stSidebar"] {
    background-color: #172431;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------
# 3. PROJECT HEADER
# -----------------------------------------

st.title("🔋 SMART BATTERY MANAGEMENT SYSTEM")
st.caption("Electric Vehicle Battery Monitoring and Safety Dashboard")

st.info(
    "DEMO MODE: All readings shown here are simulated, "
    "not measurements from a physical battery."
)

# -----------------------------------------
# 4. SIMULATED BATTERY INPUTS
# -----------------------------------------

st.sidebar.title("⚙️ Battery Simulation")
st.sidebar.write("Adjust the values to test the dashboard.")

voltage = st.sidebar.slider(
    "Battery Voltage (V)", 35.0, 60.0, 48.2, 0.1
)

current = st.sidebar.slider(
    "Battery Current (A)", 0.0, 35.0, 5.4, 0.1
)

temperature = st.sidebar.slider(
    "Battery Temperature (°C)", 10, 70, 29
)

soc = st.sidebar.slider(
    "Battery State of Charge (%)", 0, 100, 82
)

# -----------------------------------------
# 5. BATTERY SAFETY CONDITIONS
# -----------------------------------------
# Illustrative limits for a demo 48 V system.
# Actual limits must come from battery specifications.

alerts = []

if voltage < 42:
    alerts.append("Undervoltage detected!")

if voltage > 54:
    alerts.append("Overvoltage detected!")

if current > 20:
    alerts.append("Overcurrent detected!")

if temperature > 45:
    alerts.append("High battery temperature detected!")

if temperature >= 55 or voltage < 40 or voltage > 56 or current >= 25:
    battery_status = "CRITICAL"
elif alerts:
    battery_status = "WARNING"
else:
    battery_status = "NORMAL"

# -----------------------------------------
# 6. BATTERY STATUS
# -----------------------------------------

st.subheader("Battery Overview")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### Battery Charge")

    st.markdown(f"""
    <div style="background:#1C2A38; padding:25px;
                border-radius:15px; text-align:center;">
        <div style="display:flex; justify-content:center;
                    align-items:center; gap:5px;">
            <div style="width:190px; height:75px;
                        border:4px solid #DCE5ED;
                        border-radius:12px; padding:5px;">
                <div style="height:100%; width:{soc}%;
                            background:#25C987; border-radius:5px;">
                </div>
            </div>
            <div style="width:10px; height:27px;
                        background:#DCE5ED; border-radius:3px;">
            </div>
        </div>
        <h1 style="color:#25C987; margin-top:15px;">
            {soc}%
        </h1>
        <p style="color:#AAB9C7;">State of Charge (SoC)</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("### Battery Parameters")

    a, b, c = st.columns(3)

    a.metric("Voltage", f"{voltage:.1f} V")
    b.metric("Current", f"{current:.1f} A")
    c.metric("Temperature", f"{temperature} °C")

    st.markdown("### Overall Battery Condition")

    if battery_status == "CRITICAL":
        st.error("🔴 CRITICAL — Immediate attention required")
    elif battery_status == "WARNING":
        st.warning("🟠 WARNING — Abnormal battery condition")
    else:
        st.success("🟢 NORMAL — Parameters within demo limits")

# -----------------------------------------
# 7. SAFETY ALERTS
# -----------------------------------------

st.divider()
st.subheader("🛡️ Battery Safety Monitoring")

if alerts:
    for alert in alerts:
        st.error("⚠️ " + alert)
else:
    st.success("No abnormal conditions detected.")

# -----------------------------------------
# 8. BATTERY PARAMETER GRAPHS
# -----------------------------------------

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
st.line_chart(graph_data[["Voltage (V)"]])

st.markdown("**Current Variation**")
st.line_chart(graph_data[["Current (A)"]])

st.markdown("**Temperature Variation**")
st.line_chart(graph_data[["Temperature (°C)"]])

# -----------------------------------------
# 9. SYSTEM INFORMATION
# -----------------------------------------

st.divider()
st.subheader("System Information")

info1, info2, info3 = st.columns(3)

info1.metric("Monitoring Mode", "Simulation")
info2.metric("Battery Status", battery_status)
info3.metric("Safety Alerts", len(alerts))

st.caption(
    "Smart BMS Project | Software Prototype | Version 1.0"
)
/* Make battery readings clearly visible */
[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}

[data-testid="stMetricLabel"] {
    color: #D6E2EF !important;
}

[data-testid="stMetricDelta"] {
    color: #25C987 !important;
}

/* Improve general text visibility */
.stMarkdown, .stText, label, p {
    color: #EAF0F6;
}
/* Make battery readings clearly visible */
[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}

[data-testid="stMetricLabel"] {
    color: #D6E2EF !important;
}

[data-testid="stMetricDelta"] {
    color: #25C987 !important;
}

/* Improve general text visibility */
.stMarkdown, .stText, label, p {
    color: #EAF0F6;
}
/* Make battery readings clearly visible */
[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}

[data-testid="stMetricLabel"] {
    color: #D6E2EF !important;
}

[data-testid="stMetricDelta"] {
    color: #25C987 !important;
}

/* Improve general text visibility */
.stMarkdown, .stText, label, p {
    color: #EAF0F6;
}
