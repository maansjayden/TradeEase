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

MODEL_NAME = "gemini-3.1-flash-lite"


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
        prompt = f"""You are a trade compliance assistant helping a first-time SME exporter
classify a product under the Harmonized System (HS) using WCO General Rules
of Interpretation (GRI).

Product description: {product_description}
Destination country: {destination_country or "Not specified"}

Respond with ONLY valid JSON (no markdown fences, no extra commentary) in
exactly this shape:
{{
  "hs_code": "the HS code, at least 6 digits",
  "code_description": "official-style description of this HS code",
  "confidence": "High, Medium, or Low",
  "reasoning": "2-3 plain-English sentences on why this code fits, referencing the product's material or function",
  "caution": "one sentence flagging what the exporter should double-check with a licensed customs broker"
}}"""
        raw = self._call_with_retry(prompt)
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

    def _call_with_retry(self, prompt: str, max_retries: int = 4) -> str:
        """Calls Gemini, retrying with exponential backoff on free-tier 429s."""
        wait_seconds = 2
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt,
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
