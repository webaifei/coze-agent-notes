# 02 · 端到端数据流（8 跳）

以本机实测的一轮为例，输入是：**「查看热门服务」**。

## ① 输入框 → Renderer：组装消息

Composer 把输入整理成一份 payload（`app.asar` → `renderer/static/js/async/7754.*.js`）：

```js
G.q.Chat({
  session_id, device_info, content: h.richText,
  files, skill_ids, at_members, plugins, reference_cards, video_option
})
```

其中 `device_info` 决定这条消息**路由到哪台设备**（本机 = `{ type: "local_computer", device_id }`）。

## ② Renderer → 云端 HTTP

```
POST https://www.coze.cn/api/coze_claw/message/chat
```

请求体字段（源自 `renderer/static/js/index.*.js` 的 API client）：

```
session_id, content, files, skill_ids, reference_message_id, at_members,
conversation_id, video_option, quick_reply, meeting_id, reference_cards,
plugins, follow_up_behavior, device_info
```

返回 `message_id`，前端乐观插入气泡并跳转会话。**renderer 从不直连本地 bridge。**

## ③ 云端编排

云端按 `session_id` 定位绑定的 agent 与 device，把消息排成待执行任务。

## ④ 云端 → 本地 bridge：frontier 长连接下行

设备侧主动外连 `wss://frontier.coze.cn`（bridge 是 WS 客户端）。收到的帧（脱敏原文）：

```json
{
  "jsonrpc": "2.0",
  "method": "session/prompt",
  "id": "session.prompt_<ID>",
  "params": {
    "sessionId": "<CLOUD_SESSION_ID>",
    "prompt": [{
      "type": "text",
      "text": "\n<coze-context>\n单聊消息\naccount_id: 0\nsender_user_id: <USER_ID>\nagent_id: <AGENT_ID>\nsession_id: <CLOUD_SESSION_ID>\nmessage_id: <MSG_ID>\nreply_to_message_id: <MSG_ID>\n</coze-context>\n查看热门服务"
    }],
    "_meta": {
      "cozeAgentId": "<AGENT_ID>",
      "cozeDeployType": "local",
      "cozeDeviceId": "<DEVICE_ID>",
      "cozeChannel": "coze",
      "cozeTriggerMsgId": "<MSG_ID>",
      "cozeFollowUpBehavior": "steer",
      "permissionMode": "accept_edits"
    }
  }
}
```

**要点**：用户原文前面被套了一个 `<coze-context>` 信封，携带 sender / agent / session / message 标识——这是 agent 知道「谁在哪个会话里说了什么」的来源。

## ⑤ bridge → 本地 agent：ACP over stdio

bridge 按 `session/` 前缀分发，**懒加载** spawn：

```
命令: <本机>/hermes-agent/venv/bin/hermes-acp
cwd : ~/.coze/agents/<AGENT_ID>/workspace
stdio: pipe
```

ACP 握手序列：

```
→ initialize      { protocolVersion: 1, clientCapabilities: { fs: { readTextFile, writeTextFile } } }
← { agentInfo: { name: "hermes-agent", version: "0.13.0" }, protocolVersion: 1 }
→ session/new     ← 返回可用模型列表
→ session/set_mode ×2
→ session/prompt  { sessionId: "<ACP_SESSION_ID>", prompt: [{ type: "text", text: "<上文载荷>" }] }
```

**会话映射**（两边 id 不同）：

| 云端 | ACP |
|---|---|
| `<CLOUD_SESSION_ID>` | `<ACP_SESSION_ID>` |

`workspace/AGENTS.md` 即系统提示词，例如：

```
你是 <AGENT_NAME>，一个由 Coze 平台驱动的 AI 助手。
你运行在用户本地的环境中，通过 Coze 平台与用户保持沟通……
你的归属用户（user_id）是 <USER_ID>……
```

## ⑥ 本地 agent 内部：真正的 agent loop

```
读本地 agent 配置        → provider / model / base_url
读本地 agent 环境变量     → API key
组装 system prompt(AGENTS.md) + skills + 工具表
      ↓
POST <模型网关>/chat/completions
      ↓
模型返回 tool_call → 本地执行工具 → 结果回灌 → 再调模型 → …… 直到 end_turn
```

会话落盘：`~/.hermes/sessions/session_<ACP_SESSION_ID>.json`（含 `model` / `base_url` / 完整 messages）。

## ⑦ 本地 agent → bridge → 云端：流式回传

agent 通过 stdio 发 ACP 的 `session/update` **通知**（NDJSON，一行一帧）；bridge 拆帧后注入 `_meta`，转成上行 `session/update`。

本轮实测：**737 帧**流式增量，最后

```json
{ "stopReason": "end_turn" }
```

## ⑧ 云端 → 前端 → 渲染

前端经 frontier 订阅（`accessKey` / `deviceId` 来自 `GET /api/coze_claw/resource/get_frontier_key`），按 `service` + `event` 分发，喂给消息 store 做增量渲染。
另有 `GET /api/coze_claw/task/events`（`session_id` + `after_cursor`）作为兜底拉取。

## 一轮完整时序（实测）

| 时间 | 事件 |
|---|---|
| T+0.000 | 云端下发 `session/prompt`（用户消息） |
| T+1.207 | 第一帧 `session/update` 上行 |
| T+1.2 ~ 7.7 | 持续流式，累计 **737 帧** |
| T+7.697 | 最后一帧 |
| — | 前端渲染出最终结果（含工具调用产生的表格） |

总耗时约 **8 秒**，其中绝大部分在 ⑥ 的模型调用与工具执行。

## 一句话数据流

```
文本 → JSON payload → HTTPS → 云端任务队列 → WS 帧 → ACP 帧
     → 模型 API → ACP 通知流 → WS 帧流 → 前端 store → 增量 DOM
```
