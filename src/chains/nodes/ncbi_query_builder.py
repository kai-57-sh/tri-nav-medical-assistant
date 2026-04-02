"""NCBI Query Builder node (Node 12).

Builds optimized search queries for PubMed literature retrieval.
Uses symptom schema and case domain to construct relevant queries.
"""
from typing import Any

from src.chains.nodes.base import safe_node
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@safe_node("NCBIQueryBuilder")
async def ncbi_query_builder(state: dict[str, Any]) -> dict[str, Any]:
    """Build NCBI PubMed search query from symptom schema.

    Constructs optimized query combining:
    - Body part (anatomy)
    - Primary symptoms
    - Medical specialty domain (if available)

    Uses PubMed query syntax:
    - Quotes for exact phrases: "chest pain"
    - AND for combining terms: chest AND pain
    - MeSH terms when available: "Myocardial Infarction"[MeSH]

    Args:
        state: Current workflow state

    Returns:
        Updated state with ncbi_query string
    """
    symptom_schema = state.get("symptom_schema", {})
    case_domain = state.get("case_domain")
    session_id = state.get("session_id")

    if not symptom_schema:
        logger.warning(
            "No symptom schema available for NCBI query building",
            extra={"session_id": session_id}
        )
        return {"ncbi_query": ""}

    # Extract key terms
    body_part = symptom_schema.get("body_part", "")
    symptoms = symptom_schema.get("symptoms", [])

    if not symptoms:
        logger.warning(
            "No symptoms available for NCBI query building",
            extra={"session_id": session_id}
        )
        return {"ncbi_query": ""}

    # Build query terms
    query_terms = []

    # Add body part if available (anatomical context)
    if body_part:
        # Use English mapping for common body parts
        body_part_en = _map_body_part_to_english(body_part)
        query_terms.append(f'"{body_part_en}"')

    # Add primary symptom (most important)
    primary_symptom = symptoms[0] if symptoms else ""
    if primary_symptom:
        symptom_en = _map_symptom_to_english(primary_symptom)
        query_terms.append(f'"{symptom_en}"')

    # Add medical domain if available (improves relevance)
    if case_domain:
        domain_en = _map_domain_to_english(case_domain)
        query_terms.append(f'"{domain_en}"')

    # Combine with AND operator
    if query_terms:
        ncbi_query = " AND ".join(query_terms)

        # Add date filter for last 10 years (per FR-030)
        from datetime import datetime
        current_year = datetime.now().year
        date_filter = f"{current_year - 10}:3000[dpcr]"
        ncbi_query = f"{ncbi_query} AND {date_filter}"

        logger.info(
            f"NCBI query built: {ncbi_query}",
            extra={"session_id": session_id}
        )

        return {"ncbi_query": ncbi_query}

    return {"ncbi_query": ""}


def _map_body_part_to_english(body_part: str) -> str:
    """Map Chinese body part to English medical term.

    Args:
        body_part: Chinese body part name

    Returns:
        English medical term
    """
    mapping = {
        "头部": "head",
        "胸部": "chest",
        "腹部": "abdomen",
        "手臂": "arm",
        "腿部": "leg",
        "背部": "back",
        "颈部": "neck",
        "面部": "face",
        "眼睛": "eye",
        "耳朵": "ear",
        "鼻子": "nose",
        "喉咙": "throat",
        "皮肤": "skin",
        "全身": "systemic",
    }
    return mapping.get(body_part, body_part)


def _map_symptom_to_english(symptom: str) -> str:
    """Map Chinese symptom to English medical term.

    Args:
        symptom: Chinese symptom description

    Returns:
        English medical term
    """
    mapping = {
        "疼痛": "pain",
        "红疹": "rash",
        "肿胀": "swelling",
        "发烧": "fever",
        "咳嗽": "cough",
        "呼吸困难": "dyspnea",
        "头痛": "headache",
        "头晕": "dizziness",
        "恶心": "nausea",
        "呕吐": "vomiting",
        "腹泻": "diarrhea",
        "便秘": "constipation",
        "瘙痒": "itching",
        "出血": "bleeding",
        "麻木": "numbness",
        "无力": "weakness",
    }
    return mapping.get(symptom, symptom)


def _map_domain_to_english(domain: str) -> str:
    """Map Chinese medical domain to English term.

    Args:
        domain: Chinese medical specialty

    Returns:
        English specialty name
    """
    mapping = {
        "内科": "internal medicine",
        "外科": "surgery",
        "儿科": "pediatrics",
        "妇科": "gynecology",
        "皮肤科": "dermatology",
        "骨科": "orthopedics",
        "眼科": "ophthalmology",
        "耳鼻喉科": "otorhinolaryngology",
        "神经内科": "neurology",
        "心血管内科": "cardiology",
        "消化内科": "gastroenterology",
        "呼吸内科": "pulmonology",
        "急诊科": "emergency medicine",
    }
    return mapping.get(domain, domain)
