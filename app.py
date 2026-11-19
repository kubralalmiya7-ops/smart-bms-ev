# SMART EV BATTERY MANAGEMENT SYSTEM — V4.3
# Intelligent Protection & Fault Recovery
# Software simulation only; not certified battery protection hardware.

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Smart EV BMS V4.3", page_icon="🔋", layout="wide")
st.markdown("""\n<style>
.stApp {background:#0b1120;color:#e8eef7}
[data-testid="stSidebar"] {background:#111a2b}
.status-normal{background:#12382b;color:#4ade80;padding:12px;border-radius:10px;font-weight:bold}
.status-warning{background:#463416;color:#fbbf24;padding:12px;border-radius:10px;font-weight:bold}
.status-critical{background:#4a1e26;color:#fb7185;padding:12px;border-radius:10px;font-weight:bold}
</style>
""", unsafe_allow_html=True)

# Battery model: 13S4P Li-ion pack, illustrative parameters
SERIES, PARALLEL = 13, 4
CELL_NOM, CELL_MIN, CELL_MAX = 3.6, 3.0, 4.2
PACK_NOM, PACK_MIN, PACK_MAX = SERIES*CELL_NOM, SERIES*CELL_MIN, SERIES*CELL_MAX
DEFAULT_AH, R_INTERNAL = 10.0, 0.08
AMBIENT, THERMAL_CAP, COOL_COEFF = 25.0, 500.0, 1.5

# Thresholds and hysteresis recovery thresholds
V_LOW_WARN, V_LOW_CLEAR = 42.0, 43.0
V_LOW_CRIT, V_LOW_CRIT_CLEAR = PACK_MIN, 40.5
V_HIGH_WARN, V_HIGH_CLEAR = 53.0, 52.0
V_HIGH_CRIT, V_HIGH_CRIT_CLEAR = PACK_MAX, 53.5
I_WARN, I_WARN_CLEAR, I_CRIT, I_CRIT_CLEAR = 20.0, 18.0, 25.0, 22.0
T_WARN, T_WARN_CLEAR, T_CRIT, T_CRIT_CLEAR = 45.0, 42.0, 55.0, 48.0
WARNING_FACTOR, RESTORE_STEP_A = 0.50, 1.0

DEFAULTS = {
    "soc":80.0, "temperature":25.0, "voltage":PACK_NOM, "current":0.0,
    "requested_current":0.0, "effective_current":0.0, "capacity_ah":DEFAULT_AH,
    "discharged_wh":0.0, "charged_wh":0.0, "peak_temp":25.0,
    "heating_rate":0.0, "cooling_power":0.0, "thermal_state":"Normal",
    "safety_action":"Normal operation", "fault_flags":{}, "fault_history":[],
    "performance_history":[], "thermal_history":[], "recovery_mode":False,
    "simulation_elapsed":0
}
for k,v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v.copy() if isinstance(v,(dict,list)) else v

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log_event(event,severity,action,details=""):
    st.session_state.fault_history.insert(0, {"Timestamp":now(),"Event":event,"Severity":severity,"Action":action,"Details":details})
    st.session_state.fault_history = st.session_state.fault_history[:500]
def log_perf():
    s=st.session_state
    s.performance_history.append({"Timestamp":now(),"Voltage (V)":round(s.voltage,2),"Current (A)":round(s.current,2),"Requested Current (A)":round(s.requested_current,2),"Effective Current (A)":round(s.effective_current,2),"Temperature (°C)":round(s.temperature,2),"SoC (%)":round(s.soc,2),"Power (W)":round(s.voltage*s.current,2),"Thermal State":s.thermal_state,"Safety Action":s.safety_action})
    s.performance_history=s.performance_history[-1000:]
def log_thermal():
    s=st.session_state
    s.thermal_history.append({"Timestamp":now(),"Temperature (°C)":round(s.temperature,2),"Heating Rate (°C/min)":round(s.heating_rate,2),"Cooling Power (W)":round(s.cooling_power,2),"Thermal State":s.thermal_state})
    s.thermal_history=s.thermal_history[-1000:]
def reset_all():
    for k,v in DEFAULTS.items(): st.session_state[k]=v.copy() if isinstance(v,(dict,list)) else v
    st.rerun()

def ocv(soc): return (3.0+np.clip(soc,0,100)/100*1.2)*SERIES
def calc_voltage(soc,current): return float(np.clip(ocv(soc)-current*R_INTERNAL,PACK_MIN,PACK_MAX))
def calc_soc(soc,current,seconds,capacity):
    if capacity<=0:return soc
    return float(np.clip(soc-current*seconds/(3600*capacity)*100,0,100))
def calc_temp(temp,current,seconds):
    heat=current**2*R_INTERNAL
    cooling=COOL_COEFF*(temp-AMBIENT)
    return float(max(AMBIENT,temp+(heat-cooling)*seconds/THERMAL_CAP))

# Stateful hysteresis: faults remain latched until their separate clear threshold.
def update_flag(name,trigger,clear_condition):
    flags=st.session_state.fault_flags; was=flags.get(name,False)
    if not was and trigger: flags[name]=True; return "activated"
    if was and clear_condition: flags[name]=False; return "recovered"
    flags[name]=was; return None
def update_faults():
    s=st.session_state; v=s.voltage; i=abs(s.requested_current); t=s.temperature
    checks=[
        ("High Temperature Warning",t>=T_WARN,t<=T_WARN_CLEAR),
        ("Critical Temperature",t>=T_CRIT,t<=T_CRIT_CLEAR),
        ("Low Voltage Warning",v<=V_LOW_WARN,v>=V_LOW_CLEAR),
        ("Critical Low Voltage",v<=V_LOW_CRIT,v>=V_LOW_CRIT_CLEAR),
        ("High Voltage Warning",v>=V_HIGH_WARN,v<=V_HIGH_CLEAR),
        ("Critical High Voltage",v>=V_HIGH_CRIT,v<=V_HIGH_CRIT_CLEAR),
        ("High Current Warning",i>=I_WARN,i<=I_WARN_CLEAR),
        ("Critical Overcurrent",i>=I_CRIT,i<=I_CRIT_CLEAR),
        ("Rapid Temperature Rise",s.heating_rate>=5.0,s.heating_rate<=2.0),
    ]
    for name,trig,clear in checks:
        result=update_flag(name,trig,clear)
        if result=="activated": log_event(name,"Warning","Fault detected","Protection condition reached")
        elif result=="recovered": log_event(name,"Recovery","Fault cleared","Recovery threshold satisfied")

def severity_status():
    flags=st.session_state.fault_flags
    critical=[f for f in ["Critical Temperature","Critical Low Voltage","Critical High Voltage","Critical Overcurrent"] if flags.get(f)]
    warning=[f for f in ["High Temperature Warning","Low Voltage Warning","High Voltage Warning","High Current Warning","Rapid Temperature Rise"] if flags.get(f)]
    if critical:return "CRITICAL",critical
    if warning:return "WARNING",warning
    return "NORMAL",[]
def apply_safety(requested):
    s=st.session_state; sev,faults=severity_status(); prev=s.effective_current
    if sev=="CRITICAL": effective=0.0; action="CRITICAL SHUTDOWN — LOAD DISABLED"; s.recovery_mode=False
    elif sev=="WARNING": effective=requested*WARNING_FACTOR; action="WARNING — LOAD REDUCED"; s.recovery_mode=False
    else:
        delta=requested-prev
        effective=prev+np.sign(delta)*RESTORE_STEP_A if abs(delta)>RESTORE_STEP_A else requested
        s.recovery_mode=abs(requested-effective)>1e-9
        action="NORMAL — CONTROLLED LOAD RESTORATION" if s.recovery_mode else "NORMAL OPERATION"
    s.effective_current=float(effective); s.safety_action=action
    return sev,faults,effective,action

def gauge(title,value,minv,maxv,unit,color):
    fig=go.Figure(go.Indicator(mode="gauge+number",value=value,number={"suffix":unit,"font":{"color":"#eaf2ff"}},title={"text":title,"font":{"color":"#eaf2ff"}},gauge={"axis":{"range":[minv,maxv],"tickfont":{"color":"#9fb0c8"}},"bar":{"color":color},"bgcolor":"#162236","borderwidth":1,"bordercolor":"#26364e"}))
    fig.update_layout(height=255,paper_bgcolor="#0b1120",font_color="#eaf2ff",margin=dict(l=15,r=15,t=45,b=15)); return fig
def line_chart(df,x,y,title,ylabel):
    if df.empty: st.info("Chart will appear after simulation advances."); return
    fig=go.Figure(go.Scatter(x=df[x],y=df[y],mode="lines",name=y,line={"width":2}))
    fig.update_layout(title=title,xaxis_title="Time",yaxis_title=ylabel,paper_bgcolor="#0b1120",plot_bgcolor="#111a2b",font_color="#eaf2ff",height=330,margin=dict(l=35,r=15,t=45,b=35))
    st.plotly_chart(fig,use_container_width=True)

st.title("🔋 Smart EV Battery Management System")
st.caption("Version 4.3 | Intelligent Protection & Fault Recovery")
st.info("Software simulation: displayed readings are simulated or manually entered; no real battery sensors are connected.")

# Sidebar inputs
st.sidebar.title("⚙️ Simulation Controls")
mode=st.sidebar.radio("Operating Mode",["Automatic Simulation","Manual Fault Testing"],key="mode_choice")
capacity=st.sidebar.number_input("Battery Capacity (Ah)",min_value=1.0,max_value=100.0,value=float(st.session_state.capacity_ah),step=1.0)
st.session_state.capacity_ah=capacity
manual_voltage=PACK_NOM; manual_current=0.0; manual_temperature=25.0; advance=False
if mode=="Automatic Simulation":
    scenario=st.sidebar.selectbox("Scenario",["Idle","Driving - Low Load","Driving - High Load","Charging"])
    requested={"Idle":0.0,"Driving - Low Load":5.0,"Driving - High Load":15.0,"Charging":-5.0}[scenario]
else:
    st.sidebar.caption("Set inputs, then press Advance to apply a 10-second test step.")
    manual_voltage=st.sidebar.slider("Pack Voltage (V)",float(PACK_MIN),float(PACK_MAX),float(np.clip(st.session_state.voltage,PACK_MIN,PACK_MAX)),0.1)
    manual_current=st.sidebar.slider("Requested Current (A)",-30.0,30.0,float(np.clip(st.session_state.requested_current,-30,30)),0.5)
    manual_temperature=st.sidebar.slider("Battery Temperature (°C)",15.0,70.0,float(np.clip(st.session_state.temperature,15,70)),0.5)
    requested=manual_current
    advance=st.sidebar.button("▶ Advance Manual Simulation (10 sec)",use_container_width=True)
if st.sidebar.button("🔄 Reset Simulation",use_container_width=True): reset_all()

# Update simulation only in automatic mode, or on explicit manual advance.
def simulation_step(req,seconds):
    s=st.session_state; oldtemp=s.temperature; s.requested_current=float(req)
    s.voltage=calc_voltage(s.soc,req)
    s.temperature=calc_temp(oldtemp,req,seconds)
    s.heating_rate=(s.temperature-oldtemp)/seconds*60 if seconds>0 else 0.0
    s.cooling_power=max(0.0,COOL_COEFF*(s.temperature-AMBIENT))
    s.peak_temp=max(s.peak_temp,s.temperature)
    update_faults()
    _,_,effective,_=apply_safety(req)
    s.soc=calc_soc(s.soc,effective,seconds,s.capacity_ah)
    s.voltage=calc_voltage(s.soc,effective)
    update_faults()
    s.current=float(effective)
    power=s.voltage*effective
    if power>=0:s.discharged_wh+=power*seconds/3600
    else:s.charged_wh+=abs(power)*seconds/3600
    s.simulation_elapsed+=seconds
    if s.fault_flags.get("Critical Temperature",False):s.thermal_state="Critical"
    elif s.fault_flags.get("High Temperature Warning",False):s.thermal_state="Warning"
    else:s.thermal_state="Normal"
    log_perf(); log_thermal()
if mode=="Automatic Simulation":
    st_autorefresh(interval=2000,key="refresh_v43")
    simulation_step(requested,2.0)
elif advance:
    # In manual mode, the sliders are direct test inputs. Their values are applied
    # before fault evaluation; temperature is held at the selected value for this step.
    s=st.session_state; s.voltage=manual_voltage; s.temperature=manual_temperature
    s.requested_current=manual_current; s.heating_rate=0.0
    s.cooling_power=max(0.0,COOL_COEFF*(manual_temperature-AMBIENT)); s.peak_temp=max(s.peak_temp,manual_temperature)
    update_faults(); _,_,effective,_=apply_safety(manual_current); s.current=effective
    s.soc=calc_soc(s.soc,effective,10.0,s.capacity_ah); s.voltage=manual_voltage
    power=manual_voltage*effective
    if power>=0:s.discharged_wh+=power*10/3600
    else:s.charged_wh+=abs(power)*10/3600
    s.simulation_elapsed+=10
    if s.fault_flags.get("Critical Temperature",False):s.thermal_state="Critical"
    elif s.fault_flags.get("High Temperature Warning",False):s.thermal_state="Warning"
    else:s.thermal_state="Normal"
    log_perf(); log_thermal()

# Current status panel
sev,active=severity_status()
if sev=="CRITICAL":st.markdown('<div class="status-critical">🚨 CRITICAL — PROTECTION ACTIVE</div>',unsafe_allow_html=True)
elif sev=="WARNING":st.markdown('<div class="status-warning">⚠️ WARNING — LOAD REDUCTION ACTIVE</div>',unsafe_allow_html=True)
else:st.markdown('<div class="status-normal">✅ NORMAL — SYSTEM OPERATING</div>',unsafe_allow_html=True)
if active:st.error("Active fault(s): "+", ".join(active))
else:st.success("No active faults detected.")
st.info("**Safety action:** "+st.session_state.safety_action)
if st.session_state.recovery_mode:st.warning("Recovery mode: load is being restored gradually.")

# Battery overview
st.header("📊 Battery Overview")
cols=st.columns(4)
for col,label,value in zip(cols,["State of Charge","Pack Voltage","Battery Current","Temperature"],[f"{st.session_state.soc:.1f}%",f"{st.session_state.voltage:.2f} V",f"{st.session_state.current:.2f} A",f"{st.session_state.temperature:.2f} °C"]):col.metric(label,value)
cols=st.columns(4)
for col,label,value in zip(cols,["Requested Current","Effective Current","Peak Temperature","Heating Rate"],[f"{st.session_state.requested_current:.2f} A",f"{st.session_state.effective_current:.2f} A",f"{st.session_state.peak_temp:.2f} °C",f"{st.session_state.heating_rate:.2f} °C/min"]):col.metric(label,value)

# Gauge panels
st.header("🎛️ Battery Parameter Gauges")
gcols=st.columns(3)
for col,title,val,minv,maxv,unit,color in [
    (gcols[0],"Voltage",st.session_state.voltage,PACK_MIN,PACK_MAX," V","#38bdf8"),
    (gcols[1],"Current Magnitude",abs(st.session_state.current),0,30," A","#a78bfa"),
    (gcols[2],"Temperature",st.session_state.temperature,15,70," °C","#fb923c")]:col.plotly_chart(gauge(title,val,minv,maxv,unit,color),use_container_width=True)

# SoC and capacity
st.header("🔋 Battery Capacity Analysis")
sc1,sc2=st.columns([1,1])
with sc1:
    socfig=go.Figure(go.Pie(labels=["Remaining","Used"],values=[st.session_state.soc,100-st.session_state.soc],hole=0.65,marker={"colors":["#38bdf8","#263449"]},textinfo="label+percent"))
    socfig.update_layout(paper_bgcolor="#0b1120",font_color="#eaf2ff",height=300,annotations=[{"text":f"{st.session_state.soc:.1f}%","showarrow":False,"font":{"size":25,"color":"#eaf2ff"}}])
    st.plotly_chart(socfig,use_container_width=True)
with sc2:
    remaining=st.session_state.capacity_ah*st.session_state.soc/100
    st.metric("Rated Capacity",f"{st.session_state.capacity_ah:.2f} Ah")
    st.metric("Remaining Capacity",f"{remaining:.2f} Ah")
    st.metric("Consumed Capacity",f"{st.session_state.capacity_ah-remaining:.2f} Ah")
    st.caption("SoC uses simulated coulomb counting. SoH is not calculated; it requires measured capacity-test data.")

# Power and energy metrics
st.header("⚡ Power & Energy Analysis")
power=st.session_state.voltage*st.session_state.current
pcols=st.columns(3)
for col,label,val in zip(pcols,["Instantaneous Power","Energy Discharged","Energy Charged"],[f"{power:.2f} W",f"{st.session_state.discharged_wh:.3f} Wh",f"{st.session_state.charged_wh:.3f} Wh"]):col.metric(label,val)
st.caption("Positive power indicates discharge; negative power indicates charging.")

# Thermal summary
st.header("🌡️ Advanced Thermal Management")
tcols=st.columns(4)
for col,label,val in zip(tcols,["Thermal State","Peak Temperature","Heating Rate","Estimated Cooling Power"],[st.session_state.thermal_state,f"{st.session_state.peak_temp:.2f} °C",f"{st.session_state.heating_rate:.2f} °C/min",f"{st.session_state.cooling_power:.2f} W"]):col.metric(label,val)
st.caption("Cooling power is modeled heat removal, not measured cooling-system output.")

# Protection threshold table
st.header("🛡️ Intelligent Protection System")
thresholds=pd.DataFrame([
 {"Protection":"Low Voltage Warning","Trigger":f"≤ {V_LOW_WARN:.1f} V","Recovery":f"≥ {V_LOW_CLEAR:.1f} V","Action":"Load reduction"},
 {"Protection":"Critical Low Voltage","Trigger":f"≤ {V_LOW_CRIT:.1f} V","Recovery":f"≥ {V_LOW_CRIT_CLEAR:.1f} V","Action":"Load shutdown"},
 {"Protection":"High Voltage Warning","Trigger":f"≥ {V_HIGH_WARN:.1f} V","Recovery":f"≤ {V_HIGH_CLEAR:.1f} V","Action":"Load reduction"},
 {"Protection":"Critical High Voltage","Trigger":f"≥ {V_HIGH_CRIT:.1f} V","Recovery":f"≤ {V_HIGH_CRIT_CLEAR:.1f} V","Action":"Load shutdown"},
 {"Protection":"High Current Warning","Trigger":f"≥ {I_WARN:.1f} A","Recovery":f"≤ {I_WARN_CLEAR:.1f} A","Action":"Load reduction"},
 {"Protection":"Critical Overcurrent","Trigger":f"≥ {I_CRIT:.1f} A","Recovery":f"≤ {I_CRIT_CLEAR:.1f} A","Action":"Load shutdown"},
 {"Protection":"Temperature Warning","Trigger":f"≥ {T_WARN:.1f} °C","Recovery":f"≤ {T_WARN_CLEAR:.1f} °C","Action":"Load reduction"},
 {"Protection":"Critical Temperature","Trigger":f"≥ {T_CRIT:.1f} °C","Recovery":f"≤ {T_CRIT_CLEAR:.1f} °C","Action":"Load shutdown"},
 {"Protection":"Rapid Temperature Rise","Trigger":"≥ 5 °C/min","Recovery":"≤ 2 °C/min","Action":"Warning / load reduction"},
])
st.dataframe(thresholds,use_container_width=True,hide_index=True)

# Graphs
perf=pd.DataFrame(st.session_state.performance_history); therm=pd.DataFrame(st.session_state.thermal_history)
st.header("📈 Battery Performance History")
if not perf.empty:
    a,b=st.columns(2)
    with a:line_chart(perf,"Timestamp","Voltage (V)","Voltage Variation","Voltage (V)")
    with b:line_chart(perf,"Timestamp","Current (A)","Current Variation","Current (A)")
    a,b=st.columns(2)
    with a:line_chart(perf,"Timestamp","Temperature (°C)","Temperature Variation","Temperature (°C)")
    with b:line_chart(perf,"Timestamp","Power (W)","Power Variation","Power (W)")
    a,b=st.columns(2)
    with a:line_chart(perf,"Timestamp","SoC (%)","SoC History","SoC (%)")
    with b:line_chart(perf,"Timestamp","Effective Current (A)","Protected Load History","Current (A)")
else:st.info("Performance graphs populate after simulation steps.")

st.header("🌡️ Thermal History")
if not therm.empty:
    a,b=st.columns(2)
    with a:line_chart(therm,"Timestamp","Temperature (°C)","Temperature History","°C")
    with b:line_chart(therm,"Timestamp","Heating Rate (°C/min)","Heating / Cooling Rate","°C/min")
    a,b=st.columns(2)
    with a:line_chart(therm,"Timestamp","Cooling Power (W)","Estimated Cooling Power","W")
    with b:
        counts=therm["Thermal State"].value_counts()
        fig=go.Figure(go.Pie(labels=counts.index,values=counts.values,hole=0.5))
        fig.update_layout(paper_bgcolor="#0b1120",font_color="#eaf2ff",height=320)
        st.plotly_chart(fig,use_container_width=True)
else:st.info("Thermal history appears after simulation steps.")

# Fault-event history and downloads
st.header("📋 Fault Event & Recovery Log")
faults=pd.DataFrame(st.session_state.fault_history)
if not faults.empty:
    st.dataframe(faults,use_container_width=True,hide_index=True)
    st.download_button("⬇ Download Fault & Recovery CSV",faults.to_csv(index=False).encode(),"smart_bms_v4_3_fault_log.csv","text/csv")
else:st.info("No fault transitions yet. Try warning, critical, and recovery test conditions in Manual Fault Testing.")

st.header("💾 Performance Data Export")
if not perf.empty:st.download_button("⬇ Download Performance CSV",perf.to_csv(index=False).encode(),"smart_bms_v4_3_performance.csv","text/csv")
if not therm.empty:st.download_button("⬇ Download Thermal History CSV",therm.to_csv(index=False).encode(),"smart_bms_v4_3_thermal_history.csv","text/csv")

# Information/footer
st.header("ℹ️ System Information")
left,right=st.columns(2)
with left:
    st.markdown("**Battery Configuration**")
    st.write(f"- Lithium-ion battery model\n- Configuration: {SERIES}S{PARALLEL}P\n- Nominal pack voltage: {PACK_NOM:.1f} V\n- Pack voltage range: {PACK_MIN:.1f}–{PACK_MAX:.1f} V\n- Capacity: {st.session_state.capacity_ah:.1f} Ah\n- Internal resistance: {R_INTERNAL:.3f} Ω")
with right:
    st.markdown("**Software Configuration**")
    st.write("- Version: 4.3\n- Automatic simulation and manual testing\n- SoC: Coulomb counting\n- Voltage: simplified OCV and internal resistance model\n- Thermal: simplified heat/cooling model\n- Protection: fault thresholds and hysteresis\n- Priority: Critical > Warning > Normal\n- Recovery: gradual load restoration")
st.caption("No actual sensor readings or contactor are connected. SoH is not implemented. Academic simulation prototype only.")
st.divider()
st.markdown("<div style='text-align:center;color:#8fa3bd'>Smart EV Battery Management System — V4.3<br>Intelligent Protection & Fault Recovery<br>Academic Software Simulation Prototype</div>",unsafe_allow_html=True)
