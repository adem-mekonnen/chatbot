import streamlit as st

st.title("SUCCESS")
st.write("Your Streamlit app is working!")

if st.button("Click me"):
    st.success("Button clicked! Everything works!")
