import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Smart EV Battery Management System",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------
# PROFESSIONAL DARK THEME
# --------------------------------------------------

st.markdown("""
<style>
.stApp {
    background-color: #0B1120;
    color: #E5E7EB;
}

[data-testid="stSidebar"] {
    background-color: #111827;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1450px;
}

h1, h2, h3 {
    color: #F8FAFC !important;
}

p, label, span {
    color: #D1D5DB;
}

[data-testid="stMetric"] {
    background-color: #172235;
    border: 1px solid #29384D;
    padding: 16px;
    border-radius: 12px;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
}

[data-testid="stMetricLabel"] {
    color: #CBD5E1 !important;
}

div[data-testid="stPlotlyChart"] {
    background-color: transparent;
}

hr {
    border-color: #29384D;
}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.markdown("""
<h1 style="text-align:center; color:#38BDF8;">
    SMART EV BATTERY MANAGEMENT SYSTEM
</h1>
<p style="text-align:center; color:#94A3B8; font-size:16px;">
    Intelligent Battery Monitoring • Performance Analysis • Safety Alerts
</p>
""", unsafe_allow_html=True)

st.warning(
    "DEMO MODE: This dashboard currently uses simulated battery data. "
    "It is not connected to a physical battery or Arduino."
)

st.divider()


# --------------------------------------------------
# SIDEBAR - SIMULATION CONTROL
# --------------------------------------------------

st.sidebar.title("⚙️ Simulation Control")

scenario = st.sidebar.selectbox(
    "Select Battery Operating Condition",
    [
        "Normal Condition",
        "Overvoltage",
        "Undervoltage",
        "Overcurrent",
        "Overtemperature",
        "Multiple Faults"
    ]
)

st.sidebar.markdown("---")
st.sidebar.subheader("System Information")
st.sidebar.write("Battery Type: Lithium-ion (demo)")
st.sidebar.write("System: Smart EV BMS")
st.sidebar.write("Data Source: Simulated")
st.sidebar.write("Dashboard Version: 3.1")


# --------------------------------------------------
# SCENARIO DATA
# --------------------------------------------------

scenarios = {
    "Normal Condition": {
        "voltage": 48.2,
        "current": 5.4,
        "temperature": 29.0,
        "soc": 82
    },
    "Overvoltage": {
        "voltage": 56.5,
        "current": 5.4,
        "temperature": 29.0,
        "soc": 82
    },
    "Undervoltage": {
        "voltage": 38.5,
        "current": 5.4,
        "temperature": 29.0,
        "soc": 25
    },
    "Overcurrent": {
        "voltage": 48.2,
        "current": 27.0,
        "temperature": 29.0,
        "soc": 82
    },
    "Overtemperature": {
        "voltage": 48.2,
        "current": 5.4,
        "temperature": 58.0,
        "soc": 82
    },
    "Multiple Faults": {
        "voltage": 57.0,
        "current": 28.0,
        "temperature": 58.0,
        "soc": 18
    }
}

battery = scenarios[scenario]

voltage = battery["voltage"]
current = battery["current"]
temperature = battery["temperature"]
soc = battery["soc"]


# --------------------------------------------------
# SAFETY THRESHOLDS - DEMONSTRATION VALUES
# --------------------------------------------------

VOLTAGE_LOW = 42.0
VOLTAGE_HIGH = 54.0
CURRENT_HIGH = 20.0
TEMP_HIGH = 45.0

VOLTAGE_CRITICAL_LOW = 40.0
VOLTAGE_CRITICAL_HIGH = 56.0
CURRENT_CRITICAL = 25.0
TEMP_CRITICAL = 55.0


# --------------------------------------------------
# FAULT DETECTION
# --------------------------------------------------

alerts = []

if voltage > VOLTAGE_CRITICAL_HIGH:
    alerts.append("CRITICAL: Battery overvoltage detected.")
elif voltage > VOLTAGE_HIGH:
    alerts.append("WARNING: Battery voltage is above the normal range.")

if voltage < VOLTAGE_CRITICAL_LOW:
    alerts.append("CRITICAL: Battery undervoltage detected.")
elif voltage < VOLTAGE_LOW:
    alerts.append("WARNING: Battery voltage is below the normal range.")

if current > CURRENT_CRITICAL:
    alerts.append("CRITICAL: Excessive current detected.")
elif current > CURRENT_HIGH:
    alerts.append("WARNING: High current detected.")

if temperature > TEMP_CRITICAL:
    alerts.append("CRITICAL: Battery overtemperature detected.")
elif temperature > TEMP_HIGH:
    alerts.append("WARNING: Battery temperature is high.")

if alerts:
    overall_status = "FAULT DETECTED"
    status_color = "#EF4444"
elif scenario == "Normal Condition":
    overall_status = "NORMAL"
    status_color = "#22C55E"
else:
    overall_status = "NORMAL"
    status_color = "#22C55E"


# --------------------------------------------------
# OVERALL STATUS
# --------------------------------------------------

st.markdown("### SYSTEM STATUS")

st.markdown(
    f"""
    <div style="
        background-color:#172235;
        border:1px solid {status_color};
        border-left:6px solid {status_color};
        padding:18px;
        border-radius:12px;
        text-align:center;
        margin-bottom:20px;
    ">
        <h2 style="color:{status_color}; margin:0;">
            {overall_status}
        </h2>
        <p style="margin:5px 0 0 0;">
            Selected Scenario: {scenario}
        </p>
    </div>
    """,
    unsafe_allow_html=True
)


# --------------------------------------------------
# CIRCULAR GAUGE FUNCTION
# --------------------------------------------------

def create_gauge(title, value, unit, minimum, maximum,
                 warning_low=None, warning_high=None,
                 critical_low=None, critical_high=None):

    if critical_low is None:
        critical_low = minimum

    if critical_high is None:
        critical_high = maximum

    if warning_low is None:
        warning_low = minimum

    if warning_high is None:
        warning_high = maximum

    # Determine gauge colour
    if value < critical_low or value > critical_high:
        gauge_color = "#EF4444"
    elif value < warning_low or value > warning_high:
        gauge_color = "#F59E0B"
    else:
        gauge_color = "#22C55E"

    # Keep the displayed gauge value within its scale
    display_value = min(max(value, minimum), maximum)

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=display_value,
            number={
                "suffix": f" {unit}",
                "font": {
                    "size": 27,
                    "color": "#FFFFFF"
                }
            },
            title={
                "text": title,
                "font": {
                    "size": 17,
                    "color": "#CBD5E1"
                }
            },
            gauge={
                "shape": "angular",
                "axis": {
                    "range": [minimum, maximum],
                    "tickcolor": "#94A3B8",
                    "tickfont": {
                        "color": "#94A3B8",
                        "size": 10
                    }
                },
                "bar": {
                    "color": gauge_color,
                    "thickness": 0.28
                },
                "bgcolor": "#172235",
                "borderwidth": 0,
                "steps": [
                    {
                        "range": [minimum, maximum],
                        "color": "#263449"
                    }
                ],
                "threshold": {
                    "line": {
                        "color": "#FFFFFF",
                        "width": 3
                    },
                    "thickness": 0.85,
                    "value": display_value
                }
            }
        )
    )

    fig.update_layout(
        height=245,
        margin=dict(l=25, r=25, t=55, b=10),
        paper_bgcolor="#111827",
        font={"color": "#FFFFFF"}
    )

    return fig


# --------------------------------------------------
# BATTERY PARAMETER GAUGES
# --------------------------------------------------

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
            warning_low=VOLTAGE_LOW,
            warning_high=VOLTAGE_HIGH,
            critical_low=VOLTAGE_CRITICAL_LOW,
            critical_high=VOLTAGE_CRITICAL_HIGH
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )

with g2:
    st.plotly_chart(
        create_gauge(
            "BATTERY CURRENT",
            current,
            "A",
            0,
            35,
            warning_low=0,
            warning_high=CURRENT_HIGH,
            critical_low=0,
            critical_high=CURRENT_CRITICAL
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
            warning_low=0,
            warning_high=TEMP_HIGH,
            critical_low=0,
            critical_high=TEMP_CRITICAL
        ),
        use_container_width=True,
        config={"displayModeBar": False}
    )


st.divider()


# --------------------------------------------------
# STATE OF CHARGE
# --------------------------------------------------

st.markdown("### BATTERY STATE OF CHARGE")

soc_col1, soc_col2 = st.columns([1, 2])

with soc_col1:

    soc_fig = go.Figure(
        data=[
            go.Pie(
                values=[soc, 100 - soc],
                hole=0.76,
                marker={
                    "colors": ["#22C55E", "#263449"],
                    "line": {
                        "color": "#111827",
                        "width": 2
                    }
                },
                textinfo="none",
                sort=False
            )
        ]
    )

    soc_fig.update_layout(
        height=240,
        showlegend=False,
        paper_bgcolor="#0B1120",
        margin=dict(l=10, r=10, t=10, b=10),
        annotations=[
            {
                "text": f"<b>{soc}%</b><br><span style='font-size:12px'>CHARGE</span>",
                "showarrow": False,
                "font": {
                    "size": 25,
                    "color": "#FFFFFF"
                }
            }
        ]
    )

    st.plotly_chart(
        soc_fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )

with soc_col2:
    st.markdown("#### Battery Charge Information")

    st.progress(soc / 100)

    st.metric("State of Charge (SoC)", f"{soc}%")

    if soc >= 70:
        st.success("Battery charge level: High")
    elif soc >= 30:
        st.info("Battery charge level: Moderate")
    else:
        st.warning("Battery charge level: Low")


st.divider()


# --------------------------------------------------
# PERFORMANCE DATA
# --------------------------------------------------

st.markdown("### BATTERY PERFORMANCE ANALYSIS")

np.random.seed(42)

time_values = np.arange(0, 31, 1)

voltage_data = (
    voltage + 0.35 * np.sin(time_values / 3)
    + np.random.normal(0, 0.06, len(time_values))
)

current_data = (
    current + 0.8 * np.sin(time_values / 4)
    + np.random.normal(0, 0.12, len(time_values))
)

temperature_data = (
    temperature + 0.5 * np.sin(time_values / 5)
    + np.random.normal(0, 0.08, len(time_values))
)


def create_line_chart(x, y, title, y_title, line_color):

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            line={
                "color": line_color,
                "width": 3,
                "shape": "spline"
            },
            fill="tozeroy",
            fillcolor="rgba(56, 189, 248, 0.07)"
        )
    )

    fig.update_layout(
        title={
            "text": title,
            "font": {
                "size": 18,
                "color": "#F8FAFC"
            }
        },
        xaxis_title="Time (seconds)",
        yaxis_title=y_title,
        height=330,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        font={"color": "#CBD5E1"},
        margin=dict(l=45, r=25, t=55, b=45),
        xaxis={
            "gridcolor": "#263449",
            "zerolinecolor": "#263449"
        },
        yaxis={
            "gridcolor": "#263449",
            "zerolinecolor": "#263449"
        },
        hovermode="x unified"
    )

    return fig


# --------------------------------------------------
# THREE SEPARATE PERFORMANCE GRAPHS
# --------------------------------------------------

st.markdown("#### 1. Voltage Performance")

st.plotly_chart(
    create_line_chart(
        time_values,
        voltage_data,
        "Battery Voltage vs Time",
        "Voltage (V)",
        "#38BDF8"
    ),
    use_container_width=True,
    config={"displayModeBar": False}
)

st.markdown("#### 2. Current Performance")

st.plotly_chart(
    create_line_chart(
        time_values,
        current_data,
        "Battery Current vs Time",
        "Current (A)",
        "#A78BFA"
    ),
    use_container_width=True,
    config={"displayModeBar": False}
)

st.markdown("#### 3. Temperature Performance")

st.plotly_chart(
    create_line_chart(
        time_values,
        temperature_data,
        "Battery Temperature vs Time",
        "Temperature (°C)",
        "#F59E0B"
    ),
    use_container_width=True,
    config={"displayModeBar": False}
)


st.divider()


# --------------------------------------------------
# SAFETY ALERT PANEL
# --------------------------------------------------

st.markdown("### BATTERY SAFETY & FAULT DETECTION")

if alerts:
    for alert in alerts:
        if "CRITICAL" in alert:
            st.error(alert)
        else:
            st.warning(alert)
else:
    st.success("No abnormal battery conditions detected.")


# --------------------------------------------------
# SYSTEM SUMMARY
# --------------------------------------------------

st.markdown("### SYSTEM SUMMARY")

summary1, summary2, summary3, summary4 = st.columns(4)

summary1.metric("Voltage", f"{voltage:.1f} V")
summary2.metric("Current", f"{current:.1f} A")
summary3.metric("Temperature", f"{temperature:.1f} °C")
summary4.metric("Battery SoC", f"{soc}%")


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.markdown("---")

st.markdown(
    """
    <p style="text-align:center; color:#64748B; font-size:13px;">
        SMART EV BATTERY MANAGEMENT SYSTEM |
        Academic Project Demonstration |
        Simulated Data
    </p>
    """,
    unsafe_allow_html=True
)
