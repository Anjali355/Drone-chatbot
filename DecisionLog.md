# Decision Log: Skylark Drones Operations Coordinator

## 1. Key Assumptions

* **Data Source as Source of Truth:** Assumed Google Sheets acts as the primary database. Any local state in the application is ephemeral and must be synced from the cloud to ensure multi-user consistency.
* **LLM Role:** Assumed the LLM (Llama 3 via Groq) should act as a **Parser and Generator**, not as the business logic executor. The "brain" for conflict detection is hard-coded in Python (`rule_engine.py`) to ensure 100% accuracy and prevent LLM hallucinations in critical safety checks.
* **Weather Logic:** Assumed drone "Weather Ratings" follow a strict hierarchy (e.g., an IP43 rated drone can handle "Rainy" and "Clear," but a "None" rated drone can only handle "Clear").
* **Concurrency:** Assumed low-concurrency usage typical of an operations desk. Extensive row-locking was not implemented for the Google Sheets integration.

## 2. Trade-offs Chosen and Why

* **Streamlit vs. Custom React Frontend:**
* **Choice:** Streamlit.
* **Why:** Development speed was prioritized. Streamlit allowed for a rapid build of a functional dashboard with a built-in chat interface, allowing more time to be spent on the logic and LLM integration.


* **Stateless vs. Stateful LLM:**
* **Choice:** Structured Parsing (Stateless).
* **Why:** Instead of sending the entire database to the LLM (which hits token limits and increases latency), I chose to parse the query into a structured `QueryRequest` and then query the local Python data objects. This is faster and more cost-effective.


* **In-Memory Processing for Conflicts:**
* **Choice:** Pulling all data into Pydantic objects for processing.
* **Why:** Performing complex conflict checks (like date overlaps) across multiple Google Sheet tabs using API calls would be too slow. Fetching everything once and processing in memory provides a snappy user experience.



## 3. Interpretation of "Urgent Reassignments"

I interpreted this requirement as a **high-priority resolution flow** triggered when a mission critical failure occurs (e.g., a pilot calls in sick or a drone enters maintenance).

* **Detection:** The system identifies a "Critical" conflict where a previously valid mission now has an "Unavailable" resource.
* **Automation:** The agent doesn't just report the error; it proactively searches the `PilotRoster` and `DroneFleet` for candidates that match:
1. **Skills/Capabilities** (e.g., "Thermal Imaging" required).
2. **Location** (Must be in the same city).
3. **Temporal Availability** (No overlapping missions on those dates).


* **Execution:** The system presents a "One-Click Reassign" option which updates the Google Sheet instantly to minimize operational downtime.

## 4. What I’d Do Differently with More Time

* **Vector Database for Manuals (RAG):** I would implement a RAG (Retrieval-Augmented Generation) pipeline. If a user asks, *"Can Pilot X fly Drone Y?"*, the system could reference PDF manuals or DGCA regulations stored in a vector DB to provide a compliance-based answer.
* **Advanced Scheduling (OR-Tools):** Instead of simple "Available/Unavailable" checks, I would use Google OR-Tools to provide **Optimized Reassignments**—automatically suggesting the pilot who is not only available but has the lowest cost or the most experience for that specific mission type.
* **OAuth Integration:** Replace the Service Account auth with User OAuth so the system can track *who* made which change in the Google Sheet for better accountability.
* **Asynchronous Processing:** Use `FastAPI` with `Celery` for the backend. Currently, the UI waits for the Google Sheet to update. For a larger fleet, this should happen in the background to keep the UI responsive.