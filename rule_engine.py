"""
Rule engine for Skylark Drones Operations Agent.
Implements conflict detection, validation, and business logic.
FIXED: Case-insensitive skill/cert matching
"""

import logging
from typing import List, Dict, Tuple, Optional
from datetime import date, datetime, timedelta

from schemas import (
    Pilot, Drone, Mission, Conflict, ConflictType, ConflictDetectionResult,
    CostEstimate, MissionCostBreakdown, PilotStatus, DroneStatus, WeatherCondition
)
from config import WEATHER_DRONE_COMPATIBILITY

logger = logging.getLogger(__name__)


class RuleEngine:
    """Handles all business logic and conflict detection"""

    def __init__(self, pilots: List[Pilot], drones: List[Drone], missions: List[Mission]):
        """Initialize rule engine with data"""
        self.pilots = {p.name: p for p in pilots}
        self.drones = {d.drone_id: d for d in drones}
        self.missions = {m.mission_id: m for m in missions}
        self.conflicts: List[Conflict] = []

    def detect_all_conflicts(self) -> ConflictDetectionResult:
        """Run all conflict detection rules"""
        self.conflicts = []
        
        # Run all detection methods
        for mission_id, mission in self.missions.items():
            self._detect_pilot_conflicts(mission)
            self._detect_drone_conflicts(mission)
            self._detect_budget_conflicts(mission)
            self._detect_location_conflicts(mission)
            self._detect_double_booking(mission)
        
        has_critical = any(c.severity == "Critical" for c in self.conflicts)
        summary = self._generate_summary()
        
        return ConflictDetectionResult(
            conflicts=self.conflicts,
            has_critical_issues=has_critical,
            summary=summary
        )

    def _detect_pilot_conflicts(self, mission: Mission):
        """Detect pilot-related conflicts"""
        for pilot_name in mission.assigned_pilots:
            if pilot_name not in self.pilots:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.PILOT_UNAVAILABLE,
                    severity="Critical",
                    affected_entity=pilot_name,
                    description=f"Pilot '{pilot_name}' not found in roster",
                    affected_missions=[mission.mission_id]
                ))
                continue
            
            pilot = self.pilots[pilot_name]
            
            # Check pilot availability
            if pilot.status == PilotStatus.ON_LEAVE:
                if self._date_overlaps(mission, pilot.availability_start, pilot.availability_end):
                    self.conflicts.append(Conflict(
                        conflict_type=ConflictType.PILOT_UNAVAILABLE,
                        severity="Critical",
                        affected_entity=pilot_name,
                        description=f"Pilot '{pilot_name}' is on leave during mission dates",
                        affected_missions=[mission.mission_id],
                        resolution_suggestions=[f"Reassign pilot or reschedule mission"]
                    ))
            
            if pilot.status == PilotStatus.UNAVAILABLE:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.PILOT_UNAVAILABLE,
                    severity="High",
                    affected_entity=pilot_name,
                    description=f"Pilot '{pilot_name}' marked as unavailable",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[f"Update pilot status or find replacement"]
                ))
            
            # Check skill requirements (case-insensitive)
            missing_skills = self._find_missing_items(mission.required_skills, pilot.skills)
            if missing_skills:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.SKILL_MISMATCH,
                    severity="High",
                    affected_entity=pilot_name,
                    description=f"Pilot missing skills: {', '.join(missing_skills)}",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[
                        f"Train pilot in {', '.join(missing_skills)} or reassign",
                        f"Find pilot with {', '.join(missing_skills)} skills"
                    ]
                ))
            
            # Check certification requirements (case-insensitive)
            missing_certs = self._find_missing_items(mission.required_certifications, pilot.certifications)
            if missing_certs:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.CERTIFICATION_MISSING,
                    severity="Critical",
                    affected_entity=pilot_name,
                    description=f"Pilot missing certifications: {', '.join(missing_certs)}",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[
                        f"Obtain {', '.join(missing_certs)} certification",
                        f"Find pilot with {', '.join(missing_certs)} certification"
                    ]
                ))

    def _detect_drone_conflicts(self, mission: Mission):
        """Detect drone-related conflicts"""
        for drone_id in mission.assigned_drones:
            if drone_id not in self.drones:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.DRONE_UNAVAILABLE,
                    severity="Critical",
                    affected_entity=drone_id,
                    description=f"Drone '{drone_id}' not found in fleet",
                    affected_missions=[mission.mission_id]
                ))
                continue
            
            drone = self.drones[drone_id]
            
            # Check drone status
            if drone.status == DroneStatus.MAINTENANCE:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.DRONE_MAINTENANCE,
                    severity="High",
                    affected_entity=drone_id,
                    description=f"Drone '{drone_id}' is in maintenance",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[f"Complete maintenance or use different drone"]
                ))
            
            if drone.status == DroneStatus.GROUNDED:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.DRONE_UNAVAILABLE,
                    severity="Critical",
                    affected_entity=drone_id,
                    description=f"Drone '{drone_id}' is grounded",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[f"Fix issues or use different drone"]
                ))
            
            # Check maintenance scheduling
            if drone.maintenance_due_date and mission.start_date >= drone.maintenance_due_date:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.DRONE_MAINTENANCE,
                    severity="High",
                    affected_entity=drone_id,
                    description=f"Drone '{drone_id}' maintenance due on {drone.maintenance_due_date}",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[f"Schedule maintenance after mission or use different drone"]
                ))
            
            # Check weather compatibility
            if not self._check_weather_compatibility(drone, mission.expected_weather):
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.WEATHER_INCOMPATIBILITY,
                    severity="Critical",
                    affected_entity=drone_id,
                    description=f"Drone '{drone_id}' not rated for {mission.expected_weather} conditions",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[f"Use weather-compatible drone or reschedule"]
                ))

    def _detect_budget_conflicts(self, mission: Mission):
        """Detect budget-related conflicts"""
        cost_breakdown = self.calculate_mission_costs(mission.mission_id)
        
        if cost_breakdown.total_estimated_cost > cost_breakdown.mission_budget:
            overrun = cost_breakdown.total_estimated_cost - cost_breakdown.mission_budget
            self.conflicts.append(Conflict(
                conflict_type=ConflictType.BUDGET_OVERRUN,
                severity="High",
                affected_entity=mission.mission_id,
                description=f"Mission costs (${cost_breakdown.total_estimated_cost:.2f}) exceed budget (${cost_breakdown.mission_budget:.2f}) by ${overrun:.2f}",
                affected_missions=[mission.mission_id],
                resolution_suggestions=[
                    f"Increase mission budget to ${cost_breakdown.total_estimated_cost:.2f}",
                    f"Reassign to less expensive pilots",
                    f"Reduce mission scope"
                ]
            ))

    def _detect_location_conflicts(self, mission: Mission):
        """Detect location mismatch conflicts"""
        for pilot_name in mission.assigned_pilots:
            if pilot_name not in self.pilots:
                continue
            
            pilot = self.pilots[pilot_name]
            if pilot.current_location != mission.location:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.LOCATION_MISMATCH,
                    severity="Warning",
                    affected_entity=pilot_name,
                    description=f"Pilot located in '{pilot.current_location}' but mission is in '{mission.location}'",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[
                        f"Factor in travel time/costs",
                        f"Use local pilot if available"
                    ]
                ))
        
        # Check drones location
        for drone_id in mission.assigned_drones:
            if drone_id not in self.drones:
                continue
            
            drone = self.drones[drone_id]
            if drone.current_location != mission.location:
                self.conflicts.append(Conflict(
                    conflict_type=ConflictType.LOCATION_MISMATCH,
                    severity="Warning",
                    affected_entity=drone_id,
                    description=f"Drone located in '{drone.current_location}' but mission is in '{mission.location}'",
                    affected_missions=[mission.mission_id],
                    resolution_suggestions=[
                        f"Arrange drone transportation",
                        f"Use local drone if available"
                    ]
                ))

    def _detect_double_booking(self, mission: Mission):
        """Detect double-booking conflicts for pilots and drones"""
        for pilot_name in mission.assigned_pilots:
            if pilot_name not in self.pilots:
                continue
            
            pilot = self.pilots[pilot_name]
            if pilot.current_assignment and pilot.current_assignment != mission.mission_id:
                if pilot.current_assignment in self.missions:
                    other_mission = self.missions[pilot.current_assignment]
                    if self._missions_overlap(mission, other_mission):
                        self.conflicts.append(Conflict(
                            conflict_type=ConflictType.DOUBLE_BOOKING,
                            severity="Critical",
                            affected_entity=pilot_name,
                            description=f"Pilot assigned to overlapping missions: {mission.mission_id} and {pilot.current_assignment}",
                            affected_missions=[mission.mission_id, pilot.current_assignment],
                            resolution_suggestions=[
                                f"Reassign one mission to different pilot",
                                f"Reschedule one mission"
                            ]
                        ))
        
        for drone_id in mission.assigned_drones:
            if drone_id not in self.drones:
                continue
            
            drone = self.drones[drone_id]
            if drone.current_assignment and drone.current_assignment != mission.mission_id:
                if drone.current_assignment in self.missions:
                    other_mission = self.missions[drone.current_assignment]
                    if self._missions_overlap(mission, other_mission):
                        self.conflicts.append(Conflict(
                            conflict_type=ConflictType.DOUBLE_BOOKING,
                            severity="Critical",
                            affected_entity=drone_id,
                            description=f"Drone assigned to overlapping missions: {mission.mission_id} and {drone.current_assignment}",
                            affected_missions=[mission.mission_id, drone.current_assignment],
                            resolution_suggestions=[
                                f"Reassign one mission to different drone",
                                f"Reschedule one mission"
                            ]
                        ))

    def find_available_pilots(self, mission: Mission, location_filter: bool = False) -> List[Tuple[Pilot, List[str]]]:
        """Find pilots available for mission. Returns list of (pilot, missing_items) tuples"""
        available = []
        
        for pilot in self.pilots.values():
            missing_items = []
            
            # Check status
            if pilot.status not in [PilotStatus.AVAILABLE, PilotStatus.ON_MISSION]:
                continue
            
            # Check location if filter enabled
            if location_filter and pilot.current_location != mission.location:
                missing_items.append(f"location ({pilot.current_location} vs {mission.location})")
            
            # Check certifications (case-insensitive)
            missing_certs = self._find_missing_items(mission.required_certifications, pilot.certifications)
            if missing_certs:
                missing_items.append(f"certifications: {', '.join(missing_certs)}")
            
            # Check skills (case-insensitive)
            missing_skills = self._find_missing_items(mission.required_skills, pilot.skills)
            if missing_skills:
                missing_items.append(f"skills: {', '.join(missing_skills)}")
            
            # Add to available if no critical missing items
            if not missing_certs and not missing_skills:
                available.append((pilot, missing_items))
        
        return sorted(available, key=lambda x: len(x[1]))

    def find_compatible_drones(self, mission: Mission, location_filter: bool = False) -> List[Tuple[Drone, List[str]]]:
        """Find drones compatible with mission. Returns list of (drone, missing_items) tuples"""
        available = []
        
        for drone in self.drones.values():
            missing_items = []
            
            # Check status
            if drone.status not in [DroneStatus.AVAILABLE, DroneStatus.DEPLOYED]:
                continue
            
            # Check maintenance
            if drone.maintenance_due_date and mission.start_date >= drone.maintenance_due_date:
                missing_items.append(f"maintenance due")
            
            # Check location if filter enabled
            if location_filter and drone.current_location != mission.location:
                missing_items.append(f"location ({drone.current_location} vs {mission.location})")
            
            # Check drone capability requirements
            if mission.drone_requirements:
                missing_caps = self._find_missing_items(mission.drone_requirements, drone.capabilities)
                if missing_caps:
                    missing_items.append(f"capabilities: {', '.join(missing_caps)}")
            
            # Check weather compatibility (critical)
            if not self._check_weather_compatibility(drone, mission.expected_weather):
                continue  # Skip weather-incompatible drones entirely
            
            available.append((drone, missing_items))
        
        return sorted(available, key=lambda x: len(x[1]))

    def calculate_mission_costs(self, mission_id: str) -> MissionCostBreakdown:
        """Calculate total cost for a mission"""
        if mission_id not in self.missions:
            raise ValueError(f"Mission {mission_id} not found")
        
        mission = self.missions[mission_id]
        mission_days = (mission.end_date - mission.start_date).days + 1
        
        pilot_costs = []
        total_pilots_cost = 0
        
        for pilot_name in mission.assigned_pilots:
            if pilot_name not in self.pilots:
                continue
            
            pilot = self.pilots[pilot_name]
            estimated_hours = mission_days * 8  # Assume 8-hour workdays
            estimated_cost = pilot.hourly_rate * estimated_hours
            
            pilot_costs.append(CostEstimate(
                pilot_name=pilot_name,
                hourly_rate=pilot.hourly_rate,
                estimated_hours=estimated_hours,
                estimated_cost=estimated_cost,
                mission_budget=mission.budget,
                within_budget=estimated_cost <= mission.budget
            ))
            
            total_pilots_cost += estimated_cost
        
        # Calculate drone costs (simplified - 0 for now)
        total_drones_cost = 0
        
        return MissionCostBreakdown(
            mission_id=mission_id,
            pilot_costs=pilot_costs,
            total_pilots_cost=total_pilots_cost,
            total_drones_cost=total_drones_cost,
            total_estimated_cost=total_pilots_cost + total_drones_cost,
            mission_budget=mission.budget,
            within_budget=(total_pilots_cost + total_drones_cost) <= mission.budget,
            warnings=[]
        )

    def get_pilot_availability_summary(self) -> Dict[str, Dict]:
        """Get summary of pilot availability"""
        summary = {}
        
        for pilot_name, pilot in self.pilots.items():
            available_for = []
            
            # Find missions this pilot could support
            for mission_id, mission in self.missions.items():
                missing_skills = self._find_missing_items(mission.required_skills, pilot.skills)
                missing_certs = self._find_missing_items(mission.required_certifications, pilot.certifications)
                
                if not missing_skills and not missing_certs:
                    available_for.append(mission_id)
            
            summary[pilot_name] = {
                "status": pilot.status.value,
                "location": pilot.current_location,
                "hourly_rate": pilot.hourly_rate,
                "skills": pilot.skills,
                "available_for": available_for
            }
        
        return summary

    # ============= HELPER METHODS =============

    def _find_missing_items(self, required: List[str], available: List[str]) -> List[str]:
        """
        Find missing items from available list (case-insensitive).
        Example: required=['Mapping', 'Survey'], available=['mapping', 'thermal']
        Returns: ['Survey']
        """
        if not required:
            return []
        
        # Normalize to lowercase for comparison
        available_lower = {item.lower(): item for item in available}
        required_lower = set(item.lower() for item in required)
        
        # Find missing
        missing_lower = required_lower - set(available_lower.keys())
        
        # Return original required format for missing items
        return [item for item in required if item.lower() in missing_lower]

    def _check_weather_compatibility(self, drone: Drone, weather: str) -> bool:
        """Check if drone is compatible with weather conditions"""
        compatible_ratings = WEATHER_DRONE_COMPATIBILITY.get(weather, ["Standard"])
        return drone.weather_rating in compatible_ratings

    def _missions_overlap(self, mission1: Mission, mission2: Mission) -> bool:
        """Check if two missions have overlapping dates"""
        return not (mission1.end_date < mission2.start_date or mission2.end_date < mission1.start_date)

    def _date_overlaps(self, mission: Mission, avail_start: Optional[date], avail_end: Optional[date]) -> bool:
        """Check if mission dates overlap with availability dates"""
        if not avail_start or not avail_end:
            return False
        return not (mission.end_date < avail_start or avail_end < mission.start_date)

    def _generate_summary(self) -> str:
        """Generate conflict summary text"""
        if not self.conflicts:
            return "No conflicts detected. All assignments are valid."
        
        critical_count = len([c for c in self.conflicts if c.severity == "Critical"])
        high_count = len([c for c in self.conflicts if c.severity == "High"])
        warning_count = len([c for c in self.conflicts if c.severity == "Warning"])
        
        summary = f"Found {len(self.conflicts)} conflict(s): "
        parts = []
        
        if critical_count:
            parts.append(f"{critical_count} Critical")
        if high_count:
            parts.append(f"{high_count} High")
        if warning_count:
            parts.append(f"{warning_count} Warning")
        
        summary += ", ".join(parts)
        return summary