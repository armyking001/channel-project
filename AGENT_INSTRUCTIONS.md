AI Agent 集成指引（给 Trae 的机器可读说明）
版本说明

目标仓库：armyking001/channel-project
目标：在现有项目中新增一个面向管理者的 AI Agent 功能，用于分析填报的项目资料、跟单情况，返回项目可靠性评分、销售积极性评分、关键发现、建议与可追溯证据。
要求兼容仓库现有模式（FastAPI + SQLAlchemy + Pydantic + 前端 Vite/React），并使用仓库已有的 AI 模型配置（表 ai_model_configs）作为模型来源（不改变现有 3 个预置模型的配置）。
总体策略

使用现有 AIModelConfig 表（backend/app/models.py）选取模型：若请求里传 model_id 则用该配置；否则使用 is_default 或首个启用模型。
向量存储默认使用 Chroma（本地持久化），embedding provider 可为 OpenAI 或 本地 sentence-transformers；支持环境变量与数据库中 AIModelConfig 的 provider/base_url/api_key 匹配。
实现 RAG 流程：检索（agent_indexer）→ 构建 prompt（严格要求 LLM 返回 JSON）→ 调用模型（使用现有模型配置接入方式）→ 解析并返回结构化结果。
所有新接口遵循现有鉴权/依赖风格（Depends(get_db)、Depends(get_current_user)、或 require_not_archive 占位）。
要生成/修改的文件（精确路径）

新增：backend/app/services/agent_indexer.py

功能：为 project 构建向量索引（text chunking、embedding、写入 Chroma collection）、提供 get_context_for_project(project_id, top_k) 和 build_index_for_project(project_id) 与 delete_project_index(project_id)。
设计要点：
使用 CHROMA_DIR 环境变量或 config.yaml 中配置 CHROMA_DIR。
Embedding provider 支持：优先使用 OpenAI（若 model.provider 指向 openai_compatible 且有 api_key），否则 fallback 到 sentence-transformers（all-mpnet-base-v2）。中文切分使用简单分句逻辑（参考现有项目风格，可直接引入 jieba）。
Metadata 包含：project_id, source_type (form_field/file/followup), source_id, field_name, created_at。
提供 CLI 接口（main 支持 --build/--delete/--get）。
新增：backend/app/agents/report_agent.py

功能：实现 analyze(contexts, analyze_types, model_id, db, current_user) 与 query(question, contexts, model_id, db, current_user)。
analyze 要点：
先做 rule-based baseline：例如近 30 天跟单次数、是否有 tender/bid 文件、责任销售是否存在、最近跟单更新时间等，产出 rule_basis 字典并给出 baseline 分数。
将 baseline 内容与检索到的上下文打包进 LLM prompt，要求 LLM 返回单一 JSON（见 LLM Prompt 标准段）。
最多重试 LLM 调用 2 次；解析结果并转为 Pydantic 结构（AgentAnalyzeResponse）。若 LLM 返回非法 JSON，记录原始返回并返回 500（同时在日志保留完整内容）。
返回要包含：project_id, reliability_score (0-100 float), sales_activity_score (0-100 float), findings（最多 6 条）、recommendations、evidences（每条 evidence 标明 source_type/source_id/snippet）和 rule_basis。
query 要点：
执行检索并调用 LLM 以自然语言回答，返回 AgentQueryResponse（answer, sources, score）。
新增：backend/app/routers/agents.py

路由：
POST /api/agents/analyze
Request: AgentAnalyzeRequest（见 schemas）
Response: AgentAnalyzeResponse
行为：调用 agent_indexer.get_context_for_project(project_id, top_k)， 若无索引先执行 build_index_for_project，然后调用 report_agent.analyze。
POST /api/agents/query
Request: AgentQueryRequest
Response: AgentQueryResponse
行为：同上但调用 report_agent.query
路由风格要与 backend/app/routers/projects.py 一致（logger、get_db、get_current_user/require_not_archive）。
修改：backend/app/schemas.py（在合适位置追加）

新增 Pydantic 类型（与仓库现有风格保持一致，使用 ConfigDict(from_attributes=True) 与 field_validator）：
AgentAnalyzeRequest: { project_id:int, query:Optional[str]=None, analyze_types:List[str]=["reliability","sales_activity"], top_k:int=5, model_id:Optional[int]=None }
EvidenceItem: { source_type:str, source_id:Optional[int], score:Optional[float], snippet:str }
FindingItem: { title:str, detail:str, score:Optional[float], evidences:List[EvidenceItem] }
AgentAnalyzeResponse: { project_id:int, reliability_score:float, sales_activity_score:float, findings:List[ FindingItem ], recommendations:List[str], evidences:List[EvidenceItem], rule_basis:Optional[dict] }
AgentQueryRequest / AgentQueryResponse
修改：backend/app/main.py

在“注册路由”区域加入： app.include_router(agents.router)
保证导入语句符合现有顺序（from app.routers import ...），建议把 agents 放在其它 routers 附近。
新增前端（最小实现）

frontend/src/api/agents.js
analyzeProject(projectId, analyzeTypes, top_k) → POST /api/agents/analyze
queryAgent(projectId, question, top_k) → POST /api/agents/query
使用仓库已有的前端 api 封装（frontend/src/api/index.jsx）风格：调用 api.post('/agents/...' ) 或相同封装名
frontend/src/pages/AgentConsole.jsx
最小 UI：项目下拉（调用 /api/projects），Analyze 按钮，Query 输入框，结果展示（评分/发现/建议/证据）。
样式参考 Reports.jsx 与其它页面（复用现有 modal 或 card 组件样式）。
新增测试

backend/tests/test_agent.py
用 pytest + FastAPI TestClient
Mock agent_indexer.get_context_for_project 返回固定段落
Mock LLM 调用（可 monkeypatch report_agent 的内部调用）返回已知 JSON
验证 /api/agents/analyze 返回 HTTP 200 且结构符合 AgentAnalyzeResponse
依赖变更

在 backend/requirements.txt 追加（按需要）：
chromadb>=0.4.0
sentence-transformers>=2.2.2
jieba (或其它中文分句库)（可选）
openai>=0.27.0 (仅在需要 OpenAI embeddings/LLM 时)
若项目使用 pyproject/poetry，请相应更新（本任务优先改 requirements.txt）。
配置与环境变量

CHROMA_DIR：向量库持久化目录（优先从环境变量读取；fallback 到 config.yaml）
AGENT_EMBEDDING_PROVIDER： "auto"（默认） | "openai" | "local"
OPENAI_API_KEY：当 provider= openai_compatible 时使用（也可从 AIModelConfig.api_key 读取）
AGENT_DEFAULT_TOP_K：默认检索条数（若请求未提供）
LLM Prompt 模板（必须严格遵守——要求 LLM 仅输出单一 JSON）

在 report_agent 中嵌入以下模板（中文），向 LLM 发送时把 contexts 按 SOURCE_1..N 编号并在 prompt 中逐条列出。
模板（以三引号文本形式放入代码）：

""" 你是企业项目评估助手。下面给出若干上下文段（每段以 [SOURCE_n] 标注），以及一些基于规则的基准计算（rule_basis）。 请基于这些上下文和基准输出一个单一的 JSON 对象（不要输出任何额外的文本或解释），格式严格为： { "reliability_score": number, // 0-100 "sales_activity_score": number, // 0-100 "findings": [ {"title":"...","detail":"...","score":number,"evidences":["SOURCE_1","SOURCE_3"]}, ... ], "recommendations": ["...","..."], "evidences": [ {"source":"SOURCE_1","source_type":"form_field","source_id":123,"snippet":"..."}, ... ], "rule_basis": { /* 前面传入的基准计算结果，或模型自己补充 */ } } 要求：

findings 最多 6 条，每条至少包含 1 条 evidences（引用 SOURCE_n）。
scores 保持数值类型（允许小数）。
evidence snippet 最多 300 字，若包含敏感字段（手机号/身份证号），请对数字中间做脱敏（例如 13****7890）。
如果采用 rule_basis 的基线，务必在 JSON 中保留 rule_basis 字段并说明量化依据。 """
示例请求 / 响应（验收用例）

POST /api/agents/analyze
body: { "project_id": 123, "analyze_types": ["reliability","sales_activity"], "top_k": 5 }
期望响应（示例）: { "project_id": 123, "reliability_score": 72.5, "sales_activity_score": 56.0, "findings": [{"title":"资料不齐","detail":"缺少技术规格书","score":60,"evidences":["SOURCE_4"]}], "recommendations":["补齐技术规格书并安排技术对接"], "evidences":[{"source":"SOURCE_4","source_type":"file","source_id":45,"snippet":"..."}], "rule_basis":{"followup_count_30d":2,"has_tender_file":false} }
验收标准（Trae 生成后必须通过）

新增文件能 import（没有路径错误），代码风格与项目一致（导入 app.*，使用 Depends(get_db) 等）。
启动后访问 /api/agents/analyze 可得到 200/JSON（若数据库中无模型或数据，返回合理的 4xx 错误）。
测试文件能通过 pytest（至少 mock 路径，跑通 analyze happy path）。
所有外部服务调用（Chroma/OpenAI）均有超时与简单重试逻辑（2 次）。
新增的依赖列在 backend/requirements.txt，并在 README（或 AGENTS.md）新增使用说明。
安全与隐私注意

在返回 snippet 时尽量脱敏；若用户需要返回完整原文，需在 docs 中明确说明。
不要在代码或提交里写入任何敏感密钥（OPENAI_API_KEY 等应从 env 或 DB 安全字段读取，不要硬编码）。
运行命令（在仓库根目录）

本地索引项目示例：
python -m backend.app.services.agent_indexer --build 123
启动后端：
cd backend
python start_server.py （或 uvicorn app.main:app --reload）
运行测试：
cd backend
pytest -q
变更提交要求（Trae 必须遵守）

新分支： feature/ai-agent
单次提交或按文件分多次提交均可，但最终需要有单个合并分支 feature/ai-agent。
commit message 示例： feat(agent): add report analysis agent (indexer, agent, router, frontend console)
生成完毕后创建 PR 并在 PR 描述中包含「如何本地测试」部分（copy 本文件中的运行命令与验收标准）。