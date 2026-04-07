"""Canonical per-turn medical state models for v3 runtime."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ConsultationState(BaseModel):
    """Consultation extraction outputs for the current turn."""

    model_config = ConfigDict(extra="forbid")

    symptom_schema: dict[str, JsonValue] = Field(default_factory=dict)
    summary: str | None = None


class TriageState(BaseModel):
    """Triage outputs for the current turn."""

    model_config = ConfigDict(extra="forbid")

    triage_level: Literal["EMERGENCY", "URGENT", "ROUTINE", "SELF_CARE"] | None = None
    triage_reason: str | None = None
    recommended_departments: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    self_care_tips: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class EvidenceState(BaseModel):
    """Evidence retrieval outputs for the current turn."""

    model_config = ConfigDict(extra="forbid")

    ncbi_query: str | None = None
    evidence_selected: list[dict[str, JsonValue]] = Field(default_factory=list)


class NavigationState(BaseModel):
    """Navigation outputs for the current turn."""

    model_config = ConfigDict(extra="forbid")

    navigation_result: dict[str, JsonValue] | None = None
    weather_alert: dict[str, JsonValue] | None = None


class ResponseState(BaseModel):
    """Response synthesis outputs for the current turn."""

    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    response: str | None = None


class MedicalTurnState(BaseModel):
    """Canonical aggregate turn state shared across capabilities."""

    model_config = ConfigDict(extra="forbid")

    consultation: ConsultationState = Field(default_factory=ConsultationState)
    triage: TriageState = Field(default_factory=TriageState)
    evidence: EvidenceState = Field(default_factory=EvidenceState)
    navigation: NavigationState = Field(default_factory=NavigationState)
    response: ResponseState = Field(default_factory=ResponseState)
