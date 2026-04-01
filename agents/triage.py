"""
Priority scoring + drone assignment
"""
from typing import List, Tuple
from dataclasses import dataclass
import math

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
