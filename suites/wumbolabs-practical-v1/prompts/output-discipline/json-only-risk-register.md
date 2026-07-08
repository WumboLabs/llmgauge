Return only valid JSON. Do not use Markdown. Do not include commentary before or after the JSON.

Task:
Create a concise risk register for publishing a local model evaluation report based only on a Tier 1 smoke suite.

This is about local LLM model-report evidence, not generic software release testing.

JSON schema:
{
  "risk_register": [
    {
      "risk": "string",
      "severity": "low|medium|high",
      "why_it_matters": "string",
      "mitigation": "string"
    }
  ],
  "publish_decision": "publish|hold|publish_with_caveats",
  "claim_limit": "string"
}

Requirements:
- Include exactly five risks.
- Use only the allowed severity values.
- Risks must be specific to model evaluation/reporting from Tier 1 smoke evidence.
- The final decision must reflect that Tier 1 smoke evidence is not enough for a recommendation.
- `claim_limit` must say that Tier 1 supports smoke-screen claims only, not recommendations or rankings.
- Keep each string under 140 characters.
