from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from openai import OpenAI
from json_repair import repair_json

from .config import get_settings
from .model_profiles import get_active_profile, is_profile_usable


def is_llm_configured() -> bool:
    return is_profile_usable()


def require_llm_configured() -> None:
    if not is_llm_configured():
        raise RuntimeError("未配置可用模型。请在顶部“项目设置 → 模型”中填写 Base URL 与模型名；API Key 可按你的中转站要求填写或留空。")


def _client() -> OpenAI:
    profile = get_active_profile()
    api_key = profile.api_key or "ollama"
    return OpenAI(api_key=api_key, base_url=profile.base_url.rstrip("/"), timeout=profile.timeout_seconds)


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        raw = match.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return json.loads(repair_json(raw))


def _chat_text_claude_cli(system: str, user: str) -> str:
    profile = get_active_profile()
    cmd = [
        "claude",
        "-p",
        "--model",
        profile.model,
        "--output-format",
        "text",
        "--system-prompt",
        system,
        "--tools",
        "",
    ]
    proc = subprocess.run(
        cmd,
        input=user,
        text=True,
        capture_output=True,
        timeout=profile.timeout_seconds,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "Claude CLI 调用失败").strip()
        raise RuntimeError(err[:2000])
    return (proc.stdout or "").strip()


def chat_text(system: str, user: str) -> str:
    profile = get_active_profile()
    if profile.provider == "claude_cli":
        return _chat_text_claude_cli(system, user)
    resp = _client().chat.completions.create(
        model=profile.model,
        temperature=profile.temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def chat_json(system: str, user: str) -> dict[str, Any]:
    profile = get_active_profile()
    if profile.provider == "claude_cli":
        return extract_json(_chat_text_claude_cli(system + "\n必须只输出合法 JSON，不要 Markdown。", user))
    client = _client()
    try:
        resp = client.chat.completions.create(
            model=profile.model,
            temperature=profile.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except Exception:
        # Some OpenAI-compatible providers do not implement response_format.
        resp = client.chat.completions.create(
            model=profile.model,
            temperature=profile.temperature,
            messages=[
                {"role": "system", "content": system + "\n必须只输出合法 JSON，不要 Markdown。"},
                {"role": "user", "content": user},
            ],
        )
    return extract_json(resp.choices[0].message.content or "{}")
