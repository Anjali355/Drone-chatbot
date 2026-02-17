"""
Google Sheets service for reading and writing data.
Handles authentication, data fetching, and syncing.
FIXED: No proxies initialization
"""

import logging
from typing import List, Dict, Any, Optional
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime
import json
import streamlit as st
from google.oauth2.service_account import Credentials
import os

from config import GOOGLE_SHEETS_ID, SHEET_NAMES
from schemas import Pilot, Drone, Mission, PilotStatus, DroneStatus

logger = logging.getLogger(__name__)


class SheetService:
    """Handles all Google Sheets interactions"""

    def __init__(self):
        """Initialize Google Sheets client - NO PROXIES"""
        try:
            logger.info("Initializing Google Sheets client...")
            
            # Check if secrets are available (Cloud Hosting)
            if "google_credentials" in st.secrets:
                self.credentials = Credentials.from_service_account_info(
                    dict(st.secrets["google_credentials"]),
                    scopes=["https://www.googleapis.com/auth/spreadsheets"]
                )
                logger.info("✓ Authenticated using Streamlit Secrets")
            
            # Fallback for local development (if file exists)
            else:
                self.credentials = Credentials.from_service_account_file(
                    "credentials.json",
                    scopes=["https://www.googleapis.com/auth/spreadsheets"]
                )
                logger.info("✓ Authenticated using local credentials.json")
                
            self.gc = gspread.authorize(self.credentials)
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize Sheets: {e}")
            # Re-raise so the main app knows initialization failed
            raise e

            logger.info("✓ Credentials loaded")
            
            # Authorize gspread WITHOUT proxies
            self.client = gspread.authorize(self.credentials)
            logger.info("✓ Gspread authorized")
            
            # Open sheet
            self.sheet = self.client.open_by_key(GOOGLE_SHEETS_ID)
            logger.info("✓ Google Sheets client initialized successfully")
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize Google Sheets: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def get_worksheet(self, sheet_type: str) -> gspread.Worksheet:
        """Get a specific worksheet by type"""
        sheet_name = SHEET_NAMES.get(sheet_type)
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
            logger.info(f"✓ Fetched {len(records)} raw records from {sheet_type}")
            if records:
                logger.debug(f"First record columns: {list(records[0].keys())}")
            return records
        except Exception as e:
            logger.error(f"✗ Error fetching records from {sheet_type}: {e}")
            return []

    def parse_pilots(self, records: List[Dict[str, Any]]) -> List[Pilot]:
        """Convert raw records to Pilot objects"""
        pilots = []
        logger.info(f"Starting to parse {len(records)} pilot records")
        
        for idx, record in enumerate(records):
            try:
                logger.debug(f"Parsing pilot record {idx}: {record}")
                
                # Parse skills and certifications
                skills = [s.strip() for s in str(record.get("skills", "")).split(",") if s.strip()]
                certifications = [c.strip() for c in str(record.get("certifications", "")).split(",") if c.strip()]
                
                # Map status
                status_str = record.get("status", "Available").strip()
                if status_str == "Available":
                    status = PilotStatus.AVAILABLE
                elif status_str == "On Leave":
                    status = PilotStatus.ON_LEAVE
                elif status_str == "Assigned":
                    status = PilotStatus.ON_MISSION
                else:
                    status = PilotStatus.UNAVAILABLE
                
                # Handle assignment
                assignment = record.get("current_assignment", "-")
                current_assignment = None if assignment == "-" or assignment == "" else assignment
                
                # Convert daily rate to hourly
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
                logger.info(f"✓ Parsed pilot: {pilot.name} (Status: {status.value}, Skills: {skills})")
            except Exception as e:
                logger.warning(f"⚠️ Skipped pilot record {idx}: {e}")
                logger.debug(f"Failed record: {record}")
                continue
        
        logger.info(f"✓ Successfully parsed {len(pilots)}/{len(records)} pilots")
        return pilots

    def parse_drones(self, records: List[Dict[str, Any]]) -> List[Drone]:
        """Convert raw records to Drone objects"""
        drones = []
        logger.info(f"Starting to parse {len(records)} drone records")
        
        for idx, record in enumerate(records):
            try:
                logger.debug(f"Parsing drone record {idx}: {record}")
                
                # Parse capabilities
                capabilities = [c.strip() for c in str(record.get("capabilities", "")).split(",") if c.strip()]
                logger.debug(f"  Capabilities: {capabilities}")
                
                # Map status
                status_str = record.get("status", "Available").strip()
                logger.debug(f"  Status string: '{status_str}'")
                
                if status_str == "Available":
                    status = DroneStatus.AVAILABLE
                elif status_str == "Maintenance":
                    status = DroneStatus.MAINTENANCE
                elif status_str == "Deployed":
                    status = DroneStatus.DEPLOYED
                else:
                    status = DroneStatus.GROUNDED
                
                logger.debug(f"  Mapped status: {status.value}")
                
                # Get weather rating
                weather_rating = record.get("weather_resistance", "Standard").strip()
                logger.debug(f"  Weather rating: {weather_rating}")
                
                # Handle assignment
                assignment = record.get("current_assignment", "-")
                current_assignment = None if assignment == "-" or assignment == "" else assignment
                
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
                logger.info(f"✓ Parsed drone: {drone.drone_id} ({drone.model}) - Status: {status.value}")
            except Exception as e:
                logger.warning(f"⚠️ Skipped drone record {idx}: {e}")
                logger.debug(f"Failed record: {record}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        logger.info(f"✓ Successfully parsed {len(drones)}/{len(records)} drones")
        return drones

    def parse_missions(self, records: List[Dict[str, Any]]) -> List[Mission]:
        """Convert raw records to Mission objects"""
        missions = []
        logger.info(f"Starting to parse {len(records)} mission records")
        
        for idx, record in enumerate(records):
            try:
                logger.debug(f"Parsing mission record {idx}: {record}")
                
                # Parse skills and certifications
                required_skills = [s.strip() for s in str(record.get("required_skills", "")).split(",") if s.strip()]
                required_certs = [c.strip() for c in str(record.get("required_certs", "")).split(",") if c.strip()]
                logger.debug(f"  Skills: {required_skills}, Certs: {required_certs}")
                
                # Map weather
                weather_map = {
                    "Rainy": "Rainy",
                    "Sunny": "Clear",
                    "Cloudy": "Cloudy",
                    "Stormy": "Stormy",
                    "Foggy": "Foggy"
                }
                weather_forecast = record.get("weather_forecast", "Clear").strip()
                expected_weather = weather_map.get(weather_forecast, weather_forecast)
                logger.debug(f"  Weather: {weather_forecast} → {expected_weather}")
                
                # Get budget
                budget = float(record.get("mission_budget_inr", 0) or 0)
                logger.debug(f"  Budget: {budget}")
                
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
                logger.info(f"✓ Parsed mission: {mission.mission_id} ({mission.client_name})")
            except Exception as e:
                logger.warning(f"⚠️ Skipped mission record {idx}: {e}")
                logger.debug(f"Failed record: {record}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        logger.info(f"✓ Successfully parsed {len(missions)}/{len(records)} missions")
        return missions

    def update_pilot_status(self, pilot_name: str, new_status: PilotStatus) -> bool:
        """Update a pilot's status in the Google Sheet"""
        try:
            worksheet = self.get_worksheet("pilots")
            records = worksheet.get_all_records()
            
            for idx, record in enumerate(records, start=2):
                if record.get("name", "").strip() == pilot_name:
                    worksheet.update_cell(idx, self._get_column_index(worksheet, "status"), new_status.value)
                    logger.info(f"✓ Updated pilot '{pilot_name}' status to {new_status.value}")
                    return True
            
            logger.warning(f"✗ Pilot '{pilot_name}' not found in sheet")
            return False
        except Exception as e:
            logger.error(f"✗ Error updating pilot status: {e}")
            return False

    def update_drone_status(self, drone_id: str, new_status: DroneStatus) -> bool:
        """Update a drone's status in the Google Sheet"""
        try:
            worksheet = self.get_worksheet("drones")
            records = worksheet.get_all_records()
            
            for idx, record in enumerate(records, start=2):
                if record.get("drone_id", "").strip() == drone_id:
                    worksheet.update_cell(idx, self._get_column_index(worksheet, "status"), new_status.value)
                    logger.info(f"✓ Updated drone '{drone_id}' status to {new_status.value}")
                    return True
            
            logger.warning(f"✗ Drone '{drone_id}' not found in sheet")
            return False
        except Exception as e:
            logger.error(f"✗ Error updating drone status: {e}")
            return False

    def update_pilot_assignment(self, pilot_name: str, mission_id: Optional[str]) -> bool:
        """Update a pilot's current assignment"""
        try:
            worksheet = self.get_worksheet("pilots")
            records = worksheet.get_all_records()
            
            for idx, record in enumerate(records, start=2):
                if record.get("name", "").strip() == pilot_name:
                    assignment_value = mission_id if mission_id else "-"
                    worksheet.update_cell(idx, self._get_column_index(worksheet, "current_assignment"), assignment_value)
                    logger.info(f"✓ Updated pilot '{pilot_name}' assignment to {mission_id or 'None'}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"✗ Error updating pilot assignment: {e}")
            return False

    def update_drone_assignment(self, drone_id: str, mission_id: Optional[str]) -> bool:
        """Update a drone's current assignment"""
        try:
            worksheet = self.get_worksheet("drones")
            records = worksheet.get_all_records()
            
            for idx, record in enumerate(records, start=2):
                if record.get("drone_id", "").strip() == drone_id:
                    assignment_value = mission_id if mission_id else "-"
                    worksheet.update_cell(idx, self._get_column_index(worksheet, "current_assignment"), assignment_value)
                    logger.info(f"✓ Updated drone '{drone_id}' assignment to {mission_id or 'None'}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"✗ Error updating drone assignment: {e}")
            return False

    def append_record(self, sheet_type: str, record: Dict[str, Any]) -> bool:
        """Append a new record to a worksheet"""
        try:
            worksheet = self.get_worksheet(sheet_type)
            headers = worksheet.row_values(1)
            
            row_values = [record.get(header, "") for header in headers]
            worksheet.append_row(row_values)
            
            logger.info(f"✓ Appended new record to {sheet_type}")
            return True
        except Exception as e:
            logger.error(f"✗ Error appending record: {e}")
            return False

    def _get_column_index(self, worksheet: gspread.Worksheet, column_name: str) -> int:
        """Get column index by header name"""
        headers = worksheet.row_values(1)
        try:
            return headers.index(column_name) + 1
        except ValueError:
            raise ValueError(f"Column '{column_name}' not found in worksheet")

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object"""
        if not date_str or str(date_str).strip() == "" or str(date_str).strip() == "-":
            return None
        
        try:
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(str(date_str).strip(), fmt).date()
                except ValueError:
                    continue
            
            logger.warning(f"Could not parse date: {date_str}")
            return None
        except Exception as e:
            logger.warning(f"Error parsing date '{date_str}': {e}")
            return None

    def sync_data(self) -> tuple:
        """Fetch all data from Google Sheets"""
        try:
            logger.info("=" * 60)
            logger.info("Starting data sync...")
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