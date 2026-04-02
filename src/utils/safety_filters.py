"""Prohibited content detection patterns for safety verification."""
import re

from .logging_config import get_logger

logger = get_logger(__name__)


# === Diagnosis Terms ===
DIAGNOSIS_PATTERNS = [
    r"确诊",  # Diagnosed/confirmed
    r"诊断",  # Diagnosis
    r"你得的是",  # You have
    r"是.*病$",  # Is XX disease
    r"患有",  # Suffering from
    r"得了",  # Got/contracted
    r"一定是",  # Definitely is
]

# === Prescription Terms ===
PRESCRIPTION_PATTERNS = [
    r"\d+mg",  # Dosage in mg
    r"每次.*片",  # Each time X pills
    r"每日.*次",  # X times per day
    r"剂量",  # Dosage
    r"服用",  # Take/consume
    r"用药",  # Medication
    r"吃药",  # Eat medicine
    r"注射",  # Inject
    r"静脉滴注",  # IV drip
]

# === Delay-Care Terms ===
DELAY_CARE_PATTERNS = [
    r"不用就医",  # No need to see doctor
    r"不用看医生",  # No need to see doctor
    r"肯定没事",  # Definitely fine
    r"不需要治疗",  # No treatment needed
    r"可以不用管",  # Can ignore it
    r"无需就医",  # No need for medical care
    r"不用去医院",  # No need to go to hospital
]

# Compile regex patterns
DIAGNOSIS_REGEX = re.compile("|".join(DIAGNOSIS_PATTERNS), re.IGNORECASE)
PRESCRIPTION_REGEX = re.compile("|".join(PRESCRIPTION_PATTERNS), re.IGNORECASE)
DELAY_CARE_REGEX = re.compile("|".join(DELAY_CARE_PATTERNS), re.IGNORECASE)


def contains_diagnosis(text: str) -> bool:
    """Check if text contains diagnosis terms.

    Args:
        text: Text to check

    Returns:
        True if diagnosis terms found
    """
    return bool(DIAGNOSIS_REGEX.search(text))


def contains_prescription(text: str) -> bool:
    """Check if text contains prescription terms.

    Args:
        text: Text to check

    Returns:
        True if prescription terms found
    """
    return bool(PRESCRIPTION_REGEX.search(text))


def contains_delay_care(text: str) -> bool:
    """Check if text contains delay-care language.

    Args:
        text: Text to check

    Returns:
        True if delay-care terms found
    """
    return bool(DELAY_CARE_REGEX.search(text))


def check_prohibited_content(text: str) -> list[str]:
    """Check for all prohibited content types.

    Args:
        text: Text to check

    Returns:
        List of violation types found
    """
    violations = []

    if contains_diagnosis(text):
        violations.append("diagnosis")
        logger.warning("Diagnosis language detected in output")

    if contains_prescription(text):
        violations.append("prescription")
        logger.warning("Prescription language detected in output")

    if contains_delay_care(text):
        violations.append("delay_care")
        logger.warning("Delay-care language detected in output")

    return violations


def sanitize_response(text: str) -> tuple[str, list[str]]:
    """Sanitize response by removing prohibited content.

    Args:
        text: Original text

    Returns:
        Tuple of (sanitized_text, violations_found)
    """
    violations = check_prohibited_content(text)

    if not violations:
        return text, []

    # If violations found, rewrite with safer language
    # For now, return original with violations list
    # In production, this would trigger LLM rewrite
    return text, violations
