<div align="center">
  <img src="nanobot_logo.png" alt="nanobot" width="500">
  <h1>nanobot: Ultra-Lightweight Personal AI Assistant</h1>
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
nanobot onboard
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

### 3. 启动

```bash
nanobot gateway
```

### 4. 访问

浏览器打开：http://127.0.0.1:18790

## ⚙️ 配置说明

### 核心配置项

1. **agents.defaults**
   - `model`: 默认使用的模型，这里设置为 `azure/gpt-5.1-chat`
   - `model_bk`: 备用模型，设置为 `z-ai/glm-4.7`
   - `temperature`: 生成文本的随机性，设置为 0.7

2. **channels.web**
   - `enabled`: 启用 web 界面，设置为 `true`
   - `host`: 监听地址，设置为 `127.0.0.1`
   - `port`: 监听端口，设置为 `18790`

3. **providers.azureOpenai**
   - `enabled`: 启用 Azure OpenAI，设置为 `true`
   - `endpoint`: Azure OpenAI 端点
   - `apiVersion`: API 版本
   - `deploymentName`: 部署名称

### 注意事项

- 所有 API key 字段已清空，请根据实际情况填写
- Azure OpenAI 配置已预设，只需填写 `apiKey`
- Web 界面默认在 `127.0.0.1:18790` 启动
- 如需启用 WhatsApp 或 Telegram，请修改对应配置
