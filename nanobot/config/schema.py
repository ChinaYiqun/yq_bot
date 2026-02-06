"""Configuration schema using Pydantic."""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames


class WebConfig(BaseModel):
    """Web UI channel configuration (local web chat)."""
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 18790
    allow_from: list[str] = Field(default_factory=list)  # Allowed client IDs (optional)


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    web: WebConfig = Field(default_factory=WebConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI configuration."""
    enabled: bool = False
    api_key: str = ""
    endpoint: str = ""
    api_version: str = ""
    deployment_name: str = ""


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    azure_openai: AzureOpenAIConfig = Field(default_factory=AzureOpenAIConfig)


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""
    timeout: int = 60
    restrict_to_workspace: bool = False  # If true, block commands accessing paths outside workspace


class ToolsConfig(BaseModel):
    """Tools configuration."""
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)


class Config(BaseSettings):
    """Root configuration for yiqunbot."""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
    
    def get_api_key(self) -> str | None:
        """Get API key in priority order: OpenRouter > Anthropic > OpenAI > Gemini > Zhipu > Groq > vLLM."""
        azure = self.get_azure_openai()
        if azure and azure.enabled and azure.api_key:
            return azure.api_key
        return (
            self.providers.openrouter.api_key or
            self.providers.anthropic.api_key or
            self.providers.openai.api_key or
            self.providers.gemini.api_key or
            self.providers.zhipu.api_key or
            self.providers.groq.api_key or
            self.providers.vllm.api_key or
            None
        )
    
    def get_api_base(self) -> str | None:
        """Get API base URL if using OpenRouter, Zhipu or vLLM."""
        azure = self.get_azure_openai()
        if azure and azure.enabled and azure.endpoint:
            return azure.endpoint
        if self.providers.openrouter.api_key:
            return self.providers.openrouter.api_base or "https://openrouter.ai/api/v1"
        if self.providers.zhipu.api_key:
            return self.providers.zhipu.api_base
        if self.providers.vllm.api_base:
            return self.providers.vllm.api_base
        return None

    def get_azure_openai(self) -> AzureOpenAIConfig | None:
        """Resolve Azure OpenAI settings from config + env overrides."""
        cfg = self.providers.azure_openai

        env_api_key = (
            os.getenv("AZURE_OPENAI_KEY")
            or os.getenv("AZURE_OPENAI_API_KEY")
            or os.getenv("AZURE_API_KEY")
        )
        env_endpoint = (
            os.getenv("AZURE_OPENAI_ENDPOINT")
            or os.getenv("AZURE_API_BASE")
        )
        env_api_version = (
            os.getenv("AZURE_OPENAI_API_VERSION")
            or os.getenv("AZURE_API_VERSION")
        )
        env_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        env_set = any([env_api_key, env_endpoint, env_api_version, env_deployment])
        enabled = cfg.enabled or env_set
        if not enabled:
            return None

        api_key = env_api_key or cfg.api_key
        endpoint = env_endpoint or cfg.endpoint
        api_version = env_api_version or cfg.api_version
        deployment_name = env_deployment or cfg.deployment_name

        return AzureOpenAIConfig(
            enabled=True,
            api_key=api_key,
            endpoint=endpoint,
            api_version=api_version,
            deployment_name=deployment_name,
        )
    
    class Config:
        env_prefix = "NANOBOT_"
        env_nested_delimiter = "__"
