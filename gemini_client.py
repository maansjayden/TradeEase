"""
gemini_client.py — TradeEase AI layer

Uses Google's current `google-genai` SDK (the old `google-generativeai`
package is deprecated). Free tier as of 2026: Gemini 2.5 Flash gives the
best balance of quality + rate limit headroom (roughly 10-15 requests/min,
varies by region). If you hit 429 errors often during demo/testing, switch
MODEL_NAME to "gemini-2.5-flash-lite" — lower quality, higher rate limit.

Classification and invoice calls always return structured JSON with a
human-in-the-loop caution field; this is intentional — compliance is a
domain where hallucinated answers cause real financial/legal harm, so the
UI never presents AI output as final, only as a draft to verify. The
mentor chat (ask_mentor) returns plain text instead, since forcing JSON
onto free-form conversation adds parsing risk for no real benefit.
"""

import os
import json
import time
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

MODEL_NAME = "gemini-3.1-flash-lite"


class TradeComplianceResponse(BaseModel):
    hs_code: str = Field(description="The 6-digit HS code for the product, e.g. '6109.10'")
    description: str = Field(description="The official WCO description of this HS heading/subheading, as it appears in the tariff schedule")
    confidence_level: str = Field(description="Your confidence in this classification, expressed as a number out of 100, e.g. '92/100'")
    reasoning: str = Field(description="2-4 sentences explaining why this HS code applies, referencing the product's material, function, or GRI rules used")
    questions: list[str] = Field(description="List of clarifying questions needed to confirm the classification. Empty list if confidence is 80% or above and no ambiguity exists.")
    gri_rule: str = Field(description="The specific WCO General Rule of Interpretation (GRI) applied, e.g. 'GRI 1 — classification by heading text' or 'GRI 3(b) — essential character'")
    sources: list[str] = Field(description="List of authoritative sources consulted, e.g. 'WCO HS Nomenclature 2022, Chapter 61 Notes', 'US HTS Schedule B'")
    links_to_sources: list[str] = Field(description="Direct URLs to the sources listed above. Use empty string if no URL is available for a source.")


_CLASSIFY_CONFIG = types.GenerateContentConfig(
    system_instruction=(
        "You are a trade compliance expert specialising in Harmonized System (HS) classification. "
        "Rules: "
        "1. Never guess — only classify when you have enough information. "
        "2. Always populate every field in the response schema fully. "
        "3. State confidence_level critically as a number out of 100, e.g. '88/100'. "
        "4. Always name the GRI rule you applied in gri_rule. "
        "5. Always cite at least one authoritative source (WCO, national tariff schedule, etc.) in sources. "
        "6. Explain your reasoning clearly referencing the product's material, function, or use. "
        "7. If confidence is below 80%, include clarifying questions in the questions list. "
        "8. Only ask questions necessary to determine the 6-digit HS code — nothing unrelated. "
        "9. Request country of origin/destination only if it materially affects classification. "
        "10. Do not classify heavily regulated or prohibited substances."
    ),
    temperature=0.1,
    response_mime_type="application/json",
    response_schema=TradeComplianceResponse,
)


class GeminiClient:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "No GEMINI_API_KEY found. Set it in your .env file or environment "
                "variables — see .env.example."
            )
        self.client = genai.Client(api_key=key)

    # ---------- public API ----------

    def classify_hs_code(self, product_description: str, destination_country: str = "") -> dict:
        prompt = f"Classify this product: {product_description}"
        if destination_country:
            prompt += f"\nDestination country: {destination_country}"
        raw = self._call_with_retry(prompt, config=_CLASSIFY_CONFIG)
        return self._parse_json(raw)

    def generate_invoice(self, invoice_data: dict) -> dict:
        prompt = f"""You are a trade compliance assistant. Draft a commercial invoice for
cross-border export based on the structured data below. Use a standard
professional format suitable for customs purposes.

Data:
{json.dumps(invoice_data, indent=2)}

Respond with ONLY valid JSON (no markdown fences, no extra commentary) in
exactly this shape:
{{
  "invoice_number": "a reference number, format INV-YYYYMMDD-XXX",
  "formatted_invoice": "the full invoice as plain text, ready to print: header, exporter/importer details, goods table, incoterm, totals, and a declaration statement",
  "compliance_note": "one sentence noting a compliance detail the exporter should verify"
}}"""
        raw = self._call_with_retry(prompt)
        return self._parse_json(raw)

    def ask_mentor(self, message: str, history: list | None = None) -> dict:
        """Free-form trade-compliance Q&A. Plain text, not JSON — this is a
        chat, so forcing structured output would just add parsing risk for
        no benefit. Returns {"reply": "..."} to match the other methods'
        dict shape, which keeps GeminiWorker generic."""
        history = history or []
        convo_lines = []
        for turn in history[-6:]:
            speaker = "Exporter" if turn["role"] == "user" else "Mentor"
            convo_lines.append(f"{speaker}: {turn['text']}")
        convo = "\n".join(convo_lines)

        prompt = f"""You are Tia, a friendly trade-compliance mentor for first-time SME
exporters in emerging markets. Answer in plain English,
practical and encouraging. If the question involves a binding legal, tax,
or customs determination, end with one short sentence recommending they
confirm with a licensed customs broker — otherwise skip that line.

Conversation so far:
{convo}
Exporter: {message}
Mentor:"""
        raw = self._call_with_retry(prompt)
        reply = raw.strip() if raw else "Sorry, I didn't catch that — could you rephrase?"
        return {"reply": reply}

    def _call_with_retry(self, prompt: str, max_retries: int = 4, config=None) -> str:
        """Calls Gemini, retrying with exponential backoff on free-tier 429s."""
        wait_seconds = 2
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt,
                    config=config,
                )
                return response.text
            except Exception as e:
                last_error = e
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    if attempt < max_retries - 1:
                        time.sleep(wait_seconds)
                        wait_seconds *= 2
                        continue
                    raise RuntimeError(
                        "Gemini free-tier rate limit reached. Wait ~60 seconds and try again."
                    ) from e
                raise
        raise RuntimeError(str(last_error))

    def _parse_json(self, raw_text: str) -> dict:
        if not raw_text:
            return {"error": "Empty response from AI model."}
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            return {"error": "Could not parse AI response as JSON.", "raw": raw_text}
