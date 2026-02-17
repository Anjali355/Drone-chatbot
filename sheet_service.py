"""
Google Sheets service - works on local and Streamlit Cloud
"""

import logging
from typing import List, Dict, Any, Optional
import gspread
from datetime import date, datetime
import os

from schemas import Pilot, Drone, Mission, PilotStatus, DroneStatus

logger = logging.getLogger(__name__)


class SheetService:
    """Handles all Google Sheets interactions"""

    def __init__(self):
        """Initialize Google Sheets client"""
        try:
            from config import USE_STREAMLIT_SECRETS, GOOGLE_SHEETS_ID, GOOGLE_CREDENTIALS_PATH, SHEET_NAMES
            
            logger.info("Initializing Google Sheets...")
            
            if USE_STREAMLIT_SECRETS:
                # Streamlit Cloud - use secrets
                logger.info("Loading credentials from Streamlit secrets...")
                try:
                    import streamlit as st
                    from google.oauth2.service_account import Credentials
                    
                    creds_dict = dict(st.secrets["google_credentials"])
                    self.credentials = Credentials.from_service_account_info(
                        creds_dict,
                        scopes=["https://www.googleapis.com/auth/spreadsheets"]
                    )
                    logger.info("✓ Credentials loaded from Streamlit secrets")
                except Exception as e:
                    logger.error(f"Failed to load Streamlit secrets: {e}")
                    raise
            else:
                # Local - use credentials.json
                logger.info("Loading credentials from credentials.json...")
                
                if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
                    raise FileNotFoundError(f"credentials.json not found at {GOOGLE_CREDENTIALS_PATH}")
                
                from google.oauth2.service_account import Credentials
                self.credentials = Credentials.from_service_account_file(
                    GOOGLE_CREDENTIALS_PATH,
                    scopes=["https://www.googleapis.com/auth/spreadsheets"]
                )
                logger.info("✓ Credentials loaded from local file")
            
            # Authorize gspread (NO PROXIES!)
            self.client = gspread.authorize(self.credentials)
            self.sheet = self.client.open_by_key(GOOGLE_SHEETS_ID)
            self.sheet_names = SHEET_NAMES
            
            logger.info("✓ Google Sheets initialized successfully")
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize Google Sheets: {e}")
            raise

    def get_worksheet(self, sheet_type: str) -> gspread.Worksheet:
        """Get a specific worksheet by type"""
        sheet_name = self.sheet_names.get(sheet_type)
        if not sheet_name:
            raise ValueError(f"Unknown sheet type: {sheet_type}")
        
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"Worksheet '{sheet_name}' not found")
            raise

    def get_all_records(self, sheet_type: str) -> List[Dict[str, Any]]:
        """Fetch all records from a worksheet"""
        try:
            worksheet = self.get_worksheet(sheet_type)
            records = worksheet.get_all_records()
            logger.info(f"✓ Fetched {len(records)} records from {sheet_type}")
            return records
        except Exception as e:
            logger.error(f"✗ Error fetching records from {sheet_type}: {e}")
            return []

    def parse_pilots(self, records: List[Dict[str, Any]]) -> List[Pilot]:
        """Convert raw records to Pilot objects"""
        pilots = []
        logger.info(f"Parsing {len(records)} pilot records...")
        
        for idx, record in enumerate(records):
            try:
                skills = [s.strip() for s in str(record.get("skills", "")).split(",") if s.strip()]
                certifications = [c.strip() for c in str(record.get("certifications", "")).split(",") if c.strip()]
                
                status_str = record.get("status", "Available").strip()
                if status_str == "Available":
                    status = PilotStatus.AVAILABLE
                elif status_str == "On Leave":
                    status = PilotStatus.ON_LEAVE
                elif status_str == "Assigned":
                    status = PilotStatus.ON_MISSION
                else:
                    status = PilotStatus.UNAVAILABLE
                
                assignment = record.get("current_assignment", "-")
                current_assignment = None if assignment in ["-", ""] else assignment
                
                daily_rate = float(record.get("daily_rate_inr", 1500) or 1500)
                hourly_rate = daily_rate / 8
                
                pilot = Pilot(
                    name=record.get("name", "").strip(),
                    skills=skills,
                    certifications=certifications,
                    drone_experience_hours=int(record.get("experience_hours", 0) or 0),
                    current_location=record.get("location", "").strip(),
                    current_assignment=current_assignment,
                    status=status,
                    availability_start=self._parse_date(record.get("available_from")),
                    availability_end=None,
                    hourly_rate=hourly_rate,
                    email=record.get("email"),
                    phone=record.get("phone")
                )
                pilots.append(pilot)
                logger.info(f"✓ Parsed: {pilot.name}")
            except Exception as e:
                logger.warning(f"⚠️  Skipped record {idx}: {e}")
                continue
        
        logger.info(f"✓ Successfully parsed {len(pilots)}/{len(records)} pilots")
        return pilots

    def parse_drones(self, records: List[Dict[str, Any]]) -> List[Drone]:
        """Convert raw records to Drone objects"""
        drones = []
        logger.info(f"Parsing {len(records)} drone records...")
        
        for idx, record in enumerate(records):
            try:
                capabilities = [c.strip() for c in str(record.get("capabilities", "")).split(",") if c.strip()]
                
                status_str = record.get("status", "Available").strip()
                if status_str == "Available":
                    status = DroneStatus.AVAILABLE
                elif status_str == "Maintenance":
                    status = DroneStatus.MAINTENANCE
                elif status_str == "Deployed":
                    status = DroneStatus.DEPLOYED
                else:
                    status = DroneStatus.GROUNDED
                
                weather_rating = record.get("weather_resistance", "Standard").strip()
                assignment = record.get("current_assignment", "-")
                current_assignment = None if assignment in ["-", ""] else assignment
                
                drone = Drone(
                    drone_id=record.get("drone_id", "").strip(),
                    model=record.get("model", "").strip(),
                    capabilities=capabilities,
                    weather_rating=weather_rating,
                    current_assignment=current_assignment,
                    status=status,
                    current_location=record.get("location", "").strip(),
                    maintenance_due_date=self._parse_date(record.get("maintenance_due")),
                    max_flight_time=int(record.get("max_flight_time", 30) or 30),
                    purchase_date=None,
                    battery_health=int(record.get("battery_health", 100) or 100),
                    notes=record.get("notes")
                )
                drones.append(drone)
                logger.info(f"✓ Parsed: {drone.drone_id}")
            except Exception as e:
                logger.warning(f"⚠️  Skipped record {idx}: {e}")
                continue
        
        logger.info(f"✓ Successfully parsed {len(drones)}/{len(records)} drones")
        return drones

    def parse_missions(self, records: List[Dict[str, Any]]) -> List[Mission]:
        """Convert raw records to Mission objects"""
        missions = []
        logger.info(f"Parsing {len(records)} mission records...")
        
        for idx, record in enumerate(records):
            try:
                required_skills = [s.strip() for s in str(record.get("required_skills", "")).split(",") if s.strip()]
                required_certs = [c.strip() for c in str(record.get("required_certs", "")).split(",") if c.strip()]
                
                weather_map = {
                    "Rainy": "Rainy",
                    "Sunny": "Clear",
                    "Cloudy": "Cloudy",
                    "Stormy": "Stormy",
                    "Foggy": "Foggy"
                }
                weather_forecast = record.get("weather_forecast", "Clear").strip()
                expected_weather = weather_map.get(weather_forecast, weather_forecast)
                
                budget = float(record.get("mission_budget_inr", 0) or 0)
                
                mission = Mission(
                    mission_id=record.get("project_id", "").strip(),
                    client_name=record.get("client", "").strip(),
                    project_name=record.get("project_id", "").strip(),
                    location=record.get("location", "").strip(),
                    required_skills=required_skills,
                    required_certifications=required_certs,
                    start_date=self._parse_date(record.get("start_date")),
                    end_date=self._parse_date(record.get("end_date")),
                    priority=record.get("priority", "Medium").strip(),
                    budget=budget,
                    drone_requirements=None,
                    expected_weather=expected_weather,
                    assigned_pilots=[],
                    assigned_drones=[],
                    status="Planned"
                )
                missions.append(mission)
                logger.info(f"✓ Parsed: {mission.mission_id}")
            except Exception as e:
                logger.warning(f"⚠️  Skipped record {idx}: {e}")
                continue
        
        logger.info(f"✓ Successfully parsed {len(missions)}/{len(records)} missions")
        return missions

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object"""
        if not date_str or str(date_str).strip() in ["", "-"]:
            return None
        
        try:
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(str(date_str).strip(), fmt).date()
                except ValueError:
                    continue
            return None
        except Exception as e:
            logger.warning(f"Error parsing date '{date_str}': {e}")
            return None

    def sync_data(self) -> tuple:
        """Fetch all data from Google Sheets"""
        try:
            logger.info("=" * 60)
            logger.info("Syncing data from Google Sheets...")
            logger.info("=" * 60)
            
            pilots = self.parse_pilots(self.get_all_records("pilots"))
            drones = self.parse_drones(self.get_all_records("drones"))
            missions = self.parse_missions(self.get_all_records("missions"))
            
            logger.info("=" * 60)
            logger.info(f"✓ Sync complete: {len(pilots)} pilots, {len(drones)} drones, {len(missions)} missions")
            logger.info("=" * 60)
            
            return pilots, drones, missions
        except Exception as e:
            logger.error(f"✗ Error syncing data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], [], []