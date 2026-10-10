# 03 · 协议与本地运行时

## 三个协议层

| 层 | 协议 | 传输 | 端点 |
|---|---|---|---|
| 前端 ↔ 云端（发消息） | HTTPS + JSON | — | `POST /api/coze_claw/message/chat` |
| 云端 ↔ bridge | JSON-RPC 2.0 | WebSocket | `wss://frontier.coze.cn` |
| bridge ↔ 本地 agent | **ACP**（Agent Client Protocol，扩展版） | stdio（NDJSON） | 无 |

### 帧格式

**frontier（WS 文本帧，纯 JSON）**
```json
{ "jsonrpc": "2.0", "id": "...", "method": "session/prompt", "params": { ... } }
```

**ACP（stdio，一行一帧 JSON + `\n`）**
```json
{ "jsonrpc": "2.0", "id": "...", "method": "session/prompt", "params": { ... } }
```

bridge 侧用一个 NDJSON 解码器拆帧；写子进程 stdin 时逐帧 `JSON.stringify(x) + "\n"`。

## 方法清单

### 云端 → bridge（扩展方法，`_` 前缀）

```
_agent/create | update | detail | health | pair | disconnect | reset | repair
       | upgrade | listSkills | addSkills | removeSkills | publishSkill
       | getFileTree | getFileContent | listAvailableModels | switchModel
       | setConfigOption | genModelToken
_project/create | delete | getFileTree | getFileContent
_tool/readFile | writeFile | editFile | bash
```

### 会话类（ACP 标准 + 扩展）

```
initialize
session/new | load | prompt | cancel | update
session/set_mode | set_model | set_config_option | request_permission
```

### 分发规则

```
handleFrame:
  method 以 _agent/ _project/ _tool/ 开头 → extensions
  method 以 session/ 开头               → routeSessionMethod
  method == initialize                  → 返回 { protocolVersion: 1, agentCapabilities: { loadSession: true } }
```

## 本地 agent 框架适配

bridge 按 agent 的 `framework` 字段选择启动命令：

| framework | 启动命令 | 说明 |
|---|---|---|
| `hermes` | `hermes-acp` | 第三方开源 agent（Nous Research），args 为空 |
| `codex` | `codex-acp` | `@agentclientprotocol/codex-acp` 包装 |
| `claude-code` | `claude-agent-acp` | `@agentclientprotocol/claude-agent-acp` |
| `openclaw` | `openclaw acp --session agent:<id>:<name>` | 可选 `--token` |

检测结果缓存在 `~/.coze/bridge/config.json` 的 `frameworksCache`。

## agent 配置

`~/.coze/agents/<agentId>/config.json` 关键字段：

```json
{
  "agentId": "<AGENT_ID>",
  "agentName": "<名称，早期版本可能缺失>",
  "framework": "hermes",
  "workspace": "~/.coze/agents/<AGENT_ID>/workspace",
  "cozeIdentity": "<系统提示词，同时写入 workspace/AGENTS.md>",
  "model": "auto",
  "resolvedModelId": "<provider:model>",
  "sessions": {
    "<CLOUD_SESSION_ID>": {
      "acpSessionId": "<ACP_SESSION_ID>",
      "permissionMode": "accept_edits",
      "cozeGroupId": "..."
    }
  },
  "skills": [ "coze-project", "coze-file-send", "skill-assistant", "coze-agent-collaboration", "coze-device" ]
}
```

`deleteReason: "agent_deleted"` + `deletedAt` 表示该 agent 已在云端删除，本地目录成为孤儿。

## 凭证模型（重要）

「本地 agent 用什么模型」由**本地 agent 自己的配置**决定：

- `deployType: local` 且 `modelToken` 为空时，agent 使用**自己的本地凭证**直连模型厂商
  （实测：`base_url = https://api.anthropic.com`，失败即 `request_dump_*.json` 里的 403）。
- 云端下发的是 `session/prompt` 与 `_meta`，**不含模型凭证**。
- 因此：**换模型要改本地 agent 的配置，然后重启 agent 进程**（见 04）。

## 桌面主进程与 bridge 的关系

- 主进程通过 IPC `device:connect-agent` 触发接入，命令做严格白名单校验，只允许
  `npx -y [--registry=<npmjs|npmmirror>] coze-bridge[@version] …` 或 `@coze/bridge[@version] …`。
- 主进程有 bridge guardian：定期检查 + 断线指数退避重连。
- bridge 本地 IPC（`127.0.0.1:<bridgePort>`，Bearer = `bridge.token`）：
  `GET /status`、`POST /connect | /_agent/create | /agent/send | /pair | /reload | /shutdown`。
- bridge CLI：`<bridge>/bin/coze-bridge start|stop|restart|status|connect`。

## 设备与绑定

- 每次设备重新注册会拿到**新的 deviceId**；agent 绑定在 deviceId 上。
- 云端对本地已登记的 agent 会周期性发 `_agent/detail` 同步；若返回
  `70004 get claw failed`，说明云端已不认这些 agent（本地目录成了孤儿）。
