# TriNav Constitution

## Core Principles

### I. Safety First
MUST: Rule-based red-flag detection overrides any LLM triage output; outputs must never include diagnosis, prescriptions, or delay-care language.
SHOULD: Default to the more conservative triage level when uncertain.

### II. Clear Boundaries
MUST: Outputs are informational only; possible causes must be qualified as suspected/possible; include a standard disclaimer in every response.

### III. Prompt Medical Attention
MUST: EMERGENCY cases bypass evidence retrieval; responses must encourage appropriate medical care and include the hotline tip.

### IV. Data Minimization
MUST: Store only structured, non-sensitive session data; no raw text/images or precise GPS; session TTL is 60 minutes.

### V. Fallback Protection and Traceability
MUST: External service failures degrade gracefully (no 500s); explain triage/ranking rationale; log decision points with correlation IDs; red-flag rules are versioned and audit logs retained 30 days.

## Security and Compliance
MUST: TLS 1.3+ only; HSTS enabled; HTTP redirected to HTTPS; external API versions pinned with manual review and testing before updates; medical advisor review required for red-flag rules.

## Quality Gates
MUST: Contract and integration tests for all user stories and edge cases; performance tests meet SLA targets; coverage >=80% for merge.

## Governance
Constitution supersedes plan/spec/tasks; amendments require explicit update, approval, and re-validation.

**Version**: 1.0.0 | **Ratified**: 2025-01-09 | **Last Amended**: 2025-01-09
