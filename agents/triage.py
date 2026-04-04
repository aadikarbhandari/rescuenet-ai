"""
Triage Agent for RescueNet AI
Priority scoring and victim prioritization using DeepSeek LLM with fallback rule-based scoring.
"""
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
import math
import os
import json
import ast
import logging
import time
import requests

from config.settings import Settings


logger = logging.getLogger(__name__)


@dataclass
class TriageVictim:
    """Extended victim data for triage scoring."""
    victim_id: str
    severity: str = "moderate"  # "minor", "moderate", "severe", "critical"
    conscious: bool = True
    bleeding: str = "none"  # "none", "mild", "moderate", "severe"
    body_temperature_c: float = 37.0
    accessibility: float = 0.5  # 0.0 (blocked) to 1.0 (fully accessible)
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    injury_type: str = "unknown"
    time_since_report: float = 0.0
    additional_context: Dict[str, Any] = field(default_factory=dict)


class TriageAgent:
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the TriageAgent.
        
        Args:
            settings: Settings object containing DeepSeek configuration.
                     If None, reads from environment variables.
        """
        self.settings = settings
        self._victim_cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # Cache TTL in seconds
        
    @property
    def _base_url(self) -> str:
        """Get DeepSeek base URL from settings or environment."""
        if self.settings:
            return getattr(self.settings, 'deepseek_base_url', None) or os.environ.get('DEEPSEEK_BASE_URL', '')
        return os.environ.get('DEEPSEEK_BASE_URL', '')
    
    @property
    def _api_key(self) -> str:
        """Get DeepSeek API key from settings or environment."""
        if self.settings:
            return getattr(self.settings, 'deepseek_api_key', None) or os.environ.get('DEEPSEEK_API_KEY', '')
        return os.environ.get('DEEPSEEK_API_KEY', '')
    
    @property
    def _model(self) -> str:
        """Get DeepSeek model from settings or environment."""
        if self.settings:
            return getattr(self.settings, 'deepseek_model', None) or os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
        return os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
    
    def _check_llm_available(self) -> bool:
        """Check if LLM is properly configured."""
        return bool(self._base_url and self._api_key)

    def _build_triage_prompt(self, victim: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> str:
        """Build the prompt for DeepSeek LLM triage scoring."""
        victim_info = json.dumps(victim, indent=2)
        context_info = json.dumps(context, indent=2) if context else "{}"
        
        prompt = f"""You are a medical triage expert for disaster response. Analyze the following victim data and assign a rescue priority score.

VICTIM DATA:
{victim_info}

CONTEXT:
{context_info}

Based on the victim data and context, provide a triage assessment in JSON format with the following fields:
- "score": integer 0-100 (higher = more urgent)
- "priority": "critical" | "high" | "medium" | "low"
- "reasoning": one short sentence (max 20 words)
- "recommended_action": "extract" | "deliver_supplies" | "scout" | "monitor"

Consider these factors:
1. Severity of injuries (critical conditions like cardiac arrest, severe bleeding = highest priority)
2. Time since incident (longer time = worse outcomes)
3. Consciousness state (unconscious = more urgent)
4. Vital signs (abnormal temperature, severe bleeding)
5. Accessibility of location (easier access = higher effective priority for extraction)
6. Available resources and current rescue queue

Return ONLY valid JSON object, no markdown/code fences/no extra text."""
        return prompt

    def _parse_llm_response(self, response_text: Optional[str]) -> Optional[Dict[str, Any]]:
        """Parse the LLM response JSON."""
        try:
            if not response_text:
                logger.warning("LLM response content is empty; using fallback triage.")
                return None

            # Try to find JSON in the response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Extract the first JSON object if model returned extra text
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx + 1]
            
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Some providers return python-style dict strings with single quotes.
                result = ast.literal_eval(response_text)

            if isinstance(result, list) and result:
                result = result[0]
            if not isinstance(result, dict):
                logger.warning("LLM triage response is not a JSON object; using fallback triage.")
                return None

            # Normalize common alias keys from different providers/models
            if 'score' not in result:
                result['score'] = result.get('triage_score', result.get('urgency_score'))
            if 'priority' not in result:
                result['priority'] = result.get('severity', result.get('triage_priority'))
            if 'recommended_action' not in result:
                result['recommended_action'] = result.get('action', result.get('recommended_next_step'))
            if 'reasoning' not in result:
                result['reasoning'] = result.get('reason', result.get('explanation', ''))

            # Normalize common value variants so provider wording still maps to contract.
            if 'priority' in result and isinstance(result['priority'], str):
                p = result['priority'].strip().lower()
                if p in ('urgent', 'emergency'):
                    p = 'critical'
                elif p in ('severe',):
                    p = 'high'
                result['priority'] = p

            if 'recommended_action' in result and isinstance(result['recommended_action'], str):
                a = result['recommended_action'].strip().lower()
                if 'extract' in a or 'evac' in a or 'medical facility' in a:
                    a = 'extract'
                elif 'supply' in a:
                    a = 'deliver_supplies'
                elif 'scout' in a or 'assess' in a or 'survey' in a:
                    a = 'scout'
                elif 'monitor' in a or 'observe' in a:
                    a = 'monitor'
                result['recommended_action'] = a

            if 'score' in result and isinstance(result['score'], str):
                try:
                    result['score'] = float(result['score'])
                except ValueError:
                    pass
            
            # Validate required fields
            required_fields = ['score', 'priority', 'reasoning', 'recommended_action']
            for field_name in required_fields:
                if field_name not in result:
                    logger.warning(f"Missing required field in LLM response: {field_name}")
                    return None
            
            # Validate score range
            if not isinstance(result['score'], (int, float)) or not (0 <= result['score'] <= 100):
                logger.warning(f"Invalid score value: {result['score']}")
                return None
            
            # Validate priority
            valid_priorities = ['critical', 'high', 'medium', 'low']
            if result['priority'] not in valid_priorities:
                logger.warning(f"Invalid priority: {result['priority']}")
                return None
            
            # Validate recommended_action
            valid_actions = ['extract', 'deliver_supplies', 'scout', 'monitor']
            if result['recommended_action'] not in valid_actions:
                logger.warning(f"Invalid recommended_action: {result['recommended_action']}")
                return None
            
            return result
            
        except (json.JSONDecodeError, SyntaxError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return None
        except Exception as e:
            logger.warning(f"Error parsing LLM response: {e}")
            return None

    def _call_deepseek(self, prompt: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Call DeepSeek API with retry logic.
        
        Args:
            prompt: The prompt to send to DeepSeek
            max_retries: Maximum number of retry attempts
            
        Returns:
            Parsed JSON response or None on failure
        """
        if not self._check_llm_available():
            logger.warning("DeepSeek not configured - LLM triage unavailable")
            return None
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}"
        }
        
        json_schema = {
            "name": "triage_assessment",
            "schema": {
                "type": "object",
                "properties": {
                    "score": {"type": "number"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "reasoning": {"type": "string"},
                    "recommended_action": {"type": "string", "enum": ["extract", "deliver_supplies", "scout", "monitor"]},
                },
                "required": ["score", "priority", "reasoning", "recommended_action"],
                "additionalProperties": True
            },
            "strict": True
        }

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a disaster response medical triage expert. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,  # Low temperature for consistent triage decisions
            "max_tokens": 500,
            "response_format": {"type": "json_schema", "json_schema": json_schema}
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0].get('message', {}).get('content')
                        parsed = self._parse_llm_response(content)
                        if parsed is not None:
                            return parsed
                        repaired = self._attempt_json_repair(content)
                        if repaired is not None:
                            return repaired
                elif response.status_code == 400 and "response_format" in response.text:
                    # Fallback for providers that don't support structured output hints
                    payload.pop("response_format", None)
                    logger.warning("Provider rejected response_format; retrying without schema enforcement.")
                    continue
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Rate limited by DeepSeek API, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 401:
                    logger.error("DeepSeek API authentication failed - invalid API key")
                    return None
                else:
                    logger.warning(f"DeepSeek API returned status {response.status_code}: {response.text[:200]}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"DeepSeek API timeout on attempt {attempt + 1}/{max_retries}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"DeepSeek API connection error on attempt {attempt + 1}/{max_retries}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error calling DeepSeek API: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))
        
        logger.error(f"Failed to get valid response from DeepSeek after {max_retries} attempts")
        return None

    def _attempt_json_repair(self, raw_content: Optional[str]) -> Optional[Dict[str, Any]]:
        """Ask LLM to repair malformed JSON payload into expected triage schema."""
        if not raw_content:
            return None
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}"
            }
            repair_prompt = (
                "Convert the following text into a valid JSON object with keys: "
                "score, priority, reasoning, recommended_action. Return JSON only.\n\n"
                f"INPUT:\n{raw_content}"
            )
            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": "You only output valid JSON object."},
                    {"role": "user", "content": repair_prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 220
            }
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=12
            )
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                parsed = self._parse_llm_response(content)
                if parsed is not None:
                    logger.info("Recovered triage response using JSON repair pass.")
                return parsed
        except Exception as e:
            logger.debug(f"JSON repair pass failed: {e}")
        return None

    def score_victim_llm(self, victim: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Use DeepSeek to score a single victim. Returns score + reasoning.
        
        Args:
            victim: Dictionary containing victim information
            context: Optional context dictionary with additional information
            
        Returns:
            Dictionary with keys:
                - victim_id: str
                - score: float (0-100)
                - priority: str ("critical", "high", "medium", "low")
                - reasoning: str
                - recommended_action: str ("extract", "deliver_supplies", "scout", "monitor")
                - method: str ("llm" or "fallback")
        """
        victim_id = victim.get('victim_id', 'unknown')
        context = context or {}
        
        # Check cache first
        cache_key = f"{victim_id}_{hash(json.dumps(victim, sort_keys=True))}"
        if cache_key in self._victim_cache:
            cached = self._victim_cache[cache_key]
            if time.time() - cached.get('_cached_at', 0) < self._cache_ttl:
                logger.debug(f"Using cached triage result for victim {victim_id}")
                return cached
        
        # Try LLM-based scoring
        if self._check_llm_available():
            prompt = self._build_triage_prompt(victim, context)
            llm_result = self._call_deepseek(prompt, max_retries=1)
            
            if llm_result is not None:
                result = {
                    'victim_id': victim_id,
                    'score': float(llm_result.get('score', 50)),
                    'priority': llm_result.get('priority', 'medium'),
                    'reasoning': llm_result.get('reasoning', ''),
                    'recommended_action': llm_result.get('recommended_action', 'monitor'),
                    'method': 'llm'
                }
                # Cache the result
                result['_cached_at'] = time.time()
                self._victim_cache[cache_key] = result
                logger.info(f"LLM triage for victim {victim_id}: score={result['score']}, priority={result['priority']}")
                return result
        
        # Fallback to rule-based scoring
        logger.info(f"Using fallback rule-based triage for victim {victim_id}")
        return self._fallback_score(victim, context)

    def _fallback_score(self, victim: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Rule-based fallback scoring when LLM is unavailable.
        
        Args:
            victim: Dictionary containing victim information
            context: Optional context dictionary
            
        Returns:
            Dictionary with triage assessment
        """
        victim_id = victim.get('victim_id', 'unknown')
        
        # Extract victim attributes with defaults
        severity = victim.get('severity') or victim.get('injury_severity', 'moderate')
        conscious = victim.get('conscious', True)
        bleeding = victim.get('bleeding', 'none')
        body_temp = victim.get('body_temperature_c', victim.get('body_temperature', 37.0))
        accessibility = victim.get('accessibility', 0.5)
        time_since_report = victim.get('time_since_report', 0)
        injury_type = victim.get('injury_type', 'unknown')
        
        score = 0.0
        reasons = []
        
        # 1. Severity weight (0-30)
        severity_weights = {
            "critical": 30,
            "severe": 22,
            "moderate": 14,
            "minor": 6
        }
        severity_score = severity_weights.get(severity, 14)
        score += severity_score
        reasons.append(f"severity={severity} (+{severity_score})")
        
        # 2. Injury type specific scoring
        critical_injuries = ['cardiac arrest', 'respiratory failure', 'severe burns', 'amputation']
        high_injuries = ['bleeding', 'fracture', 'shock', 'head injury']
        
        if injury_type in critical_injuries:
            score += 20
            reasons.append(f"critical_injury={injury_type} (+20)")
        elif injury_type in high_injuries:
            score += 12
            reasons.append(f"high_injury={injury_type} (+12)")
        
        # 3. Consciousness (0-20)
        if not conscious:
            score += 20
            reasons.append("unconscious (+20)")
        
        # 4. Bleeding (0-25)
        bleeding_weights = {
            "severe": 25,
            "moderate": 15,
            "mild": 8,
            "none": 0
        }
        bleeding_score = bleeding_weights.get(bleeding, 0)
        score += bleeding_score
        reasons.append(f"bleeding={bleeding} (+{bleeding_score})")
        
        # 5. Body temperature (0-15)
        if body_temp < 35.0 or body_temp > 39.0:
            score += 15
            reasons.append(f"extreme_temp={body_temp}°C (+15)")
        elif 37.5 < body_temp <= 39.0:
            score += 7
            reasons.append(f"fever={body_temp}°C (+7)")
        
        # 6. Time since report (0-15)
        if time_since_report > 60:
            score += 15
            reasons.append(f"time_delay={time_since_report:.0f}min (+15)")
        elif time_since_report > 30:
            score += 10
            reasons.append(f"time_delay={time_since_report:.0f}min (+10)")
        elif time_since_report > 15:
            score += 5
            reasons.append(f"time_delay={time_since_report:.0f}min (+5)")
        
        # 7. Accessibility - easier access = higher effective priority
        accessibility_bonus = accessibility * 10.0
        score += accessibility_bonus
        reasons.append(f"accessibility={accessibility:.2f} (+{accessibility_bonus:.1f})")
        
        # Ensure score is within 0-100
        score = max(0.0, min(100.0, score))
        
        # Determine priority category
        if score >= 80:
            priority = "critical"
            recommended_action = "extract"
        elif score >= 60:
            priority = "high"
            recommended_action = "extract"
        elif score >= 40:
            priority = "medium"
            recommended_action = "deliver_supplies"
        else:
            priority = "low"
            recommended_action = "monitor"
        
        reasoning = f"Rule-based score {score:.1f}: {', '.join(reasons)}"
        
        result = {
            'victim_id': victim_id,
            'score': score,
            'priority': priority,
            'reasoning': reasoning,
            'recommended_action': recommended_action,
            'method': 'fallback'
        }
        
        # Cache the result
        cache_key = f"{victim_id}_{hash(json.dumps(victim, sort_keys=True))}"
        result['_cached_at'] = time.time()
        self._victim_cache[cache_key] = result
        
        return result

    def prioritize_all(self, victims: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Score all detected victims, sort descending by score, return prioritized list.
        
        Args:
            victims: List of victim dictionaries
            context: Optional context dictionary with additional information
            
        Returns:
            List of victim dictionaries with triage scores, sorted by priority (highest first)
        """
        if not victims:
            logger.warning("No victims provided for prioritization")
            return []
        
        context = context or {}
        scored_victims = []
        
        for victim in victims:
            # Skip undetected victims if the attribute exists
            if isinstance(victim, dict):
                if not victim.get('is_detected', True):
                    continue
            elif hasattr(victim, 'is_detected') and not victim.is_detected:
                continue
            
            # Score the victim
            triage_result = self.score_victim_llm(victim, context)
            scored_victims.append(triage_result)
        
        # Sort by score descending
        scored_victims.sort(key=lambda x: x['score'], reverse=True)
        
        # Add rank information
        for rank, victim in enumerate(scored_victims, 1):
            victim['rank'] = rank
        
        logger.info(f"Prioritized {len(scored_victims)} victims")
        return scored_victims

    def get_victims_by_action(self, prioritized_victims: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group victims by recommended action.
        
        Args:
            prioritized_victims: List of victim dictionaries with recommended_action
            
        Returns:
            Dictionary mapping action to list of victims
        """
        action_groups = {
            'extract': [],
            'deliver_supplies': [],
            'scout': [],
            'monitor': []
        }
        
        for victim in prioritized_victims:
            action = victim.get('recommended_action', 'monitor')
            if action in action_groups:
                action_groups[action].append(victim)
        
        return action_groups

    def clear_cache(self):
        """Clear the victim cache."""
        self._victim_cache.clear()
        logger.debug("Victim cache cleared")

    # Legacy methods for backward compatibility
    
    def compute_priority(self, victim: TriageVictim) -> Tuple[float, str]:
        """
        Compute a priority score between 0 and 100 (legacy method).
        
        Args:
            victim: TriageVictim dataclass instance
            
        Returns:
            Tuple of (score, reason_string)
        """
        victim_dict = {
            'victim_id': victim.victim_id,
            'severity': victim.severity,
            'conscious': victim.conscious,
            'bleeding': victim.bleeding,
            'body_temperature_c': victim.body_temperature_c,
            'accessibility': victim.accessibility,
            'injury_type': victim.injury_type,
            'time_since_report': victim.time_since_report
        }
        result = self._fallback_score(victim_dict)
        return result['score'], result['reasoning']

    def prioritize_victims(self, victims: List[TriageVictim]) -> List[Tuple[TriageVictim, float, str]]:
        """
        Sort victims by priority descending (legacy method).
        
        Args:
            victims: List of TriageVictim instances
            
        Returns:
            List of (victim, score, reason) tuples
        """
        scored = []
        for victim in victims:
            score, reason = self.compute_priority(victim)
            scored.append((victim, score, reason))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def triage_from_victim_states(self, victim_states: List[Any]) -> List[Tuple[str, float, str]]:
        """
        Convenience method for backward compatibility.
        
        Args:
            victim_states: List of victim state objects
            
        Returns:
            List of (victim_id, score, reason) tuples
        """
        victims = []
        for vs in victim_states:
            if hasattr(vs, 'is_detected') and not vs.is_detected:
                continue
            
            victim_dict = {
                'victim_id': getattr(vs, 'victim_id', 'unknown'),
                'severity': getattr(vs, 'injury_severity', 'moderate'),
                'conscious': getattr(vs, 'conscious', True),
                'bleeding': getattr(vs, 'bleeding', 'none'),
                'body_temperature_c': getattr(vs, 'body_temperature_c', 37.0),
                'accessibility': getattr(vs, 'accessibility', 0.5),
                'injury_type': getattr(vs, 'injury_type', 'unknown'),
                'time_since_report': getattr(vs, 'time_since_report', 0)
            }
            victims.append(victim_dict)
        
        prioritized = self.prioritize_all(victims)
        return [(v['victim_id'], v['score'], v['reasoning']) for v in prioritized]

    def triage_score_victim(self, victim_data: dict) -> dict:
        """
        Use LLM to score victim priority based on injury data (legacy method).
        
        Args:
            victim_data: Dictionary with victim information
            
        Returns:
            Dictionary with triage assessment
        """
        return self.score_victim_llm(victim_data, {})

    def _llm_triage_score(self, victim_id: str, injury_type: str, location: dict, 
                          time_since_report: float, additional_context: dict) -> Optional[dict]:
        """
        Internal LLM triage scoring (legacy method).
        
        Args:
            victim_id: Victim identifier
            injury_type: Type of injury
            location: Location dict
            time_since_report: Time since report
            additional_context: Additional context
            
        Returns:
            Triage result or None
        """
        victim = {
            'victim_id': victim_id,
            'injury_type': injury_type,
            'location': location,
            'time_since_report': time_since_report,
            'additional_context': additional_context
        }
        return self.score_victim_llm(victim, additional_context)

    def _fallback_triage_score(self, victim_id: str, injury_type: str, 
                               time_since_report: float, additional_context: dict) -> dict:
        """
        Fallback triage scoring (legacy method).
        
        Args:
            victim_id: Victim identifier
            injury_type: Type of injury
            time_since_report: Time since report
            additional_context: Additional context
            
        Returns:
            Triage result
        """
        victim = {
            'victim_id': victim_id,
            'injury_type': injury_type,
            'time_since_report': time_since_report,
            'additional_context': additional_context
        }
        return self._fallback_score(victim, additional_context)
