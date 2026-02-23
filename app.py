import streamlit as st

from unified_runner import switch_to

st.set_page_config(page_title="Unified App Hub", page_icon="🧭", layout="wide")

st.title("Unified Application Hub")
st.caption("Choose an application. Switching apps clears current session state.")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Chinese")
    st.write("Chinese dictionary and lineage tools.")
    if st.button("Open Chinese", use_container_width=True, type="primary"):
        switch_to("pages/01_Chinese.py")

with col2:
    st.subheader("Spanish")
    st.write("Spanish verb lab and editor.")
    if st.button("Open Spanish", use_container_width=True, type="primary"):
        switch_to("pages/02_Spanish.py")

with col3:
    st.subheader("MVC")
    st.write("MVC calculator and editor tools.")
    if st.button("Open MVC", use_container_width=True, type="primary"):
        switch_to("pages/03_MVC.py")

st.divider()
st.info("State is intentionally reset whenever you switch applications.", icon="🧼")
