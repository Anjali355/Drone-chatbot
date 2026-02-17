# Skylark Drones Operations Coordinator

The **Skylark Drones Operations Coordinator** is an AI-powered management system designed to streamline drone fleet operations. It features a natural language interface that allows users to query pilot availability, drone capabilities, and mission conflicts through a Streamlit-based dashboard.

## 🚀 Key Features

* **Natural Language Processing:** Uses the Groq API (Llama 3) to parse complex user queries into structured operational requests.
* **Conflict Detection Engine:** Automatically identifies issues such as pilot/drone double-bookings, skill/certification mismatches, and budget overruns.
* **Google Sheets Integration:** Real-time synchronization with Google Sheets for managing pilot rosters, drone fleets, and mission data.
* 
**Interactive Dashboard:** A Streamlit frontend providing data visualization, pilot/drone management views, and a dedicated chatbot interface.


* **Cost Estimation:** Calculates mission costs based on pilot hourly rates and estimated flight hours.

## 🛠️ Project Structure

* 
`app.py`: Streamlit frontend and dashboard UI.


* `main.py`: Core agent orchestrator that handles query routing and business logic.
* `llm_parser.py`: Integrates with Groq LLM to interpret natural language.
* `rule_engine.py`: Contains the logic for conflict detection and validation.
* `sheet_service.py`: Manages authentication and data sync with Google Sheets API.
* `schemas.py`: Pydantic models for type safety across pilots, drones, and missions.
* 
`config.py`: Centralized configuration for API keys, Sheet IDs, and weather compatibility.



## 📋 Prerequisites

* Python 3.8+
* Google Cloud Service Account (for Sheets API access).
* Groq API Key (for LLM parsing).



## ⚙️ Setup & Installation

1. **Install Dependencies:**
```bash
pip install -r requirements.txt

```


2. **Environment Variables:** Create a `.env` file or use Streamlit secrets with the following:
* 
`GROQ_API_KEY`: Your Groq API key.


* 
`GOOGLE_SHEETS_ID`: The ID of your operations Google Sheet.


* `google_credentials`: Service account JSON content.


3. **Run the Application:**
```bash
streamlit run app.py

```



## 💬 Example Queries

You can interact with the system using natural language:

* 
*"Find pilots with survey skills"* 


* 
*"Show drones with thermal capability in Mumbai"* 


* 
*"Calculate cost of mission PRJ001 with pilot Arjun"* 


* 
*"Check for conflicts across all missions"* 


* 
*"Show pilots available on 2026-02-07"*