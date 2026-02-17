import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

# 1. FIXED: Google Sheets Configuration
if hasattr(st, "secrets") and "google_credentials" in st.secrets:
    GOOGLE_SHEETS_ID = st.secrets.get("GOOGLE_SHEETS_ID", os.getenv("GOOGLE_SHEETS_ID"))
    GOOGLE_CREDENTIALS_PATH = None  # Explicitly set to None so code doesn't look for a file
    USE_STREAMLIT_SECRETS = True
else:
    GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
    # Only assign the path if we are NOT on the cloud
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    USE_STREAMLIT_SECRETS = False
# 2. VERIFIED: Sheet Names (Must match your CSV/Tab names exactly)
SHEET_NAMES = {
    "pilots": "Pilot Roster",
    "drones": "Drone Fleet",
    "missions": "Missions"
}

# 3. FIXED: Updated Model Name to prevent 404 errors
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.1-8b-instant" 

# 4. FIXED: Added Currency and Global Settings
CURRENCY = "INR"
DEFAULT_TIMEZONE = "Asia/Kolkata"

# 5. FIXED: Aligned Weather Mapping with your actual Drone Fleet data
# Your CSV uses "IP43 (Rain)" and "None (Clear Sky Only)"
WEATHER_DRONE_COMPATIBILITY = {
    "Rainy": ["IP43 (Rain)"],
    "Sunny": ["Standard", "IP43 (Rain)", "None (Clear Sky Only)"],
    "Cloudy": ["Standard", "IP43 (Rain)", "None (Clear Sky Only)"]
}

# Certification and Skill lists
CERTIFICATION_TYPES = ["DGCA", "Night Ops"]
SKILL_CATEGORIES = ["Mapping", "Survey", "Inspection", "Thermal"]

# Agent Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

