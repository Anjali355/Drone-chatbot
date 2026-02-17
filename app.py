"""
Streamlit Frontend for Skylark Drones Operations Coordinator
Interactive chatbot interface with data visualization
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Any
import sys
import os

# Add parent directory to path to import agent modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import DronesOperationsAgent
from schemas import PilotStatus, DroneStatus

# ============= PAGE CONFIG =============
st.set_page_config(
    page_title="🚁 Skylark Drones Operations",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============= CUSTOM CSS =============
st.markdown("""
<style>
    .main-header {
        font-size: 2.5em;
        font-weight: bold;
        color: #1f77d4;
        text-align: center;
        margin-bottom: 20px;
    }
    .status-available {
        color: #00cc00;
        font-weight: bold;
    }
    .status-maintenance {
        color: #ff9900;
        font-weight: bold;
    }
    .status-unavailable {
        color: #ff0000;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============= SESSION STATE =============
@st.cache_resource
def init_agent():
    """Initialize the agent once and cache it"""
    try:
        return DronesOperationsAgent()
    except Exception as e:
        st.error(f"Failed to initialize agent: {e}")
        return None

if 'agent' not in st.session_state:
    st.session_state.agent = init_agent()

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# ============= MAIN APP =============
def main():
    # Header
    st.markdown("<div class='main-header'>🚁 SKYLARK DRONES OPERATIONS COORDINATOR</div>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Operations Control")
        
        # Refresh Data
        if st.button("🔄 Refresh Data", use_container_width=True):
            if st.session_state.agent:
                with st.spinner("Syncing data from Google Sheets..."):
                    st.session_state.agent.refresh_data()
                st.success("✓ Data refreshed!")
        
        st.divider()
        
        # Quick Stats
        if st.session_state.agent:
            col1, col2, col3 = st.columns(3)
            with col1:
                pilot_count = len(st.session_state.agent.pilots_list)
                st.metric("Pilots", pilot_count)
            with col2:
                drone_count = len(st.session_state.agent.drones_list)
                st.metric("Drones", drone_count)
            with col3:
                mission_count = len(st.session_state.agent.missions_list)
                st.metric("Missions", mission_count)
        
        st.divider()
        
        # Navigation
        st.subheader("📋 Quick Actions")
        action = st.radio(
            "Select action:",
            ["💬 Chat", "👥 Pilots", "🛸 Drones", "📊 Missions", "🔧 Operations", "❓ Help"]
        )
    
    # Main Content
    if action == "💬 Chat":
        show_chat_interface()
    elif action == "👥 Pilots":
        show_pilots_dashboard()
    elif action == "🛸 Drones":
        show_drones_dashboard()
    elif action == "📊 Missions":
        show_missions_dashboard()
    elif action == "🔧 Operations":
        show_operations_dashboard()
    elif action == "❓ Help":
        show_help()


def show_chat_interface():
    """Display chat interface"""
    st.subheader("💬 Natural Language Chat")
    st.write("Ask questions about pilots, drones, missions, and costs in natural language.")
    
    # Chat history
    chat_container = st.container()
    
    with chat_container:
        for i, (role, message) in enumerate(st.session_state.chat_history):
            if role == "user":
                with st.chat_message("user", avatar="👤"):
                    st.write(message)
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.write(message)
    
    st.divider()
    
    # Input
    col1, col2 = st.columns([0.9, 0.1])
    with col1:
        user_input = st.text_input(
            "Your query:",
            placeholder="e.g., 'Find pilots with survey skills' or 'Calculate cost of mission PRJ001 with pilot Arjun'",
            label_visibility="collapsed"
        )
    with col2:
        send_button = st.button("Send", use_container_width=True)
    
    if send_button and user_input:
        # Add user message to history
        st.session_state.chat_history.append(("user", user_input))
        
        # Get agent response
        if st.session_state.agent:
            with st.spinner("Processing..."):
                try:
                    response = st.session_state.agent.process_query(user_input)
                    st.session_state.chat_history.append(("assistant", response))
                    st.rerun()
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.session_state.chat_history.append(("assistant", error_msg))
                    st.rerun()
    
    # Quick query suggestions
    st.divider()
    st.write("**💡 Example queries:**")
    cols = st.columns(2)
    examples = [
        "Find pilots with survey skills",
        "Show drones with thermal capability",
        "Find drones in mumbai",
        "Calculate cost of PRJ001 with Arjun",
        "Show pilots available on 2026-02-07",
        "Check for conflicts"
    ]
    for i, example in enumerate(examples):
        with cols[i % 2]:
            if st.button(f"→ {example}", use_container_width=True):
                st.session_state.chat_history.append(("user", example))
                if st.session_state.agent:
                    with st.spinner("Processing..."):
                        response = st.session_state.agent.process_query(example)
                        st.session_state.chat_history.append(("assistant", response))
                st.rerun()


def show_pilots_dashboard():
    """Display pilots information"""
    st.subheader("👥 Pilots Management")
    
    if not st.session_state.agent:
        st.error("Agent not initialized")
        return
    
    pilots = st.session_state.agent.pilots_list
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.multiselect(
            "Filter by Status:",
            [PilotStatus.AVAILABLE.value, PilotStatus.ON_MISSION.value, PilotStatus.ON_LEAVE.value, PilotStatus.UNAVAILABLE.value],
            default=[PilotStatus.AVAILABLE.value, PilotStatus.ON_MISSION.value]
        )
    
    with col2:
        location_filter = st.multiselect(
            "Filter by Location:",
            list(set([p.current_location for p in pilots])),
            default=None
        )
    
    with col3:
        skill_filter = st.multiselect(
            "Filter by Skill:",
            list(set([skill for p in pilots for skill in p.skills])),
            default=None
        )
    
    # Filter pilots
    filtered_pilots = [
        p for p in pilots
        if (not status_filter or p.status.value in status_filter)
        and (not location_filter or p.current_location in location_filter)
        and (not skill_filter or any(s in p.skills for s in skill_filter))
    ]
    
    # Display pilots
    if filtered_pilots:
        # Create DataFrame
        df_data = []
        for pilot in filtered_pilots:
            df_data.append({
                "Name": pilot.name,
                "Status": pilot.status.value,
                "Location": pilot.current_location,
                "Skills": ", ".join(pilot.skills),
                "Certifications": ", ".join(pilot.certifications),
                "Rate (₹/hr)": f"₹{pilot.hourly_rate:.2f}",
                "Experience (hrs)": pilot.drone_experience_hours,
                "Current Assignment": pilot.current_assignment or "None"
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        # Detailed view
        st.divider()
        selected_pilot = st.selectbox(
            "Select pilot for details:",
            [p.name for p in filtered_pilots]
        )
        
        if selected_pilot:
            pilot = next((p for p in filtered_pilots if p.name == selected_pilot), None)
            if pilot:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Name:** {pilot.name}")
                    st.write(f"**Status:** {pilot.status.value}")
                    st.write(f"**Location:** {pilot.current_location}")
                    st.write(f"**Hourly Rate:** ₹{pilot.hourly_rate:.2f}")
                
                with col2:
                    st.write(f"**Skills:** {', '.join(pilot.skills)}")
                    st.write(f"**Certifications:** {', '.join(pilot.certifications)}")
                    st.write(f"**Experience:** {pilot.drone_experience_hours} hours")
                    st.write(f"**Current Assignment:** {pilot.current_assignment or 'None'}")
                
                if pilot.email:
                    st.write(f"**Email:** {pilot.email}")
                if pilot.phone:
                    st.write(f"**Phone:** {pilot.phone}")
    else:
        st.info("No pilots match the selected filters.")


def show_drones_dashboard():
    """Display drones information"""
    st.subheader("🛸 Drones Fleet Management")
    
    if not st.session_state.agent:
        st.error("Agent not initialized")
        return
    
    drones = st.session_state.agent.drones_list
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.multiselect(
            "Filter by Status:",
            [DroneStatus.AVAILABLE.value, DroneStatus.DEPLOYED.value, DroneStatus.MAINTENANCE.value, DroneStatus.GROUNDED.value],
            default=[DroneStatus.AVAILABLE.value]
        )
    
    with col2:
        location_filter = st.multiselect(
            "Filter by Location:",
            list(set([d.current_location for d in drones])),
            default=None
        )
    
    with col3:
        capability_filter = st.multiselect(
            "Filter by Capability:",
            list(set([cap for d in drones for cap in d.capabilities])),
            default=None
        )
    
    # Filter drones
    filtered_drones = [
        d for d in drones
        if (not status_filter or d.status.value in status_filter)
        and (not location_filter or d.current_location in location_filter)
        and (not capability_filter or any(c in d.capabilities for c in capability_filter))
    ]
    
    # Display drones
    if filtered_drones:
        df_data = []
        for drone in filtered_drones:
            df_data.append({
                "Drone ID": drone.drone_id,
                "Model": drone.model,
                "Status": drone.status.value,
                "Location": drone.current_location,
                "Weather Rating": drone.weather_rating,
                "Capabilities": ", ".join(drone.capabilities),
                "Battery Health": f"{drone.battery_health}%",
                "Current Assignment": drone.current_assignment or "None"
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        # Detailed view
        st.divider()
        selected_drone = st.selectbox(
            "Select drone for details:",
            [d.drone_id for d in filtered_drones]
        )
        
        if selected_drone:
            drone = next((d for d in filtered_drones if d.drone_id == selected_drone), None)
            if drone:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Drone ID:** {drone.drone_id}")
                    st.write(f"**Model:** {drone.model}")
                    st.write(f"**Status:** {drone.status.value}")
                    st.write(f"**Location:** {drone.current_location}")
                
                with col2:
                    st.write(f"**Weather Rating:** {drone.weather_rating}")
                    st.write(f"**Capabilities:** {', '.join(drone.capabilities)}")
                    st.write(f"**Battery Health:** {drone.battery_health}%")
                    st.write(f"**Max Flight Time:** {drone.max_flight_time} min")
                
                if drone.maintenance_due_date:
                    st.write(f"**Maintenance Due:** {drone.maintenance_due_date}")
    else:
        st.info("No drones match the selected filters.")


def show_missions_dashboard():
    """Display missions information"""
    st.subheader("📊 Missions Management")
    
    if not st.session_state.agent:
        st.error("Agent not initialized")
        return
    
    missions = st.session_state.agent.missions_list
    
    if missions:
        df_data = []
        for mission in missions:
            df_data.append({
                "Mission ID": mission.mission_id,
                "Project": mission.project_name,
                "Client": mission.client_name,
                "Location": mission.location,
                "Start Date": mission.start_date,
                "End Date": mission.end_date,
                "Budget (₹)": f"₹{mission.budget:.2f}",
                "Priority": mission.priority,
                "Status": mission.status,
                "Assigned Pilots": len(mission.assigned_pilots),
                "Assigned Drones": len(mission.assigned_drones)
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        # Detailed view
        st.divider()
        selected_mission = st.selectbox(
            "Select mission for details:",
            [m.mission_id for m in missions]
        )
        
        if selected_mission:
            mission = next((m for m in missions if m.mission_id == selected_mission), None)
            if mission:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Mission ID:** {mission.mission_id}")
                    st.write(f"**Project:** {mission.project_name}")
                    st.write(f"**Client:** {mission.client_name}")
                    st.write(f"**Location:** {mission.location}")
                    st.write(f"**Start Date:** {mission.start_date}")
                
                with col2:
                    st.write(f"**End Date:** {mission.end_date}")
                    st.write(f"**Priority:** {mission.priority}")
                    st.write(f"**Budget:** ₹{mission.budget:.2f}")
                    st.write(f"**Status:** {mission.status}")
                    st.write(f"**Expected Weather:** {mission.expected_weather}")
                
                st.write(f"**Required Skills:** {', '.join(mission.required_skills) or 'None'}")
                st.write(f"**Required Certifications:** {', '.join(mission.required_certifications) or 'None'}")
                st.write(f"**Assigned Pilots:** {', '.join(mission.assigned_pilots) or 'None'}")
                st.write(f"**Assigned Drones:** {', '.join(mission.assigned_drones) or 'None'}")
    else:
        st.info("No missions available.")


def show_operations_dashboard():
    """Display operations summary and conflict detection"""
    st.subheader("🔧 Operations Dashboard")
    
    if not st.session_state.agent:
        st.error("Agent not initialized")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    pilots = st.session_state.agent.pilots_list
    drones = st.session_state.agent.drones_list
    missions = st.session_state.agent.missions_list
    
    with col1:
        available_pilots = len([p for p in pilots if p.status == PilotStatus.AVAILABLE])
        st.metric("Available Pilots", available_pilots, f"of {len(pilots)}")
    
    with col2:
        available_drones = len([d for d in drones if d.status == DroneStatus.AVAILABLE])
        st.metric("Available Drones", available_drones, f"of {len(drones)}")
    
    with col3:
        active_missions = len([m for m in missions if m.status == "Active"])
        st.metric("Active Missions", active_missions, f"of {len(missions)}")
    
    with col4:
        on_mission = len([p for p in pilots if p.status == PilotStatus.ON_MISSION])
        st.metric("Pilots On Mission", on_mission)
    
    st.divider()
    
    # Conflict Detection
    st.subheader("⚠️ Conflict Detection")
    
    if st.button("🔍 Check for Conflicts", use_container_width=True):
        with st.spinner("Running conflict detection..."):
            try:
                conflicts_result = st.session_state.agent.rule_engine.detect_all_conflicts()
                
                if not conflicts_result.conflicts:
                    st.success("✓ No conflicts detected. All assignments are valid!")
                else:
                    # Display summary
                    st.warning(f"⚠️ {conflicts_result.summary}")
                    
                    # Group by severity
                    critical = [c for c in conflicts_result.conflicts if c.severity == "Critical"]
                    high = [c for c in conflicts_result.conflicts if c.severity == "High"]
                    warnings = [c for c in conflicts_result.conflicts if c.severity == "Warning"]
                    
                    if critical:
                        st.error(f"🔴 **{len(critical)} Critical Issue(s):**")
                        for conflict in critical:
                            st.error(f"- {conflict.affected_entity}: {conflict.description}")
                            if conflict.resolution_suggestions:
                                st.info(f"💡 Suggestion: {conflict.resolution_suggestions[0]}")
                    
                    if high:
                        st.warning(f"🟠 **{len(high)} High Priority Issue(s):**")
                        for conflict in high:
                            st.warning(f"- {conflict.affected_entity}: {conflict.description}")
                    
                    if warnings:
                        st.info(f"🟡 **{len(warnings)} Warning(s):**")
                        for conflict in warnings:
                            st.info(f"- {conflict.affected_entity}: {conflict.description}")
            except Exception as e:
                st.error(f"Error running conflict detection: {e}")
    
    st.divider()
    
    # Pilot Status Distribution
    st.subheader("📈 Pilot Status Distribution")
    
    status_counts = {}
    for pilot in pilots:
        status = pilot.status.value
        status_counts[status] = status_counts.get(status, 0) + 1
    
    if status_counts:
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(pd.DataFrame({
                "Status": list(status_counts.keys()),
                "Count": list(status_counts.values())
            }).set_index("Status"))
        
        with col2:
            st.write("**Status Breakdown:**")
            for status, count in status_counts.items():
                st.write(f"- {status}: {count}")
    
    st.divider()
    
    # Drone Status Distribution
    st.subheader("📈 Drone Status Distribution")
    
    drone_status_counts = {}
    for drone in drones:
        status = drone.status.value
        drone_status_counts[status] = drone_status_counts.get(status, 0) + 1
    
    if drone_status_counts:
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(pd.DataFrame({
                "Status": list(drone_status_counts.keys()),
                "Count": list(drone_status_counts.values())
            }).set_index("Status"))
        
        with col2:
            st.write("**Status Breakdown:**")
            for status, count in drone_status_counts.items():
                st.write(f"- {status}: {count}")


def show_help():
    """Display help and examples"""
    st.subheader("❓ Help & Examples")
    
    st.markdown("""
    ## 🤖 How to Use the Chatbot
    
    The Skylark Drones Operations Coordinator uses natural language understanding to help you manage drone operations.
    
    ### 📝 Available Commands
    
    #### Pilot Management
    - "Find pilots with survey skills"
    - "Show available pilots"
    - "Show pilots in bangalore"
    - "Find pilots with DGCA certification"
    - "Show pilots available on 2026-02-07"
    - "Show pilot assigned to mission PRJ001"
    
    #### Drone Management
    - "Find drones with thermal capability"
    - "Show drones in mumbai"
    - "Find drones with IP43 weather rating"
    - "Show all available drones"
    - "Find drones with RGB capability"
    
    #### Mission Management
    - "Calculate cost of mission PRJ001"
    - "Calculate cost of mission PRJ001 with pilot Arjun"
    - "Show pilots assigned to mission PRJ003"
    - "Check for conflicts"
    
    #### Operations
    - "Get operations summary"
    - "Show pilot availability"
    
    ### 💡 Query Tips
    
    - Use natural language - the AI understands context
    - Be specific with dates (YYYY-MM-DD format)
    - Mention pilot/drone/mission names clearly
    - Ask about specific attributes (skills, capabilities, weather ratings)
    
    ### 📊 Dashboard Features
    
    - **👥 Pilots:** View all pilots, filter by status/location/skill
    - **🛸 Drones:** View all drones, filter by status/location/capability
    - **📊 Missions:** View all missions with assigned resources
    - **🔧 Operations:** Monitor overall fleet status and conflicts
    
    ### ⚙️ Data Management
    
    - Click **🔄 Refresh Data** to sync from Google Sheets
    - Changes are persisted to Google Sheets automatically
    
    ### 🔍 Conflict Detection
    
    The system automatically detects:
    - Double bookings (same pilot/drone assigned to overlapping missions)
    - Skill/certification mismatches
    - Budget overruns
    - Weather incompatibility
    - Maintenance scheduling issues
    
    """)


if __name__ == "__main__":
    main()