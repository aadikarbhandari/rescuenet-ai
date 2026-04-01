"""
Priority scoring + drone assignment
"""
from typing import List, Tuple
from dataclasses import dataclass
import math
import os
import json
import logging

# For LLM API calls
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

@dataclass
class TriageVictim:
    """Extended victim data for triage scoring."""
    victim_id: str
    severity: str                     # "minor", "moderate", "severe", "critical"
    conscious: bool                   # True if conscious, False if unconscious
    bleeding: str                     # "none", "mild", "moderate", "severe"
    body_temperature_c: float         # normal ~37.0
    accessibility: float              # 0.0 (completely blocked) to 1.0 (fully accessible)
    position: tuple                   # (x, y, z) coordinates

class TriageAgent:
    def __init__(self):
        pass

    def compute_priority(self, victim: TriageVictim) -> Tuple[float, str]:
        """
        Compute a priority score between 0 and 100 and a human‑readable reason.
        Higher score means higher urgency.
        """
        score = 0.0
        reasons = []

        # 1. Severity weight (0‑30)
        severity_weights = {
            "critical": 30,
            "severe": 22,
            "moderate": 14,
            "minor": 6
        }
        severity_score = severity_weights.get(victim.severity, 0)
        score += severity_score
        reasons.append(f"severity {victim.severity} (+{severity_score})")

        # 2. Consciousness (0‑20)
        if not victim.conscious:
            score += 20
            reasons.append("unconscious (+20)")
        else:
            reasons.append("conscious (+0)")

        # 3. Bleeding (0‑25)
        bleeding_weights = {
            "severe": 25,
            "moderate": 15,
            "mild": 8,
            "none": 0
        }
        bleeding_score = bleeding_weights.get(victim.bleeding, 0)
        score += bleeding_score
        reasons.append(f"bleeding {victim.bleeding} (+{bleeding_score})")

        # 4. Body temperature (0‑15)
        # Normal ~37°C, hypothermia <35°C, hyperthermia >39°C
        temp = victim.body_temperature_c
        if temp < 35.0 or temp > 39.0:
            score += 15
            reasons.append(f"extreme temperature {temp:.1f}°C (+15)")
        elif 35.0 <= temp <= 37.5:
            reasons.append(f"normal temperature {temp:.1f}°C (+0)")
        else:  # 37.5‑39.0 mild fever
            score += 7
            reasons.append(f"fever {temp:.1f}°C (+7)")

        # 5. Accessibility (0‑10)
        # Inaccessible victims are harder to reach, lower urgency adjustment
        access_bonus = victim.accessibility * 10.0
        score += access_bonus
        reasons.append(f"accessibility {victim.accessibility:.2f} (+{access_bonus:.1f})")

        # Ensure score is within 0‑100
        score = max(0.0, min(100.0, score))

        reason_str = f"Score {score:.1f}: " + ", ".join(reasons)
        return score, reason_str

    def prioritize_victims(self, victims: List[TriageVictim]) -> List[Tuple[TriageVictim, float, str]]:
        """
        Sort victims by priority descending.
        Returns list of (victim, score, reason) tuples.
        """
        scored = []
        for victim in victims:
            score, reason = self.compute_priority(victim)
            scored.append((victim, score, reason))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def triage_from_victim_states(self, victim_states: List[object]) -> List[Tuple[str, float, str]]:
        """
        Convenience method that accepts generic victim‑state‑like objects
        (must have the required attributes) and returns sorted IDs with scores.
        Only triages detected victims.
        """
        triage_victims = []
        for vs in victim_states:
            # Skip undetected victims
            if hasattr(vs, 'is_detected') and not vs.is_detected:
                continue
                
            # Convert generic object to TriageVictim
            # Expect attributes: victim_id, injury_severity, conscious, bleeding,
            # body_temperature_c, accessibility, position
            tv = TriageVictim(
                victim_id=getattr(vs, 'victim_id', 'unknown'),
                severity=getattr(vs, 'injury_severity', 'moderate'),
                conscious=getattr(vs, 'conscious', True),
                bleeding=getattr(vs, 'bleeding', 'none'),
                body_temperature_c=getattr(vs, 'body_temperature_c', 37.0),
                accessibility=getattr(vs, 'accessibility', 0.5),
                position=getattr(vs, 'position', (0.0, 0.0, 0.0))
            )
            triage_victims.append(tv)

        prioritized = self.prioritize_victims(triage_victims)
        # Return simplified list: (victim_id, score, reason)
        return [(item[0].victim_id, item[1], item[2]) for item in prioritized]

    def triage_score_victim(self, victim_data: dict) -> dict:
        """
        Use LLM to score victim priority based on injury_type, location, and time_since_report.
        
        Args:
            victim_data: dict with keys:
                - victim_id: str
                - injury_type: str (e.g., "burn", "fracture", "bleeding", "cardiac arrest")
                - location: dict with "x", "y", "z" or tuple
                - time_since_report: float (minutes since incident was reported)
                - additional_context: optional dict with extra medical info
        
        Returns:
            dict with keys:
                - victim_id: str
                - priority: str ("critical", "serious", "moderate", "minor")
                - score: float (0-100)
                - reason: str
                - method: str ("llm" or "fallback")
        """
        victim_id = victim_data.get('victim_id', 'unknown')
        injury_type = victim_data.get('injury_type', 'unknown')
        location = victim_data.get('location', {'x': 0, 'y': 0, 'z': 0})
        time_since_report = victim_data.get('time_since_report', 0)
        additional_context = victim_data.get('additional_context', {})
        
        # Try LLM-based scoring first
        llm_result = self._llm_triage_score(
            victim_id=victim_id,
            injury_type=injury_type,
            location=location,
            time_since_report=time_since_report,
            additional_context=additional_context
        )
        
        if llm_result is not None:
            return llm_result
        
        # Fallback to deterministic scoring
        return self._fallback_triage_score(
            victim_id=victim_id,
            injury_type=injury_type,
            time_since_report=time_since_report,
            additional_context=additional_context
        )
    
    def _llm_triage_score(self, victim_id: str, injury_type: str, location: dict, 
                          time_since_report: float, additional_context: dict) -> dict:
        """
        Call LLM API to get triage priority score.
        Returns None if the call fails.
        """
        # Check for required environment variables
        base_url = os.environ.get('DEEPSEEK_BASE_URL')
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        model = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
        
        if not base_url or not api_key:
            logger.warning("Missing DEEPSEEK_BASE_URL or DEEPSEEK_API_KEY, using fallback")
            return None
        
        if OpenAI is None:
            logger.warning("OpenAI client not available, using fallback")
            return None
        
        try:
            client = OpenAI(base_url=base_url, api_key=api_key)
            
            # Build context for the LLM
            context_parts = [
                f"Injury type: {injury_type}",
                f"Time since report: {time_since_report:.1f} minutes",
                f"Location: x={location.get('x', 0)}, y={location.get('y', 0)}, z={location.get('z', 0)}"
            ]
            
            for key, value in additional_context.items():
                context_parts.append(f"{key}: {value}")
            
            context_str = "\n".join(context_parts)
            
            prompt = f"""You are a medical triage expert for a disaster response system.
Analyze the following victim information and assign a priority level:

{context_str}

Based on the injury type, time elapsed, and other factors, determine the priority:
- "critical": Immediate life-threatening condition requiring immediate rescue
- "serious": Severe injury requiring rescue within minutes to hours
- "moderate": Moderate injury that can wait for rescue
- "minor": Minor injuries, can wait longer

Respond with a JSON object containing:
{{
    "priority": "<priority_level>",
    "reason": "<brief explanation of the priority decision>"
}}

Only respond with the JSON object, no other text."""

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a medical triage expert for disaster response."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                # Handle potential markdown code blocks
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()
                
                llm_result = json.loads(content)
                priority = llm_result.get('priority', 'moderate')
                reason = llm_result.get('reason', 'LLM triage assessment')
                
                # Map priority to score
                priority_to_score = {
                    'critical': 90.0,
                    'serious': 65.0,
                    'moderate': 35.0,
                    'minor': 10.0
                }
                score = priority_to_score.get(priority.lower(), 50.0)
                
                return {
                    'victim_id': victim_id,
                    'priority': priority,
                    'score': score,
                    'reason': f"LLM: {reason}",
                    'method': 'llm'
                }
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                return None
                
        except Exception as e:
            logger.warning(f"LLM triage call failed: {e}")
            return None
    
    def _fallback_triage_score(self, victim_id: str, injury_type: str, 
                                time_since_report: float, additional_context: dict) -> dict:
        """
        Deterministic fallback triage scoring when LLM is unavailable.
        """
        # Base priority by injury type
        injury_priority = {
            'cardiac arrest': 'critical',
            'severe bleeding': 'critical',
            'airway obstruction': 'critical',
            'burns (severe)': 'critical',
            'fracture (open)': 'serious',
            'internal bleeding': 'serious',
            'concussion': 'serious',
            'burns (moderate)': 'moderate',
            'fracture (closed)': 'moderate',
            'lacerations': 'moderate',
            'bruising': 'minor',
            'minor burns': 'minor',
            'scratches': 'minor'
        }
        
        priority = injury_priority.get(injury_type.lower(), 'moderate')
        
        # Adjust based on time since report
        time_multiplier = 1.0
        if time_since_report > 60:  # Over 1 hour
            time_multiplier = 1.3
            if priority == 'minor':
                priority = 'moderate'
            elif priority == 'moderate':
                priority = 'serious'
            elif priority == 'serious':
                priority = 'critical'
        elif time_since_report > 30:  # Over 30 minutes
            time_multiplier = 1.15
            if priority == 'minor':
                priority = 'moderate'
        
        # Calculate score
        base_scores = {
            'critical': 85.0,
            'serious': 60.0,
            'moderate': 35.0,
            'minor': 15.0
        }
        
        score = base_scores.get(priority, 50.0) * time_multiplier
        score = min(100.0, score)
        
        return {
            'victim_id': victim_id,
            'priority': priority,
            'score': score,
            'reason': f"Fallback: {injury_type}, {time_since_report:.1f}min elapsed",
            'method': 'fallback'
        }
    
    def triage_with_llm(self, victim_states: List[object]) -> List[Tuple[str, float, str, str]]:
        """
        Enhanced triage that uses LLM scoring when available.
        Returns list of (victim_id, score, reason, method) tuples sorted by priority.
        """
        results = []
        
        for vs in victim_states:
            # Skip undetected victims
            if hasattr(vs, 'is_detected') and not vs.is_detected:
                continue
            
            # Extract data for LLM scoring
            victim_data = {
                'victim_id': getattr(vs, 'victim_id', 'unknown'),
                'injury_type': getattr(vs, 'injury_type', 'moderate'),
                'location': getattr(vs, 'position', {'x': 0, 'y': 0, 'z': 0}),
                'time_since_report': getattr(vs, 'time_since_report', 0),
                'additional_context': {
                    'conscious': getattr(vs, 'conscious', True),
                    'bleeding': getattr(vs, 'bleeding', 'none'),
                    'body_temperature_c': getattr(vs, 'body_temperature_c', 37.0),
                    'accessibility': getattr(vs, 'accessibility', 0.5)
                }
            }
            
            result = self.triage_score_victim(victim_data)
            results.append((
                result['victim_id'],
                result['score'],
                result['reason'],
                result['method']
            ))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results
