# 04 · 排查手册

## 日志地图

| 想看什么 | 去哪 |
|---|---|
| 云端下发了什么、回了什么 | `~/.coze/bridge/logs/bridge-YYYY-MM-DD.log` |
| agent 生命周期 / skill 安装 / spawn | `~/.coze/agents/<agentId>/logs/agent-YYYY-MM-DD.log` |
| 会话内容、用的模型与 endpoint | `~/.hermes/sessions/session_<acpSessionId>.json` |
| 模型调用失败详情 | `~/.hermes/sessions/request_dump_*.json` |
| 设备绑定与 agent 列表 | `curl -H "Authorization: Bearer $(cat ~/.coze/bridge/bridge.token)" http://127.0.0.1:<bridgePort>/status` |
| 云端链路 id | 每帧里的 `logid` / `logidNew` |

## 三种典型故障的判别口诀

### 1. 发了没反应，日志里根本没有 `session/prompt`

```bash
grep -c 'session/prompt' ~/.coze/bridge/logs/bridge-$(date +%F).log
```

计数不涨 → 消息**没下到设备**。常见原因：

- **deviceId 变了**（设备重注册会换 id，旧绑定失效）
- 客户端登录的**账号/空间**与 agent 归属不一致
- 网络把 `frontier.coze.cn` 断了（日志里有 `getaddrinfo ENOTFOUND` / `ws not open`）

### 2. 有 `session/prompt`，但 `session/update` 只有一帧、约 367 字节

这是**模型调用失败**的典型签名（错误被当成一次「空回复」结束）。

```bash
ls -t ~/.hermes/sessions/request_dump_*.json | head -1 | xargs -I{} python3 -c "
import json,sys; d=json.load(open('{}'))
print(d.get('reason')); print(d['request'].get('url')); print(d['error'].get('message'))"
```

常见错误：

| 现象 | 含义 |
|---|---|
| `403 Request not allowed` | 凭证类型不被该端点接受（例如把 OAuth 令牌直接用于公开 API） |
| `401` | key 无效 / 过期 |
| `429` | 额度或限流 |

### 3. `_agent/detail` 一直报 `70004 get claw failed`

```bash
grep -c '70004' ~/.coze/bridge/logs/bridge-$(date +%F).log
```

说明 bridge 拿着本地登记的 agent 去云端问详情，云端说**不存在**。
即：**客户端看不到某 agent ≠ 本地文件被删**。客户端列表以**云端 + deviceId 绑定**为准，本地 `~/.coze/agents/*` 可能只是孤儿。

## 改完本地 agent 配置后要做什么

本地 agent 进程（如 `hermes-acp`）是从 bridge spawn 出来的，**启动时才读配置和环境变量**。改完配置必须让它重启：

```bash
pkill -f hermes-acp        # 下次 prompt 时 bridge 会重新 spawn
# 或
<bridge>/bin/coze-bridge restart
```

只改配置文件不重启，旧进程仍会用旧配置。

## 一致性自检脚本（示例）

```bash
# 1) bridge 在跑吗
<bridge>/bin/coze-bridge status

# 2) 今天有没有成功的一轮（prompt → 多帧 update → end_turn）
grep -E 'session/prompt|session/update' ~/.coze/bridge/logs/bridge-$(date +%F).log | tail -20

# 3) 本地各 agent 概览
for f in ~/.coze/agents/*/config.json; do
  python3 -c "import json,sys;d=json.load(open('$f'));print(d.get('framework'),d.get('agentId'),d.get('agentName'),len(d.get('sessions',{})))"
done
```
