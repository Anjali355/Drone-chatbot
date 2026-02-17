"""
LLM Parser for natural language query understanding.
Uses Groq API with Llama 3 to parse and understand user queries.
Structured to support LangGraph integration in future.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from groq import Groq
from datetime import date, datetime

from config import GROQ_API_KEY, GROQ_MODEL
from schemas import (
    QueryRequest, Pilot, Drone, Mission, ConflictDetectionResult,
    CostEstimate, MissionCostBreakdown
)

logger = logging.getLogger(__name__)


class LLMParser:
    """Handles natural language understanding and response generation"""

    def __init__(self):
        """Initialize Groq client"""
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL

    def parse_query(self, user_query: str) -> QueryRequest:
        """
        Parse natural language query into structured QueryRequest.
        Uses Groq Llama to understand intent and extract parameters.
        """
        prompt = f"""You are an AI assistant that parses user queries for a drone operations coordinator system.
    Analyze the following user query and determine:
    1. The query type
    2. Any parameters needed for the query

    IMPORTANT DISTINCTION:
    - "show pilot assigned to mission" or "who is assigned to" = find_pilots (SEARCH query)
    - "assign pilot to mission" = assign_pilot (ACTION query)
    - "show drone assigned to mission" or "which drone is assigned" = find_drones (SEARCH query)
    - "assign drone to mission" = assign_drone (ACTION query)

    Query: "{user_query}"

    For availability queries with dates, use find_pilots query type and extract:
    - date: specific date in YYYY-MM-DD format (e.g., "2026-02-07")
    - mission_id: if asking about availability for specific mission

    For drone queries, extract:
    - capability: what the drone can do (e.g., "thermal", "rgb", "lidar", "mapping")
    - weather_rating: drone weather resistance (e.g., "IP43", "IP67", "Standard")
    - location: where the drone is (e.g., "Mumbai", "Bangalore")
    - mission_id: mission identifier if mentioned

    For pilot queries, extract:
    - skill: what the pilot can do (e.g., "survey", "mapping", "inspection", "thermal")
    - certification: certification type (e.g., "DGCA", "Night Ops")
    - location: pilot location
    - date: date in YYYY-MM-DD format if asking about availability on specific date
    - mission_id: mission identifier if mentioned

    Return ONLY a valid JSON object with NO additional text or markdown:
    {{
        "query_type": "find_pilots|find_drones|check_conflicts|calculate_costs|update_status|assign_pilot|assign_drone|get_availability|get_summary|unknown",
        "parameters": {{
            "mission_id": null,
            "pilot_name": null,
            "drone_id": null,
            "skill": null,
            "certification": null,
            "capability": null,
            "weather_rating": null,
            "location": null,
            "date": null,
            "status": null,
            "reason": null
        }},
        "confidence": 0.95
    }}"""
        try:
            message = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500,
            )
            
            response_text = message.choices[0].message.content.strip()
            
            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            # Parse JSON response
            parsed = json.loads(response_text)
            
            # Clean parameters (remove None values)
            clean_params = {k: v for k, v in parsed.get("parameters", {}).items() if v is not None}
            
            query_request = QueryRequest(
                query_type=parsed.get("query_type", "unknown"),
                parameters=clean_params
            )
            
            logger.info(f"✓ Parsed query: {query_request.query_type}")
            logger.debug(f"  Parameters: {clean_params}")
            return query_request
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response_text if 'response_text' in locals() else 'N/A'}")
            return QueryRequest(query_type="unknown", parameters={})
        except Exception as e:
            logger.error(f"Error parsing query: {e}")
            return QueryRequest(query_type="unknown", parameters={})

    def generate_response(
        self,
        query_type: str,
        result: Any,
        context: Optional[str] = None
    ) -> str:
        """
        Generate natural language response from query results.
        Can be a summary, formatted data, or narrative explanation.
        """
        # Serialize result for LLM
        if isinstance(result, list):
            serialized = [self._serialize_object(obj) for obj in result]
        else:
            serialized = self._serialize_object(result)
        
        prompt = f"""You are a professional operations coordinator assistant. Format the following results into a clear, concise response.

Query Type: {query_type}
{f'Context: {context}' if context else ''}

Results:
{json.dumps(serialized, indent=2, default=str)}

Provide a professional, actionable response that:
1. Summarizes key findings
2. Highlights any critical issues
3. Provides recommendations where relevant
4. Uses clear formatting and bullet points where helpful

Keep the response concise but informative."""
        try:
            message = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1500,
            )
            
            return message.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Unable to generate response. Please try again."

    def generate_conflict_report(self, conflicts_result: ConflictDetectionResult) -> str:
        """Generate a formatted conflict report from conflict detection results"""
        if not conflicts_result.conflicts:
            return "✓ No conflicts detected. All assignments are valid."
        
        # Organize by severity
        critical = [c for c in conflicts_result.conflicts if c.severity == "Critical"]
        high = [c for c in conflicts_result.conflicts if c.severity == "High"]
        warnings = [c for c in conflicts_result.conflicts if c.severity == "Warning"]
        
        report = f"""
CONFLICT DETECTION REPORT
{'='*60}

{conflicts_result.summary}

"""
        
        if critical:
            report += f"🔴 CRITICAL ISSUES ({len(critical)}):\n"
            for conflict in critical:
                report += self._format_conflict(conflict)
            report += "\n"
        
        if high:
            report += f"🟠 HIGH PRIORITY ({len(high)}):\n"
            for conflict in high:
                report += self._format_conflict(conflict)
            report += "\n"
        
        if warnings:
            report += f"🟡 WARNINGS ({len(warnings)}):\n"
            for conflict in warnings:
                report += self._format_conflict(conflict)
        
        return report

    def _format_conflict(self, conflict) -> str:
        """Format a single conflict for display"""
        text = f"\n• {conflict.affected_entity}: {conflict.description}\n"
        
        if conflict.resolution_suggestions:
            text += "  Suggestions:\n"
            for suggestion in conflict.resolution_suggestions[:2]:
                text += f"    - {suggestion}\n"
        
        return text

    def generate_cost_report(self, cost_breakdown: MissionCostBreakdown) -> str:
        """Generate a formatted cost breakdown report"""
        report = f"""
MISSION COST BREAKDOWN
{'='*60}
Mission ID: {cost_breakdown.mission_id}

PILOT COSTS:
"""
        for cost in cost_breakdown.pilot_costs:
            status = "✓" if cost.within_budget else "✗"
            report += f"\n  {status} {cost.pilot_name}:\n"
            report += f"      Rate: ₹{cost.hourly_rate:.2f}/hour\n"
            report += f"      Estimated Hours: {cost.estimated_hours:.1f}\n"
            report += f"      Cost: ₹{cost.estimated_cost:.2f}\n"
        
        report += f"""
{'='*60}
Total Pilots Cost:        ₹{cost_breakdown.total_pilots_cost:.2f}
Other Costs:             ₹{cost_breakdown.total_drones_cost:.2f}
───────────────────────────────
Total Estimated Cost:    ₹{cost_breakdown.total_estimated_cost:.2f}
Mission Budget:          ₹{cost_breakdown.mission_budget:.2f}
"""
        
        if cost_breakdown.within_budget:
            remaining = cost_breakdown.mission_budget - cost_breakdown.total_estimated_cost
            report += f"✓ Within Budget: ₹{remaining:.2f} remaining\n"
        else:
            overrun = cost_breakdown.total_estimated_cost - cost_breakdown.mission_budget
            report += f"✗ BUDGET OVERRUN: ₹{overrun:.2f}\n"
        
        if cost_breakdown.warnings:
            report += f"\nWarnings:\n"
            for warning in cost_breakdown.warnings:
                report += f"  ⚠️  {warning}\n"
        
        return report

    def generate_availability_report(self, availability_summary: Dict[str, Dict]) -> str:
        """Generate a pilot availability summary report"""
        report = f"""
PILOT AVAILABILITY SUMMARY
{'='*60}

"""
        available_count = 0
        on_leave_count = 0
        unavailable_count = 0
        
        for pilot_name, info in sorted(availability_summary.items()):
            status = info['status']
            
            if status == "Available":
                available_count += 1
                icon = "🟢"
            elif status == "On Leave":
                on_leave_count += 1
                icon = "🟠"
            else:
                unavailable_count += 1
                icon = "🔴"
            
            report += f"{icon} {pilot_name}\n"
            report += f"    Status: {status}\n"
            report += f"    Location: {info['location']}\n"
            report += f"    Rate: ₹{info['hourly_rate']:.2f}/hour\n"
            report += f"    Skills: {', '.join(info['skills']) if info['skills'] else 'None'}\n"
            
            if info['available_for']:
                report += f"    Available for: {', '.join(info['available_for'][:3])}\n"
            
            report += "\n"
        
        report += f"""{'='*60}
SUMMARY:
  Available: {available_count}
  On Leave: {on_leave_count}
  Unavailable: {unavailable_count}
"""
        
        return report

    def format_pilot_list(self, pilots: List[tuple]) -> str:
        """Format a list of pilots with compatibility info"""
        if not pilots:
            return "No pilots found matching criteria."
        
        report = """
MATCHING PILOTS:
{'='*60}

"""
        for pilot, missing_items in pilots:
            report += f"✓ {pilot.name}\n"
            report += f"  Location: {pilot.current_location}\n"
            report += f"  Skills: {', '.join(pilot.skills)}\n"
            report += f"  Certifications: {', '.join(pilot.certifications)}\n"
            report += f"  Rate: ₹{pilot.hourly_rate:.2f}/hour\n"
            report += f"  Experience: {pilot.drone_experience_hours} hours\n"
            
            if missing_items:
                report += f"  ⚠️  Missing: {', '.join(missing_items)}\n"
            
            report += "\n"
        
        return report

    def format_drone_list(self, drones: List[tuple]) -> str:
        """Format a list of drones with compatibility info"""
        if not drones:
            return "No drones found matching criteria."
        
        report = """
COMPATIBLE DRONES:
{'='*60}

"""
        for drone, missing_items in drones:
            status_icon = "🟢" if drone.status.value == "Available" else "🟡"
            report += f"{status_icon} {drone.drone_id} ({drone.model})\n"
            report += f"  Location: {drone.current_location}\n"
            report += f"  Status: {drone.status.value}\n"
            report += f"  Weather Rating: {drone.weather_rating}\n"
            report += f"  Capabilities: {', '.join(drone.capabilities)}\n"
            report += f"  Battery Health: {drone.battery_health}%\n"
            
            if missing_items:
                report += f"  ⚠️  Issues: {', '.join(missing_items)}\n"
            
            report += "\n"
        
        return report

    @staticmethod
    def _serialize_object(obj: Any) -> Any:
        """Convert object to serializable format"""
        if hasattr(obj, "__dict__"):
            result = {}
            for key, value in obj.__dict__.items():
                if isinstance(value, (date, datetime)):
                    result[key] = value.isoformat()
                elif isinstance(value, list):
                    result[key] = [
                        item.isoformat() if isinstance(item, (date, datetime))
                        else LLMParser._serialize_object(item)
                        for item in value
                    ]
                elif hasattr(value, "__dict__"):
                    result[key] = LLMParser._serialize_object(value)
                else:
                    result[key] = value
            return result
        return obj

    def should_update_sheets(self, query_type: str) -> bool:
        """Determine if query result should be synced back to sheets"""
        update_types = [
            "update_status",
            "assign_pilot",
            "assign_drone",
            "reassign_pilot",
            "reassign_drone"
        ]
        return query_type in update_types