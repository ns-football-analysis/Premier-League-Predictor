import streamlit as st

# Update page_title and add page_icon to customize the main landing appearance
st.set_page_config(page_title="PL Analytics Hub", page_icon="🏠", layout="wide")

# This tells Streamlit to display "Home" as the page label in the sidebar menu
st.sidebar.success("Select a dashboard above.") 

st.write("# 🏆 Premier League Prediction Hub")
st.write("Welcome to your Premier league predictor. Use the sidebar menu on the left to toggle features:")
st.write("* **1 Match Predictor:** Run individual head-to-head fixtures.")
st.write("* **2 Season Simulator:** Run simulations to project the final league table standings.")
st.info("👈 Open the sidebar menu on the left to select an application sheet!")
