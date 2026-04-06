"""
The triage agent assigns priority to victims.
The triage score is calculated based on factors such as:
- Motion: If the victim is immobile, they may be in more critical condition.
- Temperature: A low body temperature can indicate hypothermia, which is life-threatening.
- Location: Victims in flood zones or other hazardous areas may require urgent attention.

Example scoring:
* critical
* injured
* safe
"""

class TriageAgent:

    def score(self, victim):
        severity = victim.get("severity", 1)
        distance = victim.get("distance", 0)
        return severity * 10 - distance
    
    def triage_score(self, victim):
        score = 0
        if victim.motion == False:
            score += 50
        if victim.temperature_low:
            score += 30
        if victim.in_flood_zone:
            score += 20
        return score