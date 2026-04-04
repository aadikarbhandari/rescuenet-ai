"""
RescueNet AI - Coordinator Agent
Supervisor agent for intelligent drone dispatch and mission planning.
Uses DeepSeek LLM for dispatch decisions with rule-based fallback.
"""
import requests
import json
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Union

from config.settings import Settings
from state.fleet_state import FleetState, DroneState, VictimState, MissionAssignment, MissionStatus, DroneStatus

logger = logging.getLogger(__name__)


class CoordinatorAgent:
    """
    Coordinator agent responsible for dispatching drones to rescue victims.
    Uses DeepSeek LLM for intelligent dispatch decisions when available,
    with a robust rule-based fallback system.
    """

    def __init__(self, fleet_state: FleetState, settings: Optional[Settings] = None):
        self.fleet_state = fleet_state
        self.settings = settings or Settings()
        self.decision_history: List[Dict[str, Any]] = []
        self.stats = {
            "llm_dispatches": 0,
            "rule_based_dispatches": 0,
            "total_assignments": 0,
            "failed_assignments": 0
        }
        logger.info("CoordinatorAgent initialized")

    def _call_deepseek(self, prompt: str) -> Optional[str]:
        """Call DeepSeek LLM API with structured prompt."""
        api_key = self.settings.deepseek.deepseek_api_key
        if not api_key:
            logger.warning("DeepSeek API key not configured")
            return None

        base_url = self.settings.deepseek.deepseek_base_url
        model = self.settings.deepseek.deepseek_model

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a disaster response coordinator. Analyze the situation and assign drones to victims efficiently."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }

        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"DeepSeek API call failed: {e}")
            return None

    def _build_dispatch_prompt(self, available_drones: List[DroneState], 
                                victims: List[VictimState]) -> str:
        """Build detailed prompt for LLM dispatch decision."""
        drone_info = []
        for d in available_drones:
            drone_info.append(
                f"- Drone {d.id}: battery={d.battery:.0f}%, "
                f"position=({d.position[0]:.1f}, {d.position[1]:.1f}, {d.position[2]:.1f})"
            )

        victim_info = []
        for v in victims:
            victim_info.append(
                f"- Victim {v['victim_id']}: severity={v.get('severity','moderate')}, triage_score={v.get('score',0):.1f}, "
                f"position=({v.get('x',0):.1f}, {v.get('y',0):.1f}, {v.get('z',0):.1f})"
            )

        prompt = f"""You are coordinating a drone rescue mission.

AVAILABLE DRONES:
{chr(10).join(drone_info)}

UNASSIGNED VICTIMS:
{chr(10).join(victim_info)}

Assign each victim to the nearest available drone considering battery levels.
Respond with a JSON list of assignments in this format:
[{{"drone_id": "drone_1", "victim_id": "victim_1"}}, ...]

Only include assignments where a drone can reasonably reach the victim.
"""
        return prompt

    def _parse_dispatch_response(self, response: str) -> List[Dict[str, str]]:
        """Parse JSON response from LLM dispatch decision."""
        try:
            # Try to find JSON array in response
            start_idx = response.find('[')
            end_idx = response.rfind(']')
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx+1]
                assignments = json.loads(json_str)
                return assignments
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse dispatch response: {e}")
        return []

    def _get_victim_score(self, victim: Union[VictimState, Dict[str, Any]]) -> float:
        """Extract comparable triage score from victim object or dict."""
        if isinstance(victim, dict):
            return float(victim.get("triage_score", victim.get("score", 0)) or 0)
        return float(getattr(victim, "triage_score", 0) or 0)

    def _get_victim_id(self, victim: Union[VictimState, Dict[str, Any]]) -> str:
        if isinstance(victim, dict):
            return str(victim.get("victim_id") or victim.get("id") or "unknown")
        return str(getattr(victim, "id", "unknown"))

    def _get_victim_position(self, victim: Union[VictimState, Dict[str, Any]]) -> Tuple[float, float, float]:
        if isinstance(victim, dict):
            if "position" in victim and isinstance(victim["position"], (list, tuple)):
                x, y, z = (list(victim["position"]) + [0, 0, 0])[:3]
                return float(x), float(y), float(z)
            return float(victim.get("x", 0)), float(victim.get("y", 0)), float(victim.get("z", 0))
        pos = getattr(victim, "position", (0, 0, 0))
        x, y, z = (list(pos) + [0, 0, 0])[:3]
        return float(x), float(y), float(z)

    def _rule_based_dispatch(self, available_drones: List[DroneState],
                             victims: List[Union[VictimState, Dict[str, Any]]]) -> List[Dict[str, str]]:
        """
        Rule-based dispatch fallback using greedy nearest-neighbor with priority.
        Considers: distance, battery level, victim severity.
        """
        if not available_drones or not victims:
            logger.info(f"Rule-based dispatch: no drones ({len(available_drones)}) or no victims ({len(victims)})")
            return []

        assignments = []
        # Sort victims by triage score (higher = more critical)
        sorted_victims = sorted(victims, key=self._get_victim_score, reverse=True)
        
        # Create a copy of available drones to track assignments
        available_drones_copy = list(available_drones)

        for victim in sorted_victims:
            if not available_drones_copy:
                break  # No more drones available

            # Find nearest drone that has enough battery
            best_drone = None
            best_distance = float('inf')

            for drone in available_drones_copy:
                # Calculate 3D distance
                dist = self._calculate_distance(drone.position, self._get_victim_position(victim))
                
                # Check if drone has enough battery (at least 20%)
                battery_sufficient = (getattr(drone, "battery", 0) or 0) >= 20
                
                # Prefer closer drones with sufficient battery
                if battery_sufficient and dist < best_distance:
                    best_distance = dist
                    best_drone = drone

            if best_drone:
                assignments.append({
                    "drone_id": best_drone.id,
                    "victim_id": self._get_victim_id(victim)
                })
                available_drones_copy.remove(best_drone)
                logger.info(f"Rule-based dispatch: assigned {best_drone.id} to {self._get_victim_id(victim)} (distance: {best_distance:.1f}m)")

        logger.info(f"Rule-based dispatch created {len(assignments)} assignments")
        return assignments

    def _calculate_distance(self, pos1: Tuple[float, float, float], pos2: Tuple[float, float, float]) -> float:
        """Calculate 3D Euclidean distance between two positions."""
        x1, y1, z1 = (list(pos1) + [0, 0, 0])[:3]
        x2, y2, z2 = (list(pos2) + [0, 0, 0])[:3]
        return ((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2) ** 0.5

    def decide_dispatch(self, victims: List[VictimState]) -> List[Dict[str, str]]:
        """
        Decide which drones to dispatch to which victims.
        Tries LLM first, falls back to rule-based dispatch.
        """
        # Get available drones from fleet state
        available_drones = self.fleet_state.get_available_drones()
        
        # Also include drones that are idle (not currently on a mission)
        all_drones = list(self.fleet_state.drones.values())
        idle_drones = [d for d in all_drones if getattr(d, 'status', None) in [None, 'idle', 'AVAILABLE']]
        
        # Use idle drones if no explicitly available ones
        if not available_drones and idle_drones:
            available_drones = idle_drones
            logger.info(f"Using {len(available_drones)} idle drones for dispatch")

        logger.info(f"Deciding dispatch for {len(victims)} victims, {len(available_drones)} available drones")

        # Try LLM dispatch first (if enabled and configured)
        use_llm = (
            self.settings.deepseek.deepseek_api_key and 
            self.settings.deepseek.deepseek_api_key != "YOUR_API_KEY_HERE" and
            len(available_drones) > 0 and
            len(victims) > 0
        )

        if use_llm:
            prompt = self._build_dispatch_prompt(available_drones, victims)
            response = self._call_deepseek(prompt)
            if response:
                assignments = self._parse_dispatch_response(response)
                if assignments:
                    self.stats["llm_dispatches"] += 1
                    logger.info(f"LLM dispatch created {len(assignments)} assignments")
                    try:
                        import json as _j, time as _t, os as _o
                        _df = "/tmp/rescuenet_decisions.json"
                        _ex = _j.load(open(_df)) if _o.path.exists(_df) else []
                        _ex.append({"timestamp": _t.strftime("%H:%M:%S"), "type": "LLM Dispatch", "count": len(assignments), "assignments": assignments})
                        _j.dump(_ex[-20:], open(_df, "w"))
                    except: pass
                    return assignments

        # Fall back to rule-based dispatch
        assignments = self._rule_based_dispatch(available_drones, victims)
        self.stats["rule_based_dispatches"] += 1
        if assignments:
            logger.info(f"Using rule-based dispatch: {len(assignments)} assignments created")
        else:
            logger.warning("Rule-based dispatch produced no assignments")
        return assignments

    def execute_dispatch(self, assignments: List[Dict[str, str]], 
                         env: Any) -> List[MissionAssignment]:
        """
        Execute dispatch decisions by creating missions and sending drones.
        """
        if not assignments:
            logger.info("No assignments to execute")
            return []

        mission_assignments = []
        
        for assignment in assignments:
            drone_id = assignment.get("drone_id")
            victim_id = assignment.get("victim_id")

            # Get drone and victim from fleet state
            drone = self.fleet_state.drones.get(drone_id)
            victim = self.fleet_state.victims.get(victim_id)

            if not drone:
                logger.warning(f"Drone {drone_id} not found in fleet state")
                self.stats["failed_assignments"] += 1
                continue

            if not victim:
                logger.warning(f"Victim {victim_id} not found in fleet state")
                self.stats["failed_assignments"] += 1
                continue

            # Create mission assignment
            mission = MissionAssignment(
                id=f"mission_{int(time.time() * 1000)}_{drone_id}",
                drone_id=drone_id,
                victim_id=victim_id,
                status=MissionStatus.PENDING,
                waypoints=[
                    tuple(victim.position)
                ],
                created_at=time.time()
            )

            # Add mission to fleet state
            self.fleet_state.add_mission(mission)
            
            # Update drone status to BUSY
            drone.status = DroneStatus.BUSY
            drone.current_mission_id = mission.id
            
            # Update victim status
            victim.status = "assigned"

            # Execute in environment if available
            if env:
                try:
                    env.update_drone_mission(drone_id, mission.id)
                    env.update_victim_assignment(victim_id, drone_id, mission.id)
                except Exception as e:
                    logger.warning(f"Failed to update environment: {e}")

            mission_assignments.append(mission)
            self.stats["total_assignments"] += 1
            logger.info(f"Executed dispatch: {drone_id} -> {victim_id}")

        return mission_assignments

    def replan_if_needed(self, env: Any) -> bool:
        """
        Check if replanning is needed due to aborted missions, faulted drones, 
        or new critical victims.
        """
        # Check for aborted/failed missions
        for mission in self.fleet_state.missions.values():
            if mission.status in [MissionStatus.FAILED, MissionStatus.CANCELLED]:
                # Reassign victim
                victim = self.fleet_state.victims.get(mission.victim_id)
                if victim and victim.status == "assigned":
                    victim.status = "unassigned"
                    logger.info(f"Replanning for victim {victim.id} due to mission failure")
                    return True

        # Check for faulted drones
        for drone in self.fleet_state.drones.values():
            if getattr(drone, 'fault_detected', False):
                logger.info(f"Replanning due to faulted drone {drone.id}")
                return True

        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Return coordinator statistics for dashboard."""
        return {
            "total_decisions": len(self.decision_history),
            "llm_dispatches": self.stats["llm_dispatches"],
            "rule_based_dispatches": self.stats["rule_based_dispatches"],
            "total_assignments": self.stats["total_assignments"],
            "failed_assignments": self.stats["failed_assignments"],
            "recent_decisions": self.decision_history[-10:] if self.decision_history else []
        }
