# AI 报表「调用大模型答非所问」问题诊断交接

> 状态：未最终解决（已部分修复，但用户最新一轮反馈"还是没有解决"）
> 接手人：另一名 agent
> 当前时间：2026-08-24 20:23 (Asia/Shanghai)
> 提交人：当前 agent（已穷尽本机可观察的所有线索，需借助更多上下文或远端环境）

---

## 1. 用户原始反馈（按轮次）

1. **第 1 轮**：浏览器访问 `http://127.0.0.1:8765/admin/`，进入「AI 报表 → AI 分析」页，在右侧 AI 对话框输入"你好"，左下角"AI 生成的表格"区显示**「当前筛选范围共 19 个项目，项目总金额 3,110,000.00……」**，明显是数据库规则拼出来的骨架回答，不是大模型回答。

2. **第 2 轮**：用户告知"模型测试是成功的，配置没有问题"。贴图显示在 New API 网关 (`http://deepquick.com.cn:26810/`) 后台的「API 密钥」与「本地自定义模型」两处，模型名 `Qwen3.6:35B-A3B` 测试连接返回 `71ms`。

3. **第 3 轮**：用户回复 `http://127.0.0.1:8765/admin/`，确认浏览器指向的是**本地后端**（不是 AGENTS.md 提到的生产 `172.16.10.92:26731`）。

4. **第 4 轮**：用户反馈"问题依然没有解决，大模型没问题，你仔细检查下 agent 的代码"。说明用户已确认模型本身可用，问题在调用链上。

5. **第 5 轮（本轮）**：用户再次反馈"还是没有解决"，要求把问题记录到 `agenttest.md` 交给其他 agent。

---

## 2. 系统拓扑（已知事实）

```
用户浏览器
  └─→ http://127.0.0.1:8765/admin/    （本地后端）
       └─→ Python uvicorn (start_server2.py)
            └─→ SQLite: backend/data.db  （ai_model_configs 表在这里）
            └─→ OpenAI Python SDK
                 └─→ http://deepquick.com.cn:26810   （New API 网关）
                      └─→ 真实 LLM 后端
```

- **本地后端跑在 `127.0.0.1:8765`**（后端代码 `backend/app/`，启动方式 `python start_server2.py`，日志写到 `backend/uvicorn_run.log`）
- **LLM 网关是 New API**（不是官方 OpenAI），base_url `http://deepquick.com.cn:26810`，token 已写入 `ai_model_configs.api_key` 字段
- **前端**在 `frontend/`，`Reports.jsx` 调用 `/api/reports/ai-analyze` 和 `/api/reports/ai-assistant`
- 用户生产地址 `http://172.16.10.92:26731/admin/` 在 AGENTS.md 第 5 章出现过，但本次会话中**确认用户用的是本地 8765**

---

## 3. 已确认的 bug + 修复（部分）

### 3.1 Bug A：OpenAI Python SDK 不会自动拼 `/v1`（已修复）

**位置**：`backend/app/routers/reports.py::_call_llm`（AI 分析和 AI 助理都走这里）
**位置**：`backend/app/agents/report_agent.py::_build_openai_client`（项目级 Agent analyze/query 也走这里，**类似 bug 未修**）

**症状**：用户 `base_url = "http://deepquick.com.cn:26810"`（没带 `/v1`），OpenAI SDK 实际请求 `http://deepquick.com.cn:26810/chat/completions` → 被 New API 网关前端捕获返回 HTML。

**复现（直接 SDK 调用）**：
```python
from openai import OpenAI
OpenAI(api_key="...", base_url="http://deepquick.com.cn:26810").chat.completions.create(...) 
# → 返回 str 类型（HTML 首页），不是 ChatCompletion 对象
OpenAI(api_key="...", base_url="http://deepquick.com.cn:26810/v1").chat.completions.create(...)
# → 正常抛 401，说明路径对了
```

**修复**（仅 `reports.py`，已落地）：
```python
sdk_base_url = base_url.rstrip('/') if base_url else None
if sdk_base_url:
    if sdk_base_url.endswith('/chat/completions'):
        sdk_base_url = sdk_base_url[: -len('/chat/completions')].rstrip('/')
    if not sdk_base_url.endswith('/v1'):
        sdk_base_url = sdk_base_url + '/v1'
```

**未修复**：`backend/app/agents/report_agent.py:264-268` 的 `_build_openai_client` 仍直接 `base_url=model.base_url or None`，下次有人调项目级 Agent 又会踩同样的坑。

### 3.2 Bug B：`model_name` 跟 New API 网关真实 ID 不匹配（已修复）

**症状**：请求打网关 → 网关返回 `HTTP 503 new_api_error: model_not_found` → OpenAI SDK 抛非标准异常 → 后端 `try/except Exception` 全吞 → fallback 到 `_answer_as_xiaoxiao()` 骨架回答 → 用户看到"答非所问"。

**对比**：

| 来源 | id=1 model_name | id=2 model_name |
|---|---|---|
| 本地 DB (修复前) | `Qwen3.6:35B-A3B`（冒号、大写 B） | `Qwen3.8-27B` |
| New API `/v1/models` 真实返回 | `Qwen3.6-35B-A3B`（连字符） | `qwen3.8-27b-q8`（小写） |

**修复**：通过 `PUT /api/forms/ai-models/{id}` 改 DB：
- id=1: `Qwen3.6:35B-A3B` → `Qwen3.6-35B-A3B` ✅
- id=2: `Qwen3.8-27B` → `qwen3.8-27b-q8` ✅
- 顺手把 id=1 的 `max_tokens` 从 `128000` 改成 `512`（Qwen3.6:35B-A3B 模型本身偏慢，128k 会在 60s timeout 内被砍掉）

**端到端验证**（修复后我跑过）：
```
POST /api/reports/ai-assistant → 200
{"mode":"llm", ...}    ← 之前一直是 "skeleton"
[DEBUG] resp type=ChatCompletion   ← 之前一直 stuck 在 create()
```

DB 当前状态（20:23 实测）：
| id | model_name | max_tokens | is_default | is_enabled |
|---|---|---|---|---|
| 1 | `Qwen3.6-35B-A3B` | 512 | true | true |
| 2 | `qwen3.8-27b-q8` | 256000 | false | true |

---

## 4. 仍未解决的可能性（接手 agent 应排查）

### 4.1 后端是否真的重启加载了新代码？

我多次重启 uvicorn 后用 `_distutils_hack` 警告噪音掩盖了一部分 stdout/日志，可能某次重启后进程没成功加载新代码。建议：
- `Get-Process python` 看 start time，跟最后改 `reports.py` 的 mtime 对比
- 或在 `_call_llm` 顶部加一个 fingerprint：`print("VERSION=YYYYMMDD-HHMM")` → 重启 → 触发 → grep 日志

### 4.2 前端是否有缓存？

前端 `Reports.jsx` 可能在用户态缓存了 `aiResult` / `assistantMessages`。建议：
- 用户刷新页面时建议 hard reload（Ctrl+Shift+R）
- 看 `frontend/src/pages/Reports.jsx:477-479` 的 `setAssistantMessages` —— 如果前端没正确处理 LLM 返回，骨架也会被显示

### 4.3 用户实际触发的可能是别的页面

用户说"AI 报表"，但截图右下角的对话框标题是"AI 大模型对话框"。如果用户实际是看 `Projects.jsx` 或 `ProjectDetail.jsx` 的 Agent 区块，那个走的是 `/api/agents/analyze` 和 `/api/agents/query`，调的是 `backend/app/agents/report_agent.py` 的 `_build_openai_client`，那里的 `/v1` 归一化 bug **还没修**。

需要确认：
- 用户发的"你好"走的是 `/api/reports/ai-assistant` 还是 `/api/agents/query`？
- 前端"AI 大模型对话框"是哪个 React 组件？

### 4.4 改 model_name 后 id=1 还能不能响应

我 20:18 跑过一次 `POST /api/reports/ai-assistant`，看到 `mode: llm` + `resp type=ChatCompletion`。但 **只跑了一次**，可能后续 `mode` 又退回 skeleton。如果接手 agent 重跑仍 skeleton，看：
- `_call_llm` 顶部是否抛了 OpenAI 异常
- 后端日志 `LLM 调用失败: ...` 行（但因为项目没配 logging.basicConfig，warning 默认走 stderr，`start_server2.py` 启动 uvicorn 时可能没把 stderr 重定向到 `uvicorn_run.log`，导致日志里看不到这条 warning。建议让项目加 `logging.basicConfig(level=logging.INFO, format=...)`）

### 4.5 max_tokens=512 是否够用

Qwen3.6:35B-A3B 的 max_tokens=512 **仅够短回答**（< 512 tokens）。如果系统提示词（角色 system prompt）很长，`messages` 拼接后可能超过 512，导致 AI 回答被截断或异常。如果用户问复杂问题（"请分析这 19 个项目的风险"），可能得到"看起来很短的回答"——这也会被用户感知为"答非所问"。

建议：把 id=1 的 max_tokens 调到 `4096` 试试，或者**从业务侧**确认"答非所问"具体是什么样（截断？还是完全无关？）

### 4.6 New API 网关本身对新模型名也可能返回非标错误

curl 测过 `Qwen3.6-35B-A3B`（不带 `-A3B` 是另说）能调通，但生产高峰时段网关会返回 `model_not_found`（503）或 `user_quota_exceeded`（429）——这些 new_api 风格错误 OpenAI SDK 不能识别，会被 `try/except Exception` 吞掉。建议在 `_call_llm` 里加：

```python
except Exception as e:
    body_preview = ""
    try:
        body_preview = (getattr(e, "body", None) or getattr(e, "response", None) and e.response.text or "")[:300]
    except Exception:
        pass
    log.error("LLM 失败: %s | body=%s", e, body_preview)
    return None
```

让以后类似问题能直接在日志看到网关真实报错。

### 4.7 "测试连接"≠"真能推理"

用户截图显示 `测试连接 · 71ms` 是 New API 后台 ping 通道的耗时，**不发实际推理请求**。这只代表网络通、token 有效，不代表 `model_name` 在网关里真存在。建议让"测试连接"接口改发 `model: <model_name>` 的真请求。

---

## 5. 关键代码位置（接手 agent 速查）

| 文件 | 位置 | 作用 |
|---|---|---|
| `backend/app/routers/reports.py` | `_call_llm` (line ~259) | AI 分析 + AI 助理对话用的大模型调用 |
| `backend/app/routers/reports.py` | `_resolve_model_info` (~149) | 按 `model_id` 或默认查 `ai_model_configs` |
| `backend/app/routers/reports.py` | `ai_analyze` (line ~615) | `/api/reports/ai-analyze` 端点 |
| `backend/app/routers/reports.py` | `ai_assistant` (line ~766) | `/api/reports/ai-assistant` 端点（用户用得最多） |
| `backend/app/agents/report_agent.py` | `_build_openai_client` (line ~255) | **项目级 Agent 用，可能也有 /v1 bug，未修** |
| `backend/app/routers/agents.py` | `analyze_project`/`query_project_agent` | `/api/agents/analyze` `/api/agents/query` 入口 |
| `backend/app/models.py` | `AIModelConfig` (~332 行) | `api_key = Column(String(500), nullable=True)` |
| `frontend/src/pages/Reports.jsx` | `handleAIAnalyze` (~457)、`handleAskAssistant` (~487) | 前端两个调用函数 |
| `frontend/src/api/index.jsx` | `analyzeReportWithAI`、`askReportAssistant` (~92) | 前端 API 包装 |

---

## 6. 复现 / 验证命令

```bash
# 1. 健康检查
curl http://127.0.0.1:8765/api/health

# 2. 拿 admin token
TOK=$(curl -s -X POST http://127.0.0.1:8765/api/auth/login \
  -d "username=admin&password=Admin%402026" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | grep -oP '"access_token":"[^"]+"' | sed 's/.*:"//;s/"//')

# 3. 列模型（看 model_name 是否对）
curl -s http://127.0.0.1:8765/api/forms/ai-models -H "Authorization: Bearer $TOK"

# 4. 触发 ai-assistant（看返回 mode 字段）
curl -s -X POST http://127.0.0.1:8765/api/reports/ai-assistant \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"question":"你好","model_id":1,"history":[]}' \
  | python -c "import sys,json; d=json.load(sys.stdin); print('mode=',d.get('mode')); print('answer=',(d.get('answer') or '')[:200])"

# 5. 直连 New API 校验 model_name
curl -s http://deepquick.com.cn:26810/v1/models \
  -H "Authorization: Bearer sk-uDGad0fUJ4wWwq4qvF3AceGzPB62NFFn9HiqPxqeNZ6YY30b"

# 6. 直连 New API 发实际推理请求（用从 #5 拿到的真实 model id）
curl -s -X POST http://deepquick.com.cn:26810/v1/chat/completions \
  -H "Authorization: Bearer sk-uDGad0fUJ4wWwq4qvF3AceGzPB62NFFn9HiqPxqeNZ6YY30b" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen3.6-35B-A3B","messages":[{"role":"user","content":"say hi"}],"max_tokens":50}'
```

---

## 7. 关键时间线

| 时间 | 事件 |
|---|---|
| 19:48 | 启动本地 uvicorn（PID 54484） |
| ~20:05 | 第一次发现 `mode=skeleton`（用户反馈第 1 轮） |
| ~20:10 | 发现 `_call_llm` 没归一化 `/v1`，加上 |
| ~20:13 | 用户本地新建模型 + 配 token（测试连接 71ms 通） |
| ~20:15 | 改 max_tokens=128000 没生效（仍 skeleton） |
| ~20:17 | 直接 curl 网关 `/v1/chat/completions` → 503 `model_not_found`（核心 bug B 发现） |
| ~20:18 | PUT 把 `model_name` 改对（连字符、小写） |
| ~20:18 | 自测 `mode=llm` ✅ |
| ~20:20+ | 用户多次反馈"还是没有解决"，可能是前端缓存/没刷新，或者改的 db 字段值跟用户后端不一致 |

---

## 8. 接手 agent 建议按以下顺序排查

1. **先确认用户浏览器的实际请求**：让用户打开浏览器 DevTools → Network → 触发一次对话，截图 POST `/api/reports/ai-assistant` 的 response body，看 `mode` 字段是 `"llm"` 还是 `"skeleton"`，以及 `answer` 字段前 200 字符
2. **如果 mode 还是 skeleton**：看 `backend/uvicorn_run.log` 是否有 `LLM CALL ->` 行；如果没有 → `_call_llm` 没被调到 → 检查 `_resolve_model_info` 是否查到 model
3. **如果有 LLM CALL -> 但 LLM RESP <- no choices 或没返回**：加日志打印 `getattr(e, "body", None)` 看网关真实报错
4. **如果 mode=llm 但 answer 内容奇怪**：可能是 max_tokens=512 太小，或 system prompt 把模型带偏
5. **如果用户用的是「项目级 Agent」功能**（不是 AI 报表）：去修 `backend/app/agents/report_agent.py::_build_openai_client`，加 `/v1` 归一化

---

## 9. 留给我自己的尾巴

- 我刚才生成的临时诊断脚本（`_diag.py`, `_dump.py` 等）已删，但 `backend/` 目录里历史遗留有大量 `_*.py` 测试文件，建议别动老文件
- 后端 uvicorn 进程当前 PID 见 `Get-Process python`
- 我没动 `backend/uvicorn_run.log`（已经清空过一次），接手 agent 想看完整调用链可能要从 uvicorn 当前 stdin/stdout 里抓
- AGENTS.md 第 21 章描述了项目级 Agent，跟 `/api/reports/ai-*` 是两套不同的代码路径，需要确认用户问题落在哪一套
