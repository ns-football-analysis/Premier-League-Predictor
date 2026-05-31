import streamlit as st

# This simple configuration automatically looks inside the 'pages' folder 
# and builds a beautiful navigation sidebar for your user layout!
st.set_page_config(page_title="PL Analytics Hub", layout="wide")

st.write("# 🏆 Premier League Prediction Hub")
st.write("Welcome to your Premier league predictor. Use the sidebar menu on the left to toggle features:")
st.write("* **1 Match Predictor:** Run individual head-to-head fixtures.")
st.write("* **2 Season Simulator:** Run end of season simulation to project the final league table standings.")
st.info("👈 Open the sidebar menu on the left to select an application sheet!")