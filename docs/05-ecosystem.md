# 05 · 生态版图：谁是谁

## 官方公开仓库（coze-dev 组织，共 18 个）

| 类别 | 仓库 | 许可 |
|---|---|---|
| **Agent 开发平台** | `coze-studio` | Apache-2.0 |
| 评测 / 可观测 | `coze-loop` | Apache-2.0 |
| OpenAPI SDK | `coze-js` / `coze-py` / `coze-go` / `coze-java` / `coze-ios` / `coze-android` / `coze-sdk-gen` | MIT |
| CozeLoop SDK | `cozeloop-js` / `cozeloop-go` / `cozeloop-java` / `cozeloop-python` / `cozeloop-examples` | MIT |
| MCP | `coze-mcp-server`（已归档） | MIT |
| 本地 agent 接入插件 | `coze-openclaw-plugin` | MIT |
| 其他 | `coze-cookbook` / `voice-studio` / `rush-arch` | — |

**没有** `coze-bridge` / `coze-claw` / `coze-desktop` 这类仓库。

## 那 `coze-bridge` 呢？

它以 **npm 包**形式公开发布（声明 MIT），但：

- 发布物是**混淆后的构建产物**（构建脚本里明确 `USE_OBFUSCATED_*`，devDeps 含 `javascript-obfuscator`）
- 依赖 `@agentclientprotocol/codex-acp`、`@agentclientprotocol/claude-agent-acp`
- 描述即：*Local daemon that bridges cloud Agent Service and on-device AI agents over extended ACP*
- **tarball 里没有源码**，也没有对应的公开 GitHub 仓库

结论：这一层**可获取但不可读**，这也是为什么需要解析 `app.asar` 才能看到协议细节。

## 本地 agent 内核来自第三方

| framework | 来源 |
|---|---|
| hermes | **Nous Research** 的 `hermes-agent`（MIT），独立开源项目 |
| codex | OpenAI Codex CLI 的 ACP 包装 |
| claude-code | Anthropic 的 ACP 包装 |
| openclaw | 独立开源项目 |

**Coze 自己实现的是胶水（bridge + 云端编排），不是 agent 内核。**

## coze-studio 是什么（常见误解）

- ❌ 不是 Codex / Claude Code 那类终端编码 agent
- ✅ 是**自托管的 AI Agent 开发平台**（可视化搭 agent / workflow / 插件 / 知识库，再发布成 OpenAPI/Chat SDK）
- 形态更像 **Dify / n8n**，而不是 CLI

它**内部包含** agent runtime：后端 Go + DDD，运行时基于 Eino。

## DAG 与 agent loop：两套运行时

| | DAG 工作流引擎 | Agent loop（Codex 类） |
|---|---|---|
| 控制流 | **边在编译期定死** | **模型运行时决定** |
| 循环 | 结构上禁止，用节点显式表达 | 本质就是 `while` 循环 |
| 步骤概念 | 节点执行（可并行 / 子流程 / 可恢复） | 一次模型推理 |
| 工具调用 | 图上的一个节点 | 模型动态选择 |

coze-studio 的 **workflow** 是前者；它的 **agent** 是「在一张手写好的图里，嵌一个 ReAct 子图」——所以两套运行时共用同一个图引擎。

## CozeLoop SDK 是什么

客户端 SDK，做两件事：

1. **上报 Trace/Span**：把外部应用的 LLM/Agent 调用链上报到 CozeLoop 平台做观测
2. **PromptHub / PTaaS**：拉取、格式化、执行平台托管的 Prompt

它**不含 agent 运行时**。`coze-loop` 仓库本身就是它的用户（后端用 `cozeloop-go` 给自己上报 trace）。

## 一张表定位所有东西

| 名字 | 是什么 | 形态 |
|---|---|---|
| 扣子桌面 + `coze-bridge` | 本地 agent 编排（ACP ↔ 云端） | 桌面应用 + 混淆桥接包 |
| `hermes-agent` / codex / claude-code | 本地 agent 内核 | CLI |
| **coze-studio** | 自托管 agent 开发平台（含 agent/workflow runtime） | 服务端平台 |
| Coze Loop | 评测 + 可观测平台 | 服务端平台 |
| CozeLoop SDK | 接入 CozeLoop 的客户端 | 库 |
| coze-js / coze-py … | 调 Coze OpenAPI 的客户端 | 库 |
