import requests
import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Helios-X Dashboard", layout="wide")
st.title("Helios-X Trading Dashboard")

API_URL = "http://127.0.0.1:8000"

def safe_request(method, endpoint, **kwargs):
    try:
        if method == 'get':
            return requests.get(f"{API_URL}{endpoint}", timeout=2, **kwargs).json()
        elif method == 'post':
            return requests.post(f"{API_URL}{endpoint}", timeout=2, **kwargs).json()
    except Exception as e:
        return {"error": str(e)}

st.sidebar.header("System Status")
status = safe_request('get', '/status')

if "error" in status:
    st.error(f"⚠️ Cannot reach API at {API_URL}")
    st.info("Start the API server with: `uvicorn helios_api.server:app --port 8000`")
else:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Running", "Yes" if status.get('running') else "No")
    with col2:
        st.metric("PID", status.get('pid', 'N/A'))
    with col3:
        st.metric("Kill Switch", "Active" if status.get('kill_switch') else "Ready")
    with col4:
        st.metric("Audit Log", "Active" if status.get('audit_exists') else "Inactive")
    
    st.divider()
    st.header("Trading Controls")
    
    with st.form("start_form"):
        col1, col2 = st.columns(2)
        with col1:
            symbol = st.text_input("Symbol", value="SPLG")
            capital = st.number_input("Capital ($)", value=500.0, step=100.0)
        with col2:
            qty = st.number_input("Qty per trade", value=1, step=1)
            duration = st.number_input("Duration (seconds)", value=1800, step=300)
        
        if st.form_submit_button("Start Trading"):
            result = safe_request('post', '/start', json={
                "symbol": symbol.upper(),
                "capital": float(capital),
                "qty": int(qty),
                "run_seconds": int(duration)
            })
            if "error" not in result:
                st.success(f"✅ Trading started (PID: {result.get('pid')})")
            else:
                st.error(f"❌ Error: {result.get('error')}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⏸ Stop (Graceful)"):
            result = safe_request('post', '/stop')
            st.info("Graceful stop initiated...")
    with col2:
        if st.button("🛑 Kill (Hard Stop)"):
            result = safe_request('post', '/kill')
            st.warning("Hard stop executed")
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    st.divider()
    st.header("Audit Log")
    n = st.slider("Lines to show", 10, 500, 100, 10)
    if st.button("Load Audit Log"):
        audit = safe_request('get', f'/audit/tail?n={n}')
        if "error" not in audit:
            for line in audit.get('lines', []):
                st.write(line)
