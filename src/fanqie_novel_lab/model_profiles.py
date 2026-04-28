from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI
from pydantic import BaseModel, Field

from .config import CONFIG_DIR, get_settings

PROFILES_PATH = CONFIG_DIR / "model_profiles.json"


class ModelProfile(BaseModel):
    name: str
    # openai = OpenAI-compatible HTTP API; claude_cli = local Claude Code CLI bridge.
    provider: str = "openai"
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.75
    timeout_seconds: int = 120
    note: str = ""

    @property
    def masked_key(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "****"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"


class ModelProfileStore(BaseModel):
    active: str = "default"
    profiles: dict[str, ModelProfile] = Field(default_factory=dict)


PRESET_BASE_URLS: dict[str, str] = {
    "自定义 / 任意中转": "",
    "DeepSeek": "https://api.deepseek.com/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
    "One API / New API 本地": "http://127.0.0.1:3000/v1",
    "LiteLLM Proxy 本地": "http://127.0.0.1:4000/v1",
    "Ollama 本地": "http://localhost:11434/v1",
    "LM Studio 本地": "http://localhost:1234/v1",
    "OpenAI": "https://api.openai.com/v1",
    "硅基流动 SiliconFlow": "https://api.siliconflow.cn/v1",
    "火山方舟 Ark": "https://ark.cn-beijing.volces.com/api/v3",
}


def _profile_from_env() -> ModelProfile:
    settings = get_settings()
    return ModelProfile(
        name="default",
        provider="openai",
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "",
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
        note="从 .env 初始化",
    )


def load_store() -> ModelProfileStore:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not PROFILES_PATH.exists():
        profile = _profile_from_env()
        store = ModelProfileStore(active=profile.name, profiles={profile.name: profile})
        save_store(store)
        return store
    try:
        data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        store = ModelProfileStore(**data)
    except Exception:
        profile = _profile_from_env()
        store = ModelProfileStore(active=profile.name, profiles={profile.name: profile})
        save_store(store)
    if not store.profiles:
        profile = _profile_from_env()
        store.profiles[profile.name] = profile
        store.active = profile.name
        save_store(store)
    if store.active not in store.profiles:
        store.active = next(iter(store.profiles.keys()))
        save_store(store)
    return store


def save_store(store: ModelProfileStore) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(store.model_dump_json(indent=2), encoding="utf-8")


def list_profiles() -> list[ModelProfile]:
    store = load_store()
    return list(store.profiles.values())


def get_active_profile() -> ModelProfile:
    store = load_store()
    return store.profiles[store.active]


def upsert_profile(profile: ModelProfile, make_active: bool = True) -> None:
    store = load_store()
    store.profiles[profile.name] = profile
    if make_active:
        store.active = profile.name
    save_store(store)


def set_active_profile(name: str) -> ModelProfile:
    store = load_store()
    if name not in store.profiles:
        raise KeyError(f"模型配置不存在：{name}")
    store.active = name
    save_store(store)
    return store.profiles[name]


def delete_profile(name: str) -> None:
    store = load_store()
    if len(store.profiles) <= 1:
        raise ValueError("至少保留一个模型配置")
    store.profiles.pop(name, None)
    if store.active == name:
        store.active = next(iter(store.profiles.keys()))
    save_store(store)


def _is_local_base_url(base_url: str) -> bool:
    b = base_url.lower()
    return "localhost" in b or "127.0.0.1" in b or "0.0.0.0" in b


def is_profile_usable(profile: ModelProfile | None = None) -> bool:
    p = profile or get_active_profile()
    if p.provider == "claude_cli":
        return bool(p.model.strip())
    if not p.base_url.strip() or not p.model.strip():
        return False
    # 不强制 API Key：有些本地网关、内网中转、无鉴权反向代理只需要
    # OpenAI-compatible Base URL + 模型名。真正鉴权失败交给调用时返回。
    return True


def fetch_models(base_url: str, api_key: str = "", timeout_seconds: int = 30) -> list[str]:
    """Fetch models from an OpenAI-compatible /models endpoint.

    支持 DeepSeek、OpenRouter、Ollama、LM Studio、vLLM、硅基流动等兼容接口。
    """
    api_key = api_key or ("ollama" if _is_local_base_url(base_url) else "")
    try:
        client = OpenAI(api_key=api_key or "EMPTY", base_url=base_url.rstrip("/"), timeout=timeout_seconds)
        models = client.models.list()
        ids = sorted({m.id for m in models.data if getattr(m, "id", None)})
        if ids:
            return ids
    except Exception:
        pass

    # Fallback direct GET for providers with slightly different clients.
    root = base_url.rstrip("/")
    urls = [root + "/models"]
    if not root.endswith("/v1"):
        urls.append(root + "/v1/models")
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    last_error: Exception | None = None
    data: Any = None
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout_seconds)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:
            last_error = exc
    if data is None:
        raise last_error or RuntimeError("模型列表为空")
    raw = data.get("data", data if isinstance(data, list) else [])
    ids: list[str] = []
    for item in raw:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
        elif hasattr(item, "id"):
            ids.append(str(item.id))
    return sorted(set(ids))
