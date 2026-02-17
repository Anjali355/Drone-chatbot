"""
Main agent module for Skylark Drones Operations Coordinator.
Orchestrates query handling, business logic, and Google Sheets sync.
Designed for modular LangGraph integration.
"""

import logging
import sys
from datetime import date, datetime
from typing import Optional, Dict, Any

from sheet_service import SheetService
from rule_engine import RuleEngine
from llm_parser import LLMParser
from schemas import PilotStatus, DroneStatus, Mission

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DronesOperationsAgent:
    """Main agent orchestrator"""

    def __init__(self):
        """Initialize all components"""
        logger.info("🚀 Initializing Skylark Drones Operations Agent...")
        
        try:
            # Initialize services
            self.sheet_service = SheetService()
            self.llm_parser = LLMParser()
            
            # Load initial data
            self.refresh_data()
            
            logger.info("✓ Agent initialized successfully")
        except Exception as e:
            logger.error(f"✗ Failed to initialize agent: {e}")
            raise

    def refresh_data(self):
        """Sync all data from Google Sheets and initialize rule engine"""
        logger.info("📊 Syncing data from Google Sheets...")
        
        pilots, drones, missions = self.sheet_service.sync_data()
        self.rule_engine = RuleEngine(pilots, drones, missions)
        self.pilots_list = pilots
        self.drones_list = drones
        self.missions_list = missions
        
        logger.info(f"✓ Data synced: {len(pilots)} pilots, {len(drones)} drones, {len(missions)} missions")

    def process_query(self, user_query: str) -> str:
        """
        Main entry point for processing user queries.
        Parses natural language, executes appropriate actions, returns formatted response.
        """
        logger.info(f"📝 Processing query: {user_query}")
        
        # Parse the natural language query
        parsed_request = self.llm_parser.parse_query(user_query)
        query_type = parsed_request.query_type
        params = parsed_request.parameters
        
        try:
            # Route to appropriate handler
            if query_type == "find_pilots":
                return self._handle_find_pilots(params)
            
            elif query_type == "find_drones":
                return self._handle_find_drones(params)
            
            elif query_type == "check_conflicts":
                return self._handle_check_conflicts(params)
            
            elif query_type == "calculate_costs":
                return self._handle_calculate_costs(params)
            
            elif query_type == "assign_pilot":
                return self._handle_assign_pilot(params)
            
            elif query_type == "assign_drone":
                return self._handle_assign_drone(params)
            
            elif query_type == "update_status":
                return self._handle_update_status(params)
            
            elif query_type == "get_availability":
                return self._handle_get_availability(params)
            
            elif query_type == "get_summary":
                return self._handle_get_summary(params)
            
            else:
                return self._handle_unknown(query_type, user_query)
        
        except Exception as e:
            logger.error(f"✗ Error processing query: {e}")
            return f"Error: {str(e)}"

    # ============= QUERY HANDLERS =============

    def _handle_find_pilots(self, params: Dict[str, Any]) -> str:
        """Find pilots matching criteria"""
        mission_id = params.get("mission_id")
        skill = params.get("skill")
        certification = params.get("certification")
        location = params.get("location")
        date_str = params.get("date")
        
        # If checking availability on specific date
        if date_str:
            try:
                from datetime import datetime
                check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return f"Invalid date format. Use YYYY-MM-DD (e.g., 2026-02-07)"
            
            available_on_date = []
            for pilot in self.pilots_list:
                if pilot.status == PilotStatus.AVAILABLE:
                    available_on_date.append(pilot)
                elif pilot.status == PilotStatus.ON_LEAVE:
                    if pilot.availability_start and pilot.availability_end:
                        if not (check_date >= pilot.availability_start and check_date <= pilot.availability_end):
                            available_on_date.append(pilot)
            
            if not available_on_date:
                return f"No pilots available on {date_str}"
            
            matching = [(p, []) for p in available_on_date]
            response = f"Pilots available on {date_str}:\n"
            response += self.llm_parser.format_pilot_list(matching)
            return response
        
        # If mission_id provided - show who is assigned OR find available pilots for mission
        if mission_id:
            mission = self.rule_engine.missions.get(mission_id)
            if not mission:
                return f"Mission {mission_id} not found."
            
            # If mission has assigned pilots, show them
            if mission.assigned_pilots:
                response = f"Pilots assigned to mission {mission_id}:\n"
                assigned = [self.rule_engine.pilots[name] for name in mission.assigned_pilots if name in self.rule_engine.pilots]
                matching = [(p, []) for p in assigned]
                response += self.llm_parser.format_pilot_list(matching)
                return response
            
            # Otherwise show available pilots for this mission
            matching_pilots = self.rule_engine.find_available_pilots(mission, location_filter=bool(location))
            
            if not matching_pilots:
                return f"No pilots available for mission {mission_id}"
            
            response = f"Pilots available for mission {mission_id}:\n"
            response += self.llm_parser.format_pilot_list(matching_pilots)
            
            return response
        
        # Use case-insensitive skill/certification matching
        elif skill or certification or location:
            skill_lower = skill.lower() if skill else None
            cert_lower = certification.lower() if certification else None
            location_lower = location.lower() if location else None
            
            filtered = []
            for pilot in self.pilots_list:
                if skill_lower:
                    if not any(s.lower() == skill_lower for s in pilot.skills):
                        continue
                
                if cert_lower:
                    if not any(c.lower() == cert_lower for c in pilot.certifications):
                        continue
                
                if location_lower:
                    if pilot.current_location.lower() != location_lower:
                        continue
                
                filtered.append(pilot)
            
            if not filtered:
                return f"No pilots found matching: skill={skill}, cert={certification}, location={location}"
            
            matching = [(p, []) for p in filtered]
            return self.llm_parser.format_pilot_list(matching)
        
        else:
            # Return all available pilots
            available = [(p, []) for p in self.pilots_list if p.status == PilotStatus.AVAILABLE]
            return self.llm_parser.format_pilot_list(available)


    def _handle_find_drones(self, params: Dict[str, Any]) -> str:
        """Find drones matching criteria"""
        mission_id = params.get("mission_id")
        location = params.get("location")
        capability = params.get("capability")  # Add this
        weather_rating = params.get("weather_rating")  # Add this
        
        if mission_id:
            mission = self.rule_engine.missions.get(mission_id)
            if not mission:
                return f"Mission {mission_id} not found."
            
            matching_drones = self.rule_engine.find_compatible_drones(mission, location_filter=bool(location))
            
            response = f"Drones compatible with mission {mission_id}:\n"
            response += self.llm_parser.format_drone_list(matching_drones)
            
            return response
        
        elif capability or weather_rating or location:
            # Normalize search terms to lowercase
            capability_lower = capability.lower() if capability else None
            weather_lower = weather_rating.lower() if weather_rating else None
            location_lower = location.lower() if location else None
            
            filtered = []
            for drone in self.drones_list:
                # Case-insensitive capability matching
                if capability_lower:
                    if not any(c.lower() == capability_lower for c in drone.capabilities):
                        continue
                
                # Case-insensitive weather rating matching
                if weather_lower:
                    if drone.weather_rating.lower() != weather_lower:
                        continue
                
                # Case-insensitive location matching
                if location_lower:
                    if drone.current_location.lower() != location_lower:
                        continue
                
                filtered.append(drone)
            
            if not filtered:
                return f"No drones found matching: capability={capability}, weather_rating={weather_rating}, location={location}"
            
            matching = [(d, []) for d in filtered]
            return self.llm_parser.format_drone_list(matching)
        
        else:
            # Return all available drones
            available = [(d, []) for d in self.drones_list if d.status == DroneStatus.AVAILABLE]
            return self.llm_parser.format_drone_list(available)

    def _handle_check_conflicts(self, params: Dict[str, Any]) -> str:
        """Detect all conflicts in current assignments"""
        mission_id = params.get("mission_id")
        
        if mission_id:
            mission = self.rule_engine.missions.get(mission_id)
            if not mission:
                return f"Mission {mission_id} not found."
            
            # Run conflict detection
            result = self.rule_engine.detect_all_conflicts()
            
            # Filter to specific mission
            mission_conflicts = [c for c in result.conflicts if mission_id in c.affected_missions]
            
            if not mission_conflicts:
                return f"✓ No conflicts detected for mission {mission_id}"
            
            # Generate report
            report = f"CONFLICTS FOR MISSION {mission_id}\n{'='*60}\n\n"
            for conflict in mission_conflicts:
                report += f"{conflict.severity}: {conflict.description}\n"
                if conflict.resolution_suggestions:
                    report += "  Suggestions:\n"
                    for sug in conflict.resolution_suggestions[:2]:
                        report += f"    - {sug}\n"
                report += "\n"
            
            return report
        
        else:
            # Check all conflicts
            result = self.rule_engine.detect_all_conflicts()
            return self.llm_parser.generate_conflict_report(result)

    def _handle_calculate_costs(self, params: Dict[str, Any]) -> str:
        """Calculate mission costs - with optional hypothetical pilot assignment"""
        mission_id = params.get("mission_id")
        pilot_name = params.get("pilot_name")  # Hypothetical pilot to check cost
        
        if not mission_id:
            return "Mission ID required for cost calculation."
        
        if mission_id not in self.rule_engine.missions:
            return f"Mission {mission_id} not found."
        
        mission = self.rule_engine.missions[mission_id]
        
        # If pilot_name provided, calculate cost as if that pilot is assigned
        if pilot_name:
            if pilot_name not in self.rule_engine.pilots:
                return f"Pilot '{pilot_name}' not found."
            
            pilot = self.rule_engine.pilots[pilot_name]
            mission_days = (mission.end_date - mission.start_date).days + 1
            estimated_hours = mission_days * 8
            estimated_cost = pilot.hourly_rate * estimated_hours
            
            response = f"HYPOTHETICAL COST - Mission {mission_id} with pilot {pilot_name}\n"
            response += f"{'='*60}\n"
            response += f"Mission: {mission.project_name}\n"
            response += f"Client: {mission.client_name}\n"
            response += f"Duration: {mission_days} days ({estimated_hours} hours)\n"
            response += f"Pilot: {pilot_name}\n"
            response += f"Hourly Rate: ₹{pilot.hourly_rate:.2f}/hour\n"
            response += f"\nCalculation:\n"
            response += f"  {mission_days} days × 8 hours/day × ₹{pilot.hourly_rate:.2f}/hour\n"
            response += f"  = {estimated_hours} hours × ₹{pilot.hourly_rate:.2f}\n"
            response += f"  = ₹{estimated_cost:.2f}\n\n"
            response += f"Mission Budget: ₹{mission.budget:.2f}\n"
            
            if estimated_cost <= mission.budget:
                remaining = mission.budget - estimated_cost
                response += f"✓ WITHIN BUDGET: ₹{remaining:.2f} remaining\n"
            else:
                overrun = estimated_cost - mission.budget
                response += f"✗ BUDGET OVERRUN: ₹{overrun:.2f} over budget\n"
            
            return response
        
        # If no specific pilot, calculate for currently assigned pilots
        else:
            cost_breakdown = self.rule_engine.calculate_mission_costs(mission_id)
            return self.llm_parser.generate_cost_report(cost_breakdown)

    def _handle_assign_pilot(self, params: Dict[str, Any]) -> str:
        """Assign a pilot to a mission"""
        pilot_name = params.get("pilot_name")
        mission_id = params.get("mission_id")
        
        if not pilot_name or not mission_id:
            return "Pilot name and mission ID required."
        
        if pilot_name not in self.rule_engine.pilots:
            return f"Pilot '{pilot_name}' not found."
        
        if mission_id not in self.rule_engine.missions:
            return f"Mission {mission_id} not found."
        
        mission = self.rule_engine.missions[mission_id]
        
        # Check for conflicts
        conflicts = self.rule_engine.detect_all_conflicts()
        mission_conflicts = [c for c in conflicts.conflicts if mission_id in c.affected_missions]
        
        # Try assignment
        if pilot_name not in mission.assigned_pilots:
            mission.assigned_pilots.append(pilot_name)
            
            # Update Google Sheets
            if self.sheet_service.update_pilot_assignment(pilot_name, mission_id):
                if self.sheet_service.update_pilot_status(pilot_name, PilotStatus.ON_MISSION):
                    response = f"✓ Pilot '{pilot_name}' assigned to mission {mission_id}\n"
                    
                    if mission_conflicts:
                        response += f"\n⚠️  {len(mission_conflicts)} conflicts detected:\n"
                        for conflict in mission_conflicts[:3]:
                            response += f"  - {conflict.description}\n"
                    
                    return response
        
        return f"Could not assign pilot '{pilot_name}' to mission {mission_id}"

    def _handle_assign_drone(self, params: Dict[str, Any]) -> str:
        """Assign a drone to a mission"""
        drone_id = params.get("drone_id")
        mission_id = params.get("mission_id")
        
        if not drone_id or not mission_id:
            return "Drone ID and mission ID required."
        
        if drone_id not in self.rule_engine.drones:
            return f"Drone '{drone_id}' not found."
        
        if mission_id not in self.rule_engine.missions:
            return f"Mission {mission_id} not found."
        
        mission = self.rule_engine.missions[mission_id]
        drone = self.rule_engine.drones[drone_id]
        
        # Check weather compatibility
        if not self.rule_engine._check_weather_compatibility(drone, mission.expected_weather):
            return f"✗ Drone {drone_id} is not rated for {mission.expected_weather} conditions"
        
        if drone_id not in mission.assigned_drones:
            mission.assigned_drones.append(drone_id)
            
            if self.sheet_service.update_drone_assignment(drone_id, mission_id):
                if self.sheet_service.update_drone_status(drone_id, DroneStatus.DEPLOYED):
                    return f"✓ Drone '{drone_id}' assigned to mission {mission_id}"
        
        return f"Could not assign drone '{drone_id}' to mission {mission_id}"

    def _handle_update_status(self, params: Dict[str, Any]) -> str:
        """Update pilot or drone status"""
        entity_type = params.get("entity_type", "pilot")
        entity_name = params.get("pilot_name") or params.get("drone_id")
        new_status = params.get("status")
        reason = params.get("reason", "")
        
        if not entity_name or not new_status:
            return "Entity name and status required."
        
        if entity_type == "pilot":
            try:
                status = PilotStatus(new_status)
                if self.sheet_service.update_pilot_status(entity_name, status):
                    msg = f"✓ Pilot '{entity_name}' status updated to {new_status}"
                    if reason:
                        msg += f"\nReason: {reason}"
                    return msg
            except ValueError:
                return f"Invalid pilot status: {new_status}"
        
        elif entity_type == "drone":
            try:
                status = DroneStatus(new_status)
                if self.sheet_service.update_drone_status(entity_name, status):
                    msg = f"✓ Drone '{entity_name}' status updated to {new_status}"
                    if reason:
                        msg += f"\nReason: {reason}"
                    return msg
            except ValueError:
                return f"Invalid drone status: {new_status}"
        
        return f"Could not update status for {entity_name}"

    def _handle_get_availability(self, params: Dict[str, Any]) -> str:
        """Get pilot availability summary"""
        availability = self.rule_engine.get_pilot_availability_summary()
        return self.llm_parser.generate_availability_report(availability)

    def _handle_get_summary(self, params: Dict[str, Any]) -> str:
        """Get overall operations summary"""
        summary = f"""
OPERATIONS SUMMARY
{'='*60}

Pilots: {len(self.pilots_list)} total
  - Available: {len([p for p in self.pilots_list if p.status == PilotStatus.AVAILABLE])}
  - On Leave: {len([p for p in self.pilots_list if p.status == PilotStatus.ON_LEAVE])}
  - On Mission: {len([p for p in self.pilots_list if p.status == PilotStatus.ON_MISSION])}

Drones: {len(self.drones_list)} total
  - Available: {len([d for d in self.drones_list if d.status == DroneStatus.AVAILABLE])}
  - Deployed: {len([d for d in self.drones_list if d.status == DroneStatus.DEPLOYED])}
  - Maintenance: {len([d for d in self.drones_list if d.status == DroneStatus.MAINTENANCE])}

Missions: {len(self.missions_list)} total
  - Planned: {len([m for m in self.missions_list if m.status == 'Planned'])}
  - Active: {len([m for m in self.missions_list if m.status == 'Active'])}
  - Completed: {len([m for m in self.missions_list if m.status == 'Completed'])}

CONFLICTS:
"""
        conflicts = self.rule_engine.detect_all_conflicts()
        summary += conflicts.summary
        
        return summary

    def _handle_unknown(self, query_type: str, original_query: str) -> str:
        """Handle unknown query types"""
        return f"""
I couldn't determine the query type. Please try one of these formats:

1. Find Pilots: "Find available pilots for mission PRJ001" or "Show pilots with surveying skills"
2. Find Drones: "Find available drones for mission PRJ001" or "Show drones rated for rainy weather"
3. Check Conflicts: "Check for conflicts" or "Show conflicts for mission PRJ001"
4. Calculate Costs: "Calculate costs for mission PRJ001 with Arjun as pilot"
5. Assign: "Assign pilot John to mission PRJ001" or "Assign drone D001 to mission PRJ001"
6. Update Status: "Mark Sneha as on leave" or "Set drone D002 to maintenance"
7. Availability: "Show pilot availability on 2026-02-07"
8. Summary: "Get operations summary"

Your query: "{original_query}"
"""

    # ============= INTERACTIVE MODE =============

    def run_interactive(self):
        """Run agent in interactive mode"""
        print("\n" + "="*60)
        print("🚁 SKYLARK DRONES OPERATIONS COORDINATOR")
        print("="*60)
        print("Natural language interface for drone operations management")
        print("\nType 'help' for examples, 'refresh' to sync data, or 'quit' to exit\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == "quit":
                    print("Goodbye! ✈️")
                    break
                
                if user_input.lower() == "refresh":
                    self.refresh_data()
                    print("✓ Data refreshed from Google Sheets\n")
                    continue
                
                if user_input.lower() == "help":
                    print(self._handle_unknown("", ""))
                    continue
                
                # Process query
                response = self.process_query(user_input)
                print(f"\nAgent: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! ✈️")
                break
            except Exception as e:
                print(f"Error: {e}\n")


def main():
    """Main entry point"""
    try:
        agent = DronesOperationsAgent()
        agent.run_interactive()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()