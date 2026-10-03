"""Generic OpenAI-compatible chat completions client. No provider hardcoding."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from resume_engine.config import AIConfig

T = TypeVar("T", bound=BaseModel)

# Exponential backoff waits for HTTP 429 when only one key is configured.
RATE_LIMIT_BACKOFF_SECONDS = (2.0, 5.0, 10.0)
KEY_SWITCH_PAUSE_SECONDS = 0.5


class AIClientError(Exception):
    pass


class AIClient:
    def __init__(
        self,
        ai: AIConfig,
        *,
        on_key_switch: Callable[[str], None] | None = None,
    ) -> None:
        if not ai.api_keys:
            raise ValueError("AIConfig.api_keys must not be empty")
        self.ai = ai
        self.last_tokens: int | None = None
        self.active_key_index = 0
        self.last_key_label = self._key_label(0)
        self.on_key_switch = on_key_switch

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        timeout: float = 90.0,
    ) -> T:
        content = self._chat(system=system, user=user, timeout=timeout)
        parsed = _parse_json_object(content)
        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise AIClientError(f"AI JSON failed schema validation: {exc}") from exc

    def complete_text(
        self,
        *,
        system: str,
        user: str,
        timeout: float = 90.0,
    ) -> str:
        content = self._chat(system=system, user=user, timeout=timeout)
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:\w+)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _key_label(self, index: int) -> str:
        return f"{index + 1}/{len(self.ai.api_keys)}"

    def _notify_switch(self, message: str) -> None:
        if self.on_key_switch is not None:
            self.on_key_switch(message)

    def _chat(self, *, system: str, user: str, timeout: float) -> str:
        keys = self.ai.api_keys
        n_keys = len(keys)
        if n_keys == 1:
            return self._chat_single_key(
                key=keys[0], system=system, user=user, timeout=timeout
            )

        last_http_error: Exception | None = None
        start = self.active_key_index % n_keys
        for offset in range(n_keys):
            index = (start + offset) % n_keys
            key = keys[index]
            label = self._key_label(index)
            try:
                data = self._post_once(
                    key=key, system=system, user=user, timeout=timeout
                )
                self.active_key_index = index
                self.last_key_label = label
                self.last_tokens = _extract_tokens(data)
                return _extract_content(data)
            except _FailoverError as exc:
                last_http_error = exc.cause
                if offset < n_keys - 1:
                    next_label = self._key_label((index + 1) % n_keys)
                    self._notify_switch(
                        f"AI key {label} {exc.reason}; switching to key {next_label}"
                    )
                    time.sleep(KEY_SWITCH_PAUSE_SECONDS)
                continue

        raise AIClientError(
            f"AI HTTP error after trying {n_keys} keys: {last_http_error}"
        ) from last_http_error

    def _chat_single_key(
        self, *, key: str, system: str, user: str, timeout: float
    ) -> str:
        self.last_key_label = self._key_label(0)
        last_http_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                data = self._post_once(
                    key=key,
                    system=system,
                    user=user,
                    timeout=timeout,
                    allow_429_retry=True,
                    attempt=attempt,
                )
                self.active_key_index = 0
                self.last_tokens = _extract_tokens(data)
                return _extract_content(data)
            except _FailoverError as exc:
                last_http_error = exc.cause
                if attempt < 3 and exc.reason in {
                    "rate-limited",
                    "request failed",
                    "server error",
                }:
                    if exc.reason != "rate-limited":
                        time.sleep(2.0 * attempt)
                    continue
                break
        raise AIClientError(f"AI HTTP error: {last_http_error}") from last_http_error

    def _post_once(
        self,
        *,
        key: str,
        system: str,
        user: str,
        timeout: float,
        allow_429_retry: bool = False,
        attempt: int = 1,
    ) -> dict[str, Any]:
        url = f"{self.ai.api_base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.ai.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code == 429:
                    if allow_429_retry:
                        wait_s = RATE_LIMIT_BACKOFF_SECONDS[
                            min(attempt - 1, len(RATE_LIMIT_BACKOFF_SECONDS) - 1)
                        ]
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait_s = float(retry_after)
                            except ValueError:
                                pass
                        time.sleep(wait_s)
                    raise _FailoverError(
                        "rate-limited",
                        httpx.HTTPStatusError(
                            "429 Too Many Requests",
                            request=response.request,
                            response=response,
                        ),
                    )
                if response.status_code in {401, 403}:
                    raise _FailoverError(
                        "unauthorized",
                        httpx.HTTPStatusError(
                            f"{response.status_code} Unauthorized",
                            request=response.request,
                            response=response,
                        ),
                    )
                if response.status_code >= 500:
                    raise _FailoverError(
                        "server error",
                        httpx.HTTPStatusError(
                            f"{response.status_code} Server Error",
                            request=response.request,
                            response=response,
                        ),
                    )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise AIClientError("Unexpected AI response shape")
                return data
        except _FailoverError:
            raise
        except AIClientError:
            raise
        except httpx.HTTPError as exc:
            raise _FailoverError("request failed", exc) from exc


class _FailoverError(Exception):
    def __init__(self, reason: str, cause: Exception) -> None:
        self.reason = reason
        self.cause = cause
        super().__init__(reason)


def _extract_content(data: dict[str, Any]) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIClientError("Unexpected AI response shape") from exc

    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _extract_tokens(data: dict[str, Any]) -> int | None:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None
    total = usage.get("total_tokens")
    if isinstance(total, int):
        return total
    prompt = usage.get("prompt_tokens") or 0
    completion = usage.get("completion_tokens") or 0
    if isinstance(prompt, int) and isinstance(completion, int) and (prompt or completion):
        return prompt + completion
    return None


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise AIClientError("AI response was not valid JSON") from None
        obj = json.loads(match.group(0))
    if not isinstance(obj, dict):
        raise AIClientError("AI JSON root must be an object")
    return obj
