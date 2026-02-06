<div align="center">
  <img src="yiqunbot_logo.png" alt="yiqunbot" width="500">
  <h1>yiqunbot: Ultra-Lightweight Personal AI Assistant</h1>
</div>

## 📦 Install

**Install from source** (latest features, recommended for development)

```bash
git clone https://github.com/ChinaYiqun/yq_bot.git
cd yq_bot
pip install -e .
```

## 🚀 Quick Start

### 1. Initialize

```bash
yiqunbot onboard
```

### 2. Configure

Edit config file: `~/.nanobot/config.json`

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "azure/gpt-5.1-chat",
      "model_bk": "z-ai/glm-4.7",
      "maxTokens": 8192,
      "temperature": 0.7,
      "maxToolIterations": 20
    }
  },


  "channels": {

    "web": {
      "enabled": true,
      "host": "127.0.0.1",
      "port": 18790
    },
    "whatsapp": {
      "enabled": false,
      "bridgeUrl": "ws://localhost:3001",
      "allowFrom": []
    },
    "telegram": {
      "enabled": false,
      "token": "",
      "allowFrom": []
    }
  },
  "providers": {
    "azureOpenai": {
      "enabled": true,
      "apiKey": "",
      "endpoint": "https://wenjinvoice-resource.openai.azure.com/",
      "apiVersion": "2024-12-01-preview",
      "deploymentName": "gpt-5.1-chat"
    },


    "anthropic": {
      "apiKey": "",
      "apiBase": null
    },
    "openai": {
      "apiKey": "",
      "apiBase": null
    },
    "openrouter": {
      "apiKey": "",
      "apiBase": "https://openrouter.ai/api/v1"
    },
    "groq": {
      "apiKey": "",
      "apiBase": null
    },
    "zhipu": {
      "apiKey": "",
      "apiBase": null
    },
    "vllm": {
      "apiKey": "",
      "apiBase": null
    },
    "gemini": {
      "apiKey": "",
      "apiBase": null
    }
  },
  "gateway": {
    "host": "0.0.0.0",
    "port": 18790
  },
  "tools": {
    "web": {
      "search": {
        "apiKey": "",
        "maxResults": 5
      }
    },
    "exec": {
      "timeout": 60,
      "restrictToWorkspace": false
    }
  }
}
```

### 3. Start

```bash
yiqunbot gateway
```

### 4. Access

Open in browser: http://127.0.0.1:18790

## ⚙️ Configuration Instructions

### Core Configuration Items

1. **agents.defaults**
   - `model`: Default model to use, set to `azure/gpt-5.1-chat`
   - `model_bk`: Backup model, set to `z-ai/glm-4.7`
   - `temperature`: Randomness of generated text, set to 0.7

2. **channels.web**
   - `enabled`: Enable web interface, set to `true`
   - `host`: Listen address, set to `127.0.0.1`
   - `port`: Listen port, set to `18790`

3. **providers.azureOpenai**
   - `enabled`: Enable Azure OpenAI, set to `true`
   - `endpoint`: Azure OpenAI endpoint
   - `apiVersion`: API version
   - `deploymentName`: Deployment name

### Notes

- All API key fields have been cleared, please fill in according to your actual situation
- Azure OpenAI configuration is preset, you only need to fill in `apiKey`
- Web interface starts at `127.0.0.1:18790` by default
- To enable WhatsApp or Telegram, please modify the corresponding configuration
