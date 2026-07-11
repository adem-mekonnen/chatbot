import streamlit as st

st.title("🎉 SUCCESS!")
st.write("If you can see this, Streamlit is working!")
st.balloons()

if st.button("Click me!"):
    st.success("✅ Your Streamlit deployment works!")
