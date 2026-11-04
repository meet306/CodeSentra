"""
Groq API integration client (Free Tier).
Provides resilient inference with structured JSON outputs and rate-limit backoff.
"""

import asyncio
import json
from typing import Any

from groq import APIConnectionError, APIStatusError, AsyncGroq, RateLimitError

from app.config import Settings, get_settings
from app.core.errors import GroqAPIError, RateLimitExceededError
from app.core.logging import logger
from app.schemas.review import Finding, Severity


class GroqClient:
    """Async Groq API client configured for free-tier resilience."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: AsyncGroq | None = None

    @property
    def client(self) -> AsyncGroq:
        """Lazy initialization of AsyncGroq client."""
        if not self.settings.GROQ_API_KEY:
            raise GroqAPIError(
                "GROQ_API_KEY is not set. Please obtain a free API key at https://console.groq.com/keys and configure it in .env"
            )
        if self._client is None:
            self._client = AsyncGroq(
                api_key=self.settings.GROQ_API_KEY,
                timeout=self.settings.GROQ_TIMEOUT_SECONDS,
            )
        return self._client

    async def generate_completion_with_retry(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Calls Groq API with exponential backoff retries for rate limits."""
        target_model = model or self.settings.GROQ_MODEL
        retries = 0
        backoff_seconds = 2.0

        while retries <= self.settings.GROQ_MAX_RETRIES:
            try:
                logger.info(f"Calling Groq API (model: {target_model}, attempt {retries + 1}/{self.settings.GROQ_MAX_RETRIES + 1})")
                response = await self.client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format or {"type": "json_object"},
                )

                content_str = response.choices[0].message.content or "{}"
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }

                try:
                    parsed_json = json.loads(content_str)
                except json.JSONDecodeError as json_err:
                    logger.warning(f"Groq output was not valid JSON: {json_err}. Raw output: {content_str[:200]}")
                    parsed_json = {"raw_content": content_str}

                return {
                    "data": parsed_json,
                    "usage": usage,
                    "model": response.model,
                }

            except RateLimitError as rl_err:
                retries += 1
                if retries > self.settings.GROQ_MAX_RETRIES:
                    logger.error(f"Groq rate limit exceeded after {retries} retries: {rl_err}")
                    raise RateLimitExceededError(
                        f"Groq API rate limit exceeded. Please wait before retrying. Details: {str(rl_err)}"
                    )
                sleep_time = backoff_seconds * (2 ** (retries - 1))
                logger.warning(f"Rate limited by Groq API. Backing off for {sleep_time:.1f}s before retry {retries}...")
                await asyncio.sleep(sleep_time)

            except (APIConnectionError, APIStatusError) as api_err:
                retries += 1
                if retries > self.settings.GROQ_MAX_RETRIES:
                    logger.error(f"Groq API error after {retries} retries: {api_err}")
                    raise GroqAPIError(f"Groq API failed: {str(api_err)}")
                sleep_time = backoff_seconds * (2 ** (retries - 1))
                logger.warning(f"Groq API connection/status issue. Retrying in {sleep_time:.1f}s... Error: {api_err}")
                await asyncio.sleep(sleep_time)

        raise GroqAPIError("Max retries exceeded communicating with Groq API.")

    def parse_findings_from_dict(
        self,
        raw_data: dict[str, Any],
        agent_name: str = "ai_reviewer",
        valid_files: list[str] | None = None,
    ) -> list[Finding]:
        """Safely parses and validates a list of Findings from model response."""
        findings_list = raw_data.get("findings", [])
        if not isinstance(findings_list, list):
            logger.warning(f"Expected 'findings' list in Groq response, got: {type(findings_list)}")
            return []

        validated: list[Finding] = []
        valid_files_set = set(valid_files) if valid_files else None

        for item in findings_list:
            if not isinstance(item, dict):
                continue

            file_path = str(item.get("file_path", "")).strip()
            # Prevent hallucinated file names
            if valid_files_set and file_path not in valid_files_set:
                # Check if it matches filename without path
                matched = [vf for vf in valid_files_set if vf.endswith(file_path) or file_path.endswith(vf)]
                if matched:
                    file_path = matched[0]
                else:
                    logger.warning(f"Discarding finding with non-existent file path '{file_path}'")
                    continue

            # Validate severity enum
            raw_severity = str(item.get("severity", "INFO")).upper().strip()
            severity = Severity.INFO
            if raw_severity in Severity.__members__:
                severity = Severity[raw_severity]

            # Line number validation
            line_no = item.get("line_number")
            if line_no is not None:
                try:
                    line_no = int(line_no)
                    if line_no <= 0:
                        line_no = None
                except (ValueError, TypeError):
                    line_no = None

            # Confidence score validation
            confidence_val = item.get("confidence", 0.8)
            try:
                confidence_float = float(confidence_val)
                confidence_float = max(0.0, min(1.0, confidence_float))
            except (ValueError, TypeError):
                confidence_float = 0.8

            try:
                finding = Finding(
                    agent_name=agent_name,
                    title=str(item.get("title", "Review Notice")).strip()[:150],
                    description=str(item.get("description", "")).strip(),
                    severity=severity,
                    confidence=confidence_float,
                    file_path=file_path,
                    line_number=line_no,
                    code_snippet=str(item.get("code_snippet")) if item.get("code_snippet") else None,
                    suggested_fix=str(item.get("suggested_fix")) if item.get("suggested_fix") else None,
                    reasoning=str(item.get("reasoning", "Identified based on diff examination")).strip(),
                )
                validated.append(finding)
            except Exception as e:
                logger.warning(f"Failed to instantiate Finding from payload: {e}")
                continue

        return validated
