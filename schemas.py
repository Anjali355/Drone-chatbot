"""
Data schemas for Skylark Drones Operations Agent.
Defines Pydantic models for type safety and validation.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum


class PilotStatus(str, Enum):
    """Enum for pilot availability status"""
    AVAILABLE = "Available"
    ON_LEAVE = "On Leave"
    UNAVAILABLE = "Unavailable"
    ON_MISSION = "On Mission"


class DroneStatus(str, Enum):
    """Enum for drone status"""
    AVAILABLE = "Available"
    DEPLOYED = "Deployed"
    MAINTENANCE = "Maintenance"
    GROUNDED = "Grounded"


class WeatherCondition(str, Enum):
    """Enum for weather conditions"""
    CLEAR = "Clear"
    CLOUDY = "Cloudy"
    RAINY = "Rainy"
    STORMY = "Stormy"
    FOGGY = "Foggy"


# ============= PILOT MODELS =============
class Pilot(BaseModel):
    """Represents a drone pilot"""
    name: str = Field(..., description="Pilot's full name")
    skills: List[str] = Field(default_factory=list, description="List of skills")
    certifications: List[str] = Field(default_factory=list, description="List of certifications")
    drone_experience_hours: int = Field(default=0, description="Total flight hours")
    current_location: str = Field(..., description="Current location/base")
    current_assignment: Optional[str] = Field(default=None, description="Current project ID if assigned")
    status: PilotStatus = Field(default=PilotStatus.AVAILABLE, description="Current availability status")
    availability_start: Optional[date] = Field(default=None, description="When pilot becomes available")
    availability_end: Optional[date] = Field(default=None, description="When pilot goes on leave")
    hourly_rate: float = Field(default=75.0, description="Hourly rate in USD")
    email: Optional[str] = Field(default=None, description="Pilot's email")
    phone: Optional[str] = Field(default=None, description="Pilot's phone number")

    @validator("drone_experience_hours")
    def validate_experience(cls, v):
        if v < 0:
            raise ValueError("Experience hours cannot be negative")
        return v

    @validator("hourly_rate")
    def validate_rate(cls, v):
        if v <= 0:
            raise ValueError("Hourly rate must be positive")
        return v


class PilotAssignment(BaseModel):
    """Represents a pilot assigned to a mission"""
    pilot_name: str
    mission_id: str
    start_date: date
    end_date: date
    role: Optional[str] = None
    estimated_hours: float
    assigned_drone: Optional[str] = None


# ============= DRONE MODELS =============
class Drone(BaseModel):
    """Represents a drone in the fleet"""
    drone_id: str = Field(..., description="Unique drone identifier")
    model: str = Field(..., description="Drone model name")
    capabilities: List[str] = Field(default_factory=list, description="List of capabilities")
    weather_rating: str = Field(default="Standard", description="Weather resistance rating")
    current_assignment: Optional[str] = Field(default=None, description="Current mission ID if deployed")
    status: DroneStatus = Field(default=DroneStatus.AVAILABLE, description="Current status")
    current_location: str = Field(..., description="Current location")
    maintenance_due_date: Optional[date] = Field(default=None, description="Next maintenance date")
    max_flight_time: int = Field(default=30, description="Max flight time in minutes")
    purchase_date: Optional[date] = Field(default=None, description="When drone was purchased")
    battery_health: Optional[int] = Field(default=100, description="Battery health percentage")
    notes: Optional[str] = Field(default=None, description="Additional notes")

    @validator("weather_rating")
    def validate_weather_rating(cls, v):
        # Accept full weather ratings from CSV and extract base rating
        # E.g., "IP43 (Rain)" → "IP43"
        v = str(v).strip()
        
        # Extract base rating (before parenthesis if exists)
        if "(" in v:
            base_rating = v.split("(")[0].strip()
        else:
            base_rating = v
        
        # Map common variants to valid ratings
        rating_map = {
            "Standard": "Standard",
            "IP43": "IP43",
            "IP67": "IP67",
            "IP43 (Rain)": "IP43",
            "IP67 (Heavy Rain)": "IP67",
            "None (Clear Sky Only)": "Standard",
            "None": "Standard",
        }
        
        # Check if exact match exists
        if v in rating_map:
            return rating_map[v]
        
        # Check if base rating is valid
        if base_rating in ["Standard", "IP43", "IP67"]:
            return base_rating
        
        # Default to Standard if unrecognized
        return "Standard"

    @validator("battery_health")
    def validate_battery(cls, v):
        if v is not None and not (0 <= v <= 100):
            raise ValueError("Battery health must be between 0 and 100")
        return v


class DroneAssignment(BaseModel):
    """Represents a drone assigned to a mission"""
    drone_id: str
    mission_id: str
    start_date: date
    end_date: date
    expected_weather: WeatherCondition = WeatherCondition.CLEAR


# ============= MISSION MODELS =============
class Mission(BaseModel):
    """Represents a client project/mission"""
    mission_id: str = Field(..., description="Unique mission identifier")
    client_name: str = Field(..., description="Client company name")
    project_name: str = Field(..., description="Project name")
    location: str = Field(..., description="Mission location")
    required_skills: List[str] = Field(default_factory=list, description="Required pilot skills")
    required_certifications: List[str] = Field(default_factory=list, description="Required certifications")
    start_date: date = Field(..., description="Mission start date")
    end_date: date = Field(..., description="Mission end date")
    priority: str = Field(default="Medium", description="Priority level")
    budget: float = Field(..., description="Total budget in USD")
    drone_requirements: Optional[List[str]] = Field(default=None, description="Required drone capabilities")
    expected_weather: WeatherCondition = Field(default=WeatherCondition.CLEAR, description="Expected weather")
    assigned_pilots: List[str] = Field(default_factory=list, description="Assigned pilot names")
    assigned_drones: List[str] = Field(default_factory=list, description="Assigned drone IDs")
    status: str = Field(default="Planned", description="Mission status")

    @validator("budget")
    def validate_budget(cls, v):
        if v <= 0:
            raise ValueError("Budget must be positive")
        return v

    @validator("start_date", "end_date", pre=True)
    def parse_dates(cls, v):
        if isinstance(v, str):
            return datetime.strptime(v, "%Y-%m-%d").date()
        return v


# ============= CONFLICT MODELS =============
class ConflictType(str, Enum):
    """Types of conflicts that can be detected"""
    DOUBLE_BOOKING = "Double Booking"
    SKILL_MISMATCH = "Skill Mismatch"
    CERTIFICATION_MISSING = "Missing Certification"
    BUDGET_OVERRUN = "Budget Overrun"
    LOCATION_MISMATCH = "Location Mismatch"
    WEATHER_INCOMPATIBILITY = "Weather Incompatibility"
    DRONE_MAINTENANCE = "Drone In Maintenance"
    PILOT_UNAVAILABLE = "Pilot Unavailable"


class Conflict(BaseModel):
    """Represents a detected conflict"""
    conflict_type: ConflictType
    severity: str = Field(default="Warning", description="Severity level")
    affected_entity: str = Field(..., description="Name of pilot/drone/mission affected")
    description: str = Field(..., description="Detailed conflict description")
    affected_missions: List[str] = Field(default_factory=list, description="Missions involved")
    resolution_suggestions: Optional[List[str]] = Field(default=None, description="Suggested fixes")
    timestamp: datetime = Field(default_factory=datetime.now)


# ============= QUERY/RESPONSE MODELS =============
class QueryRequest(BaseModel):
    """Request model for agent queries"""
    query_type: str = Field(..., description="Type of query")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AssignmentResult(BaseModel):
    """Result of an assignment operation"""
    success: bool
    message: str
    conflicts_detected: List[Conflict] = Field(default_factory=list)
    assignment_id: Optional[str] = None


class ConflictDetectionResult(BaseModel):
    """Result of conflict detection"""
    conflicts: List[Conflict] = Field(default_factory=list)
    has_critical_issues: bool
    summary: str


# ============= COST MODELS =============
class CostEstimate(BaseModel):
    """Cost estimate for a mission"""
    pilot_name: str
    hourly_rate: float
    estimated_hours: float
    estimated_cost: float
    mission_budget: float
    within_budget: bool

    @validator("estimated_cost", pre=True, always=True)
    def calculate_cost(cls, v, values):
        if "hourly_rate" in values and "estimated_hours" in values:
            return values["hourly_rate"] * values["estimated_hours"]
        return v


class MissionCostBreakdown(BaseModel):
    """Complete cost breakdown for a mission"""
    mission_id: str
    total_pilots_cost: float
    total_drones_cost: float = 0.0
    total_estimated_cost: float
    mission_budget: float
    within_budget: bool
    pilot_costs: List[CostEstimate] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)