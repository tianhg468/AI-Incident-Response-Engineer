# Verification Prompt Template

**Version:** v1.0

## Task

Verify the following hypothesis by running targeted checks.

## Hypothesis to Verify

**Description:** {hypothesis_description}

**Falsification Criterion:** {falsification_criterion}

**Proposed Checks:** {verification_checks}

## Available Evidence

{current_evidence}

## Instructions

Run the verification checks and determine the status:
- **confirmed**: The hypothesis is strongly supported by evidence
- **refuted**: The hypothesis is contradicted by evidence (falsification criterion met)
- **inconclusive**: Unable to confirm or refute with available evidence

For each check:
1. Execute the check using available tools
2. Document the result
3. Assess against the falsification criterion

Provide your response as JSON:
```json
{
  "status": "confirmed | refuted | inconclusive",
  "evidence": [
    {"check": "...", "result": "...", "interpretation": "..."},
    ...
  ],
  "reasoning": "Detailed explanation of why this hypothesis is confirmed/refuted/inconclusive"
}
```
