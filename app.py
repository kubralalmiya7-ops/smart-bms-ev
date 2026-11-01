import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Smart BMS | EV Control Centre",
    page_icon="🔋",
    layout="wide"
)

# ==========================================
# PROFESSIONAL DASHBOARD CSS
# ==========================================

st.markdown("""
<style>
.stApp {
    background: #0A111C;
    color: #EAF2F8;
}

header {
    background: transparent !important;
}

.block-container {
    max-width: 1450px;
    padding-top: 2rem;
    padding-bottom: 2rem;
}

h1, h2, h3, h4, p, label {
    color: #EAF2F8 !important;
}

[data-testid="stSidebar"] {
    background: #111E2D;
}

[data-testid="stMetric"] {
    background: #172638;
    padding: 16px;
    border-radius: 12px;
    border: 1px solid #30465D;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}

[data-testid="stMetricLabel"] {
    color: #AFC3D6 !important;
}

div[data-testid="stAlert"] {
    border-radius: 10px;
}

hr {
    border-color: #26394D;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# SIMULATION SCENARIOS
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

st.sidebar.markdown("## 🔋 SMART BMS")
st.sidebar.caption("EV Battery Control Centre")

scenario = st.sidebar.selectbox(
    "Operating Condition",
    list(scenarios.keys())
)

voltage, current, temperature, soc = scenarios[scenario]

st.sidebar.divider()

st.sidebar.markdown("### Battery Configuration")
st.sidebar.write("Battery Chemistry: Lithium-ion")
st.sidebar.write("Nominal Voltage: 48 V")
st.sidebar.write("Monitoring Mode: Simulation")
st.sidebar.write("System: Electric Vehicle")

st.sidebar.info(
    "Change the operating condition to test "
    "different battery behaviours."
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

st.markdown("""
<h1 style="font-size:34px; margin-bottom:0;">
🔋 SMART BATTERY MANAGEMENT SYSTEM
</h1>
<p style="color:#8FAFC6 !important; font-size:16px;">
ELECTRIC VEHICLE | BATTERY MONITORING & SAFETY CONTROL CENTRE
</p>
""", unsafe_allow_html=True)

header1, header2 = st.columns([3, 1])

with header1:
    st.caption("BATTERY PERFORMANCE MONITORING")

with header2:
    if status == "NORMAL":
        st.success("● SYSTEM NORMAL")
    elif status == "WARNING":
        st.warning("● SYSTEM WARNING")
    else:
        st.error("● CRITICAL ALERT")

st.info(
    "SIMULATION MODE — All readings are simulated "
    "and are not measured from a physical battery."
)

st.divider()


# ==========================================
# CIRCULAR GAUGE FUNCTION
# ==========================================

def create_gauge(title, value, unit, maximum, warning, critical):

    if value >= critical or value < warning[0]:
        gauge_color = "#FF4B5C"
    elif value >= warning[1] or value < warning[0]:
        gauge_color = "#F5A623"
    else:
        gauge_color = "#24D6A0"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={
                "suffix": f" {unit}",
                "font": {
                    "size": 29,
                    "color": "#FFFFFF"
                }
            },
            title={
                "text": title,
                "font": {
                    "size": 19,
                    "color": "#D8E6F2"
                }
            },
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [0, maximum],
                    "tickcolor": "#AFC3D6",
                    "tickfont": {
                        "color": "#AFC3D6",
                        "size": 10
                    }
                },
                "bar": {
                    "color": gauge_color,
                    "thickness": 0.25
                },
                "bgcolor": "#172638",
                "borderwidth": 0,
                "steps": [
                    {
                        "range": [0, maximum],
                        "color": "#26394D"
                    }
                ],
                "threshold": {
                    "line": {
                        "color": "#FFFFFF",
                        "width": 3
                    },
                    "thickness": 0.8,
                    "value": value
                }
            }
        )
    )

    fig.update_layout(
        height=270,
        margin=dict(l=25, r=25, t=65, b=15),
        paper_bgcolor="#111E2D",
        font={"color": "#FFFFFF"}
    )

    return fig


# ==========================================
# THREE CIRCULAR GAUGES
# ==========================================

st.subheader("⚡ LIVE BATTERY PARAMETERS")

g1, g2, g3 = st.columns(3)

with g1:
    fig_voltage = create_gauge(
        "BATTERY VOLTAGE",
        voltage,
        "V",
        60,
        (42, 54),
        56
    )
    st.plotly_chart(
        fig_voltage,
        use_container_width=True,
        config={"displayModeBar": False}
    )

with g2:
    fig_current = create_gauge(
        "BATTERY CURRENT",
        current,
        "A",
        35,
        (0, 20),
        25
    )
    st.plotly_chart(
        fig_current,
        use_container_width=True,
        config={"displayModeBar": False}
    )

with g3:
    fig_temperature = create_gauge(
        "BATTERY TEMPERATURE",
        temperature,
        "°C",
        70,
        (0, 45),
        55
    )
    st.plotly_chart(
        fig_temperature,
        use_container_width=True,
        config={"displayModeBar": False}
    )


st.divider()


# ==========================================
# BATTERY CHARGE INDICATOR
# ==========================================

st.subheader("🔋 BATTERY CHARGE STATUS")

charge_col1, charge_col2 = st.columns([1, 2])

with charge_col1:

    charge_fig = go.Figure(
        go.Pie(
            values=[soc, 100 - soc],
            hole=0.78,
            marker={
                "colors": ["#24D6A0", "#26394D"]
            },
            textinfo="none",
            hoverinfo="skip",
            sort=False
        )
    )

    charge_fig.add_annotation(
        text=f"<b>{soc}%</b><br><span style='font-size:12px'>SoC</span>",
        showarrow=False,
        font={
            "size": 27,
            "color": "#FFFFFF"
        }
    )

    charge_fig.update_layout(
        height=220,
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#0A111C"
    )

    st.plotly_chart(
        charge_fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )

with charge_col2:

    st.markdown("### BATTERY CONDITION")

    if status == "NORMAL":
        st.success("NORMAL — Battery parameters within demo limits.")

    elif status == "WARNING":
        st.warning("WARNING — Abnormal battery parameter detected.")

    else:
        st.error("CRITICAL — Multiple or severe abnormal conditions detected.")

    st.metric("Selected Scenario", scenario)
    st.metric("Detected Faults", len(alerts))


st.divider()


# ==========================================
# SEPARATE PERFORMANCE GRAPHS
# ==========================================

st.subheader("📈 BATTERY PERFORMANCE ANALYSIS")

st.caption(
    "Simulated parameter variations across 30 simulation steps"
)

time = np.arange(1, 31)

voltage_data = voltage + np.sin(time / 3) * 0.7
current_data = current + np.cos(time / 4) * 1.0
temperature_data = temperature + np.sin(time / 5) * 2


# VOLTAGE GRAPH

st.markdown("### ⚡ Voltage Variation")

voltage_fig = go.Figure()

voltage_fig.add_trace(
    go.Scatter(
        x=time,
        y=voltage_data,
        mode="lines",
        name="Voltage",
        line={
            "color": "#36A2EB",
            "width": 3
        },
        fill="tozeroy",
        fillcolor="rgba(54,162,235,0.10)"
    )
)

voltage_fig.update_layout(
    height=280,
    paper_bgcolor="#111E2D",
    plot_bgcolor="#111E2D",
    font={"color": "#D8E6F2"},
    xaxis_title="Simulation Step",
    yaxis_title="Voltage (V)",
    margin=dict(l=20, r=20, t=20, b=20),
    hovermode="x unified"
)

st.plotly_chart(
    voltage_fig,
    use_container_width=True,
    config={"displayModeBar": False}
)


# CURRENT GRAPH

st.markdown("### ⚡ Current Variation")

current_fig = go.Figure()

current_fig.add_trace(
    go.Scatter(
        x=time,
        y=current_data,
        mode="lines",
        name="Current",
        line={
            "color": "#24D6A0",
            "width": 3
        },
        fill="tozeroy",
        fillcolor="rgba(36,214,160,0.10)"
    )
)

current_fig.update_layout(
    height=280,
    paper_bgcolor="#111E2D",
    plot_bgcolor="#111E2D",
    font={"color": "#D8E6F2"},
    xaxis_title="Simulation Step",
    yaxis_title="Current (A)",
    margin=dict(l=20, r=20, t=20, b=20),
    hovermode="x unified"
)

st.plotly_chart(
    current_fig,
    use_container_width=True,
    config={"displayModeBar": False}
)


# TEMPERATURE GRAPH

st.markdown("### 🌡️ Temperature Variation")

temperature_fig = go.Figure()

temperature_fig.add_trace(
    go.Scatter(
        x=time,
        y=temperature_data,
        mode="lines",
        name="Temperature",
        line={
            "color": "#FFAA45",
            "width": 3
        },
        fill="tozeroy",
        fillcolor="rgba(255,170,69,0.10)"
    )
)

temperature_fig.update_layout(
    height=280,
    paper_bgcolor="#111E2D",
    plot_bgcolor="#111E2D",
    font={"color": "#D8E6F2"},
    xaxis_title="Simulation Step",
    yaxis_title="Temperature (°C)",
    margin=dict(l=20, r=20, t=20, b=20),
    hovermode="x unified"
)

st.plotly_chart(
    temperature_fig,
    use_container_width=True,
    config={"displayModeBar": False}
)


st.divider()


# ==========================================
# SAFETY MONITORING
# ==========================================

st.subheader("🛡️ BATTERY SAFETY MONITORING")

safety1, safety2 = st.columns([2, 1])

with safety1:

    if alerts:
        for alert in alerts:
            st.error("⚠️ " + alert)
    else:
        st.success("✓ No abnormal conditions detected.")

with safety2:

    st.metric("Safety Status", status)
    st.metric("Total Faults", len(alerts))


# ==========================================
# SYSTEM INFORMATION
# ==========================================

st.divider()

st.subheader("💻 SYSTEM INFORMATION")

i1, i2, i3, i4 = st.columns(4)

i1.metric("Battery Type", "Lithium-ion")
i2.metric("Nominal Voltage", "48 V")
i3.metric("Monitoring Mode", "Simulation")
i4.metric("System Status", status)


# ==========================================
# FOOTER
# ==========================================

st.divider()

st.caption(
    "SMART BMS | EV Battery Monitoring & Safety System | Version 3.0"
)

st.caption(
    "Academic software prototype. Simulated readings and "
    "illustrative thresholds are not validated battery protection settings."
)
