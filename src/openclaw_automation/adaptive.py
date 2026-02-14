"""Adaptive retry layer for browser-agent-based award search runners.

Wraps run_browser_agent_goal() with:
- Failure diagnosis from agent result text + status
- Goal adaptation on retry (prepends warnings + airline hints)
- Result validation (miles vs dollars, sane data)
- Cooldown between retries
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .browser_agent_adapter import run_browser_agent_goal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Airline-specific hints (appended on retry, not first attempt)
# ---------------------------------------------------------------------------

AIRLINE_HINTS: Dict[str, List[str]] = {
    "united": [
        "After switching 'Show price in' to Miles, the date field clears. Re-enter the date and click Update.",
        "Do NOT select 'Money + Miles'. Select pure 'Miles'.",
        "Use the direct URL to navigate — do NOT fill the booking form.",
    ],
    "delta": [
        "You MUST click 'Shop with Miles' checkbox BEFORE clicking 'Find Flights'.",
        "If the checkbox isn't in the accessibility tree, use mouse_click at x=50, y=173.",
        "ALWAYS navigate to the direct URL even if the form looks pre-filled.",
        "DO NOT click CONTINUE on results — the individual flights page crashes Chrome.",
    ],
    "aeromexico": [
        "The page is in SPANISH. The points toggle says 'Usar mis Puntos Aeromexico Rewards'.",
        "If toggle not in a11y tree, use mouse_click at approximately x=345, y=520.",
        "Type characters one-by-one (use press action) to avoid reCAPTCHA detection.",
    ],
    "singapore": [
        "Use slow typing (delay=120ms) for autocomplete fields.",
        "The Vue.js calendar requires clicking suggest-items, not direct input.",
        "Do NOT use form.submit() or fetch() — they trigger Akamai CAPTCHA.",
    ],
}

# Cooldown between retries (seconds)
RETRY_COOLDOWNS = [5, 15, 30]

# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------


@dataclass
class Diagnosis:
    failure_type: str  # login_wall, captcha, wrong_pricing, empty_results,
    #                    page_crash, element_not_found, timeout, unknown
    detail: str
    retryable: bool


def diagnose(airline: str, agent_result: Dict[str, Any]) -> Diagnosis:
    """Diagnose a failed or invalid agent run from its result dict."""
    result_obj = agent_result.get("result") or {}
    if isinstance(result_obj, dict):
        status = result_obj.get("status", "")
        result_text = str(result_obj.get("result", ""))
    else:
        status = ""
        result_text = str(result_obj)

    error_text = str(agent_result.get("error", ""))
    combined = f"{result_text} {error_text}".lower()

    # Captcha (not retryable)
    if re.search(r"captcha|recaptcha|hcaptcha|bot.detect", combined):
        return Diagnosis("captcha", "CAPTCHA or bot detection triggered", retryable=False)

    # Rate limited (not retryable)
    if re.search(r"rate.limit|too.many.requests|429", combined):
        return Diagnosis("rate_limited", "Rate limited by the website", retryable=False)

    # Login wall
    if re.search(r"sign.in|log.in|login.required|session.expired|please.sign", combined):
        if status in ("stuck", "max_steps", ""):
            return Diagnosis("login_wall", "Agent hit a login/sign-in wall", retryable=True)

    # Page crash / target closed
    if re.search(r"target.closed|page.crash|browser.crash|context.destroy|net::err", combined):
        return Diagnosis("page_crash", "Browser page crashed or was closed", retryable=True)

    # Timeout / max steps
    if status == "max_steps":
        return Diagnosis("timeout", "Agent exhausted max steps without completing", retryable=True)

    # Wrong pricing (dollars instead of miles)
    has_dollars = bool(re.search(r"\$\d", combined))
    has_miles = bool(re.search(r"miles|puntos|points", combined))
    if has_dollars and not has_miles:
        return Diagnosis("wrong_pricing", "Results show cash prices, not miles/points", retryable=True)

    # Empty results
    if status == "success" and not result_text.strip():
        return Diagnosis("empty_results", "Agent completed but returned no result text", retryable=True)
    if re.search(r"no.flights|no.results|no.availability|unavailable", combined):
        return Diagnosis("empty_results", "No flights/results found", retryable=True)

    # Element not found
    if re.search(r"element.not.found|could.not.find|selector.not|not.visible", combined):
        return Diagnosis("element_not_found", "Agent couldn't locate a required UI element", retryable=True)

    # Stuck without specific reason
    if status == "stuck":
        return Diagnosis("stuck", f"Agent got stuck: {result_text[:100]}", retryable=True)

    # Generic error
    if not agent_result.get("ok"):
        return Diagnosis("unknown", f"Run failed: {error_text[:150]}", retryable=True)

    # Validation-triggered (ok=True but invalid result)
    return Diagnosis("unknown", "Result did not pass validation", retryable=True)


# ---------------------------------------------------------------------------
# Goal adaptation
# ---------------------------------------------------------------------------

_DIAGNOSIS_WARNINGS = {
    "login_wall": (
        "WARNING: The previous attempt hit a login/sign-in wall. "
        "If you see a 'Sign in' popup or login page, close it immediately and continue. "
        "Do NOT attempt to fill in login credentials unless explicitly told to."
    ),
    "wrong_pricing": (
        "WARNING: The previous attempt showed CASH prices instead of miles/points. "
        "You MUST switch the pricing view to miles/points before reporting results."
    ),
    "page_crash": (
        "WARNING: The previous attempt crashed the browser page. "
        "Be careful with your actions — avoid excessive scrolling, "
        "do not click 'Continue' or secondary result pages, and wait for pages to load."
    ),
    "element_not_found": (
        "WARNING: The previous attempt couldn't find a required UI element. "
        "If an element isn't in the accessibility tree, try using mouse_click "
        "with approximate coordinates. Take a screenshot first to orient yourself."
    ),
    "empty_results": (
        "WARNING: The previous attempt returned no results. "
        "Make sure the search actually completes — wait for loading spinners to finish."
    ),
    "stuck": (
        "WARNING: The previous attempt got stuck. "
        "Follow the action sequence strictly. If a step fails, skip it and continue."
    ),
    "timeout": (
        "WARNING: The previous attempt ran out of steps. "
        "Be more efficient — don't repeat failed actions. Move on if something doesn't work."
    ),
}


def adapt_goal(original_goal: str, diag: Diagnosis, airline: str) -> str:
    """Prepend warnings and hints to the original goal for retry."""
    parts: List[str] = []

    # Add diagnosis-specific warning
    warning = _DIAGNOSIS_WARNINGS.get(diag.failure_type)
    if warning:
        parts.append(warning)

    # Add airline hints on retry
    hints = AIRLINE_HINTS.get(airline, [])
    if hints:
        parts.append("=== KNOWN ISSUES FOR THIS AIRLINE ===")
        for hint in hints:
            parts.append(f"- {hint}")

    if parts:
        parts.append("")  # blank line separator
        parts.append("=== ORIGINAL INSTRUCTIONS (follow these) ===")
        parts.append("")

    parts.append(original_goal)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Result validation
# ---------------------------------------------------------------------------

def validate_result(
    airline: str,
    agent_result: Dict[str, Any],
    inputs: Dict[str, Any],
) -> Tuple[bool, str]:
    """Check if agent result is valid. Returns (is_valid, reason)."""
    result_obj = agent_result.get("result") or {}
    if isinstance(result_obj, dict):
        status = result_obj.get("status", "")
        result_text = str(result_obj.get("result", ""))
    else:
        status = ""
        result_text = str(result_obj)

    # Must have completed successfully
    if status not in ("success", ""):
        return False, f"Agent status is '{status}', not 'success'"

    if not result_text.strip():
        return False, "Empty result text"

    text_lower = result_text.lower()

    # Check for miles/points presence (airline-specific)
    if airline == "aeromexico":
        if not re.search(r"puntos|points|millas|pts", text_lower):
            if re.search(r"\$\d|mxn|pesos", text_lower):
                return False, "Shows peso/dollar prices, not puntos"
    elif airline == "united":
        # Reject if combo pricing is present and no standalone miles line exists
        combo_lines = re.findall(r".*\$[\d,]+\s*\+\s*[\d,]+\s*miles.*", text_lower)
        all_miles_lines = re.findall(r".*\d[\d,]*\s*miles.*", text_lower)
        if combo_lines and len(combo_lines) >= len(all_miles_lines):
            return False, "Only combo pricing ($ + miles) found, not pure miles"
    elif airline == "delta":
        if not re.search(r"miles|mi\b", text_lower):
            if re.search(r"\$\d", text_lower):
                return False, "Shows dollar prices, not miles"
    elif airline == "singapore":
        if not re.search(r"miles|mi\b", text_lower):
            return False, "No miles data in result"

    return True, "ok"


# ---------------------------------------------------------------------------
# Core adaptive runner
# ---------------------------------------------------------------------------

def adaptive_run(
    *,
    goal: str,
    url: str,
    max_steps: int,
    airline: str,
    inputs: Dict[str, Any],
    max_attempts: int = 3,
    trace: bool = True,
    use_vision: bool = True,
) -> Dict[str, Any]:
    """Run browser agent with adaptive retry on failure.

    Returns the same dict as run_browser_agent_goal() plus:
    - "attempts": number of attempts made
    - "diagnoses": list of Diagnosis details from failed attempts
    """
    diagnoses: List[str] = []
    current_goal = goal
    current_max_steps = max_steps
    last_result: Dict[str, Any] = {"ok": False, "error": "no attempts made", "result": None}

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "adaptive_run [%s] attempt %d/%d (max_steps=%d)",
            airline, attempt, max_attempts, current_max_steps,
        )

        agent_result = run_browser_agent_goal(
            goal=current_goal,
            url=url,
            max_steps=current_max_steps,
            trace=trace,
            use_vision=use_vision,
        )
        last_result = agent_result

        if agent_result.get("ok"):
            # Validate the result
            is_valid, reason = validate_result(airline, agent_result, inputs)
            if is_valid:
                logger.info(
                    "adaptive_run [%s] attempt %d succeeded (valid result)",
                    airline, attempt,
                )
                agent_result["attempts"] = attempt
                agent_result["diagnoses"] = diagnoses
                return agent_result
            else:
                logger.warning(
                    "adaptive_run [%s] attempt %d: ok but invalid — %s",
                    airline, attempt, reason,
                )
                diag = diagnose(airline, agent_result)
                diag_str = f"attempt {attempt}: valid=False ({reason}), diag={diag.failure_type}: {diag.detail}"
                diagnoses.append(diag_str)
        else:
            diag = diagnose(airline, agent_result)
            diag_str = f"attempt {attempt}: ok=False, diag={diag.failure_type}: {diag.detail}"
            diagnoses.append(diag_str)
            logger.warning("adaptive_run [%s] %s", airline, diag_str)

            if not diag.retryable:
                logger.info(
                    "adaptive_run [%s] not retryable (%s), giving up",
                    airline, diag.failure_type,
                )
                break

        # Prepare for retry
        if attempt < max_attempts:
            diag = diagnose(airline, agent_result)
            current_goal = adapt_goal(goal, diag, airline)

            # Bump max_steps on timeout
            if diag.failure_type == "timeout":
                current_max_steps = current_max_steps + 10

            # Cooldown
            cooldown_idx = min(attempt - 1, len(RETRY_COOLDOWNS) - 1)
            cooldown = RETRY_COOLDOWNS[cooldown_idx]
            logger.info("adaptive_run [%s] cooling down %ds before retry", airline, cooldown)
            time.sleep(cooldown)

    # All attempts exhausted
    last_result["attempts"] = max_attempts
    last_result["diagnoses"] = diagnoses
    return last_result
