import os
from dotenv import load_dotenv

load_dotenv()

# Initialize flags
USE_STREAMLIT_SECRETS = False
GOOGLE_CREDENTIALS_PATH = None
GROQ_API_KEY = None
GOOGLE_SHEETS_ID = None

# Try Streamlit first, but only if running inside Streamlit
try:
    import streamlit as st
    
    # Check if we have secrets available
    if hasattr(st, "secrets") and len(st.secrets) > 0:
        try:
            GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")
            GOOGLE_SHEETS_ID = st.secrets.get("GOOGLE_SHEETS_ID")
            
            # Check if google_credentials exist in secrets
            if "google_credentials" in st.secrets:
                GOOGLE_CREDENTIALS_PATH = None
                USE_STREAMLIT_SECRETS = True
            else:
                # Secrets exist but no google_credentials
                GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
                USE_STREAMLIT_SECRETS = False
        except Exception as e:
            print(f"Warning: Could not load Streamlit secrets: {e}")
            USE_STREAMLIT_SECRETS = False
    else:
        # Streamlit available but no secrets - use local config
        USE_STREAMLIT_SECRETS = False
        
except ImportError:
    # Streamlit not installed - use local config
    USE_STREAMLIT_SECRETS = False
except Exception as e:
    # Any other error - use local config
    print(f"Warning: Error importing Streamlit: {e}")
    USE_STREAMLIT_SECRETS = False

# If not using Streamlit secrets, get from environment variables
if not USE_STREAMLIT_SECRETS:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

# Ensure we have API key
if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY not found in environment or Streamlit secrets")

if not GOOGLE_SHEETS_ID:
    print("⚠️  WARNING: GOOGLE_SHEETS_ID not found in environment or Streamlit secrets")

# Sheet Names (Must match your Google Sheet tabs exactly)
SHEET_NAMES = {
    "pilots": "Pilot Roster",
    "drones": "Drone Fleet",
    "missions": "Missions"
}

# Groq Model Configuration
GROQ_MODEL = "llama-3.1-8b-instant"

# Currency and Regional Settings
CURRENCY = "INR"
DEFAULT_TIMEZONE = "Asia/Kolkata"

# Weather Compatibility Mapping
WEATHER_DRONE_COMPATIBILITY = {
    "Rainy": ["IP43 (Rain)", "IP43"],
    "Sunny": ["Standard", "IP43 (Rain)", "IP43", "None (Clear Sky Only)"],
    "Cloudy": ["Standard", "IP43 (Rain)", "IP43", "None (Clear Sky Only)"],
    "Clear": ["Standard", "IP43", "IP67"]
}

# Certification Types
CERTIFICATION_TYPES = ["DGCA", "Night Ops"]

# Skill Categories
SKILL_CATEGORIES = ["Mapping", "Survey", "Inspection", "Thermal"]

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"