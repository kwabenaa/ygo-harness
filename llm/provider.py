"""One OpenAI-compatible client for every backend we care about.

OpenRouter, Ollama, LM Studio and llama-server all speak the OpenAI chat
completions API, so the only things that differ are `base_url`, the model
string, and whether an API key is needed. There is no provider abstraction
here beyond that, deliberately.

A note on reproducibility: OpenRouter's `:floor` suffix routes to whichever
provider is cheapest right now, and `openrouter/free` rotates across models.
Both are excellent while developing and poison for benchmark numbers, because
the serving backend changes between runs. Use them freely for smoke tests;
pin an exact provider and model for anything written to bench/results/.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


@dataclass
class Usage:
    """Running token/cost tally. Cost per duel is a reported metric, so this
    is part of the harness rather than an afterthought."""
    calls: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    #: Tokens written to cache. Billed at a premium (1.25x on Anthropic), so a
    #: run that writes the cache repeatedly without reading it is *more*
    #: expensive than not caching - worth being able to see.
    cache_write_tokens: int = 0
    completion_tokens: int = 0

    def add(self, resp) -> None:
        self.calls += 1
        u = getattr(resp, "usage", None)
        if not u:
            return
        self.prompt_tokens += getattr(u, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(u, "completion_tokens", 0) or 0
        details = getattr(u, "prompt_tokens_details", None)
        if details is not None:
            self.cached_tokens += getattr(details, "cached_tokens", 0) or 0
            self.cache_write_tokens += getattr(details, "cache_write_tokens", 0) or 0

    def cost(self, in_per_m: float, out_per_m: float,
             cached_per_m: float | None = None,
             write_multiplier: float = 1.25) -> float:
        """Cost at the given rates, counting cache reads and writes separately.

        Writes are billed above the normal input rate, so charging them as
        ordinary input understates a run that keeps missing the cache.
        """
        cached_rate = in_per_m if cached_per_m is None else cached_per_m
        fresh = max(self.prompt_tokens - self.cached_tokens
                    - self.cache_write_tokens, 0)
        return (
            fresh / 1e6 * in_per_m
            + self.cache_write_tokens / 1e6 * in_per_m * write_multiplier
            + self.cached_tokens / 1e6 * cached_rate
            + self.completion_tokens / 1e6 * out_per_m
        )

    def __str__(self) -> str:
        return (f"{self.calls} calls, {self.prompt_tokens} in "
                f"({self.cached_tokens} cached), {self.completion_tokens} out")


#: Named presets. base_url and env var only - no pricing baked in, since that
#: drifts and a stale number in code is worse than no number.
PRESETS = {
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama":     ("http://localhost:11434/v1", None),
    "lmstudio":   ("http://localhost:1234/v1", None),
    "llamacpp":   ("http://localhost:8080/v1", None),
}


@dataclass
class Provider:
    model: str
    preset: str = "openrouter"
    base_url: str | None = None
    api_key: str | None = None
    temperature: float = 0.0
    max_tokens: int = 2048
    #: Non-OpenAI parameters (OpenRouter's `reasoning`, provider routing, ...).
    #: These must go through the SDK's extra_body, not as keyword arguments -
    #: the client rejects unknown kwargs outright.
    extra_body: dict = field(default_factory=dict)
    #: Send the system prompt as a content block carrying a cache breakpoint.
    #:
    #: Anthropic models cache only where a breakpoint is marked - without one
    #: nothing is written to cache at all, which is what we were doing.
    #: Measured on a 9,926-token system prompt through OpenRouter: first call
    #: writes and costs $0.0124, second reads and costs $0.0010. Twelve times
    #: cheaper, and it applies to every call after the first.
    #:
    #: Below roughly 2,048 tokens Anthropic will not cache at all, so small
    #: puzzles get nothing from this - and lose nothing either. Verified
    #: harmless on qwen, which ignores the annotation.
    cache_system: bool = True
    usage: Usage = field(default_factory=Usage)

    def __post_init__(self):
        if OpenAI is None:
            raise ImportError("pip install openai")
        url, env = PRESETS.get(self.preset, (None, None))
        base = self.base_url or url
        if base is None:
            raise ValueError(f"unknown preset {self.preset!r}; pass base_url")
        key = self.api_key or (os.environ.get(env) if env else None) or "not-needed"
        self.client = OpenAI(base_url=base, api_key=key)

    def complete(self, system: str, user: str, *,
                 reasoning: dict | None = None) -> str:
        """One completion. System prompt first so the stable prefix is
        cache-eligible on backends that cache automatically.

        `reasoning` overrides the configured budget for this call only. That
        exists for one specific recovery: a reasoning model given no budget
        can spend the entire `max_tokens` thinking and return empty content,
        and the only fix that does not just move the threshold is to ask again
        with a budget it must conclude within.
        """
        body = dict(self.extra_body or {})
        if reasoning is not None:
            body["reasoning"] = reasoning
        sys_content = (
            [{"type": "text", "text": system,
              "cache_control": {"type": "ephemeral"}}]
            if self.cache_system else system
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": sys_content},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_body=body or None,
        )
        self.usage.add(resp)
        #: "length" means the model was cut off mid-thought rather than
        #: choosing to stop, which is what an empty reply usually means here.
        self.last_finish_reason = getattr(resp.choices[0], "finish_reason", None)
        choice = resp.choices[0].message
        # OpenRouter returns a reasoning model's thinking alongside the
        # content. Keep the most recent one so a transcript can show *why*
        # a decision was made, not just which index came back.
        self.last_reasoning = (getattr(choice, "reasoning", None) or "")
        return (choice.content or "").strip()


def from_config(role: str, path: str | None = None, **overrides) -> "Provider":
    """Build a Provider for a named role in llm/models.yaml.

    Roles exist because deliberation should be paid for only where it changes
    the answer - see the measurements in that file.
    """
    import pathlib

    import yaml

    path = path or (pathlib.Path(__file__).parent / "models.yaml")
    cfg = yaml.safe_load(open(path))
    if role not in cfg:
        raise KeyError(f"role {role!r} not in {path}; have {sorted(cfg)}")
    spec = dict(cfg[role])
    reasoning = spec.pop("reasoning", None)
    extra = {"reasoning": reasoning} if reasoning else {}
    spec.update(overrides)
    return Provider(extra_body=extra, **spec)
