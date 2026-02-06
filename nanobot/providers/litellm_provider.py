"""LiteLLM provider implementation for multi-provider support."""

import os
from typing import Any

import httpx

import litellm
from litellm import acompletion

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenRouter, Anthropic, OpenAI, Gemini, and many other providers through
    a unified interface.
    """
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        api_version: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5"
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.api_version = api_version
        
        # Detect OpenRouter by api_key prefix or explicit api_base
        self.is_openrouter = (
            (api_key and api_key.startswith("sk-or-")) or
            (api_base and "openrouter" in api_base)
        )

        # Detect Azure OpenAI
        self.is_azure = (
            default_model.startswith("azure/") or
            (api_base and "openai.azure.com" in api_base)
        )
        
        # Track if using custom endpoint (vLLM, etc.)
        self.is_vllm = bool(api_base) and not self.is_openrouter and not self.is_azure
        
        # Configure LiteLLM based on provider
        if api_key:
            if self.is_openrouter:
                # OpenRouter mode - set key
                os.environ["OPENROUTER_API_KEY"] = api_key
            elif self.is_azure:
                # Azure OpenAI
                os.environ.setdefault("AZURE_OPENAI_API_KEY", api_key)
                os.environ.setdefault("AZURE_API_KEY", api_key)
            elif self.is_vllm:
                # vLLM/custom endpoint - uses OpenAI-compatible API
                os.environ["OPENAI_API_KEY"] = api_key
            elif "anthropic" in default_model:
                os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
            elif "openai" in default_model or "gpt" in default_model:
                os.environ.setdefault("OPENAI_API_KEY", api_key)
            elif "gemini" in default_model.lower():
                os.environ.setdefault("GEMINI_API_KEY", api_key)
            elif "zhipu" in default_model or "glm" in default_model or "zai" in default_model:
                os.environ.setdefault("ZHIPUAI_API_KEY", api_key)
            elif "groq" in default_model:
                os.environ.setdefault("GROQ_API_KEY", api_key)
        
        if api_base:
            litellm.api_base = api_base
            if self.is_azure:
                os.environ.setdefault("AZURE_API_BASE", api_base)
        if api_version:
            litellm.api_version = api_version
            if self.is_azure:
                os.environ.setdefault("AZURE_API_VERSION", api_version)
        
        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
        
        Returns:
            LLMResponse with content and/or tool calls.
        """
        model = model or self.default_model

        # Direct Azure OpenAI request (matches Azure REST API usage)
        if self.is_azure:
            return await self._chat_azure_direct(
                messages=messages,
                tools=tools,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        
        # For OpenRouter, prefix model name if not already prefixed
        if self.is_openrouter and not model.startswith("openrouter/"):
            model = f"openrouter/{model}"
        
        # For Zhipu/Z.ai, ensure prefix is present
        # Handle cases like "glm-4.7-flash" -> "zai/glm-4.7-flash"
        if ("glm" in model.lower() or "zhipu" in model.lower()) and not (
            model.startswith("zhipu/") or 
            model.startswith("zai/") or 
            model.startswith("openrouter/")
        ):
            model = f"zai/{model}"
        
        # For vLLM, use hosted_vllm/ prefix per LiteLLM docs
        # Convert openai/ prefix to hosted_vllm/ if user specified it
        if self.is_vllm:
            model = f"hosted_vllm/{model}"

        # For Azure OpenAI, model should be prefixed with azure/
        if self.is_azure and not model.startswith("azure/"):
            model = f"azure/{model}"
        
        # For Gemini, ensure gemini/ prefix if not already present
        if "gemini" in model.lower() and not model.startswith("gemini/"):
            model = f"gemini/{model}"
        
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Pass api_base directly for custom endpoints (vLLM, etc.)
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_version:
            kwargs["api_version"] = self.api_version
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            # Return error as content for graceful handling
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    async def _chat_azure_direct(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not self.api_base or not self.api_key:
            return LLMResponse(
                content="Error calling LLM: missing Azure API base or key",
                finish_reason="error",
            )
        if not self.api_version:
            return LLMResponse(
                content="Error calling LLM: missing Azure API version",
                finish_reason="error",
            )

        deployment = model.removeprefix("azure/") if model.startswith("azure/") else model
        endpoint = self.api_base.rstrip("/")
        url = (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={self.api_version}"
        )

        def build_body(use_max_completion: bool, include_temperature: bool = True) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "messages": messages,
            }
            if include_temperature:
                payload["temperature"] = temperature
            if use_max_completion:
                payload["max_completion_tokens"] = max_tokens
            else:
                payload["max_tokens"] = max_tokens
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            return payload

        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Prefer max_completion_tokens for newer Azure models (e.g., gpt-5.1)
                use_max_completion = True
                include_temperature = True
                body = build_body(use_max_completion, include_temperature)
                resp = await client.post(url, json=body, headers=headers)

                if resp.status_code == 400:
                    try:
                        err = resp.json().get("error", {})
                        param = err.get("param")
                        msg = err.get("message", "")
                    except Exception:
                        param = None
                        msg = ""

                    needs_retry = (
                        param in ("max_tokens", "max_completion_tokens")
                        or "max_tokens" in msg
                        or "max_completion_tokens" in msg
                    )
                    temp_unsupported = (
                        param == "temperature"
                        or "temperature" in msg
                    )
                    if needs_retry:
                        use_max_completion = not use_max_completion
                        body = build_body(use_max_completion, include_temperature)
                        resp = await client.post(url, json=body, headers=headers)
                    if resp.status_code == 400 and temp_unsupported:
                        include_temperature = False
                        body = build_body(use_max_completion, include_temperature)
                        resp = await client.post(url, json=body, headers=headers)

            if resp.status_code != 200:
                return LLMResponse(
                    content=(
                        f"Error calling LLM: Azure HTTP {resp.status_code} - {resp.text}"
                    ),
                    finish_reason="error",
                )

            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content") or ""

            tool_calls = []
            for tc in message.get("tool_calls") or []:
                args = tc.get("function", {}).get("arguments")
                if isinstance(args, str):
                    try:
                        import json as _json

                        args = _json.loads(args)
                    except Exception:
                        args = {"raw": args}
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.get("id", ""),
                        name=tc.get("function", {}).get("name", ""),
                        arguments=args or {},
                    )
                )

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason") or "stop",
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
        
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
