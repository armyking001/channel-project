from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import UserRole
from app.services import agent_indexer
from app.agents import report_agent


class DummyDB:
    pass


def _fake_user():
    return SimpleNamespace(
        id=1,
        username="tester",
        real_name="测试用户",
        role=UserRole.admin,
        children=[],
    )


def _fake_project(project_id=123):
    followup = SimpleNamespace(
        id=9001,
        stage=SimpleNamespace(value="商务沟通"),
        progress="客户已确认需求，等待技术方案补充。",
        risks="技术规格书还未定稿。",
        next_plan="补充技术规格书并安排演示。",
        next_owner="张三",
        expected_amount=128.0,
        expected_sign_date=None,
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    return SimpleNamespace(
        id=project_id,
        project_name="AI Agent 测试项目",
        project_code="AGT-001",
        project_type=SimpleNamespace(value="信息化"),
        source="channel",
        partner_company="测试客户",
        responsible_sales="李四",
        project_amount=256.0,
        expected_amount=300.0,
        fee_amount=6.0,
        project_overview="这是一个用于验证 Agent 分析链路的测试项目。",
        approval_status=SimpleNamespace(value="pending_approval"),
        win_bid_status=SimpleNamespace(value="in_progress"),
        tender_file="招标文件.docx",
        bid_file=None,
        tender_folder=None,
        bid_folder=None,
        form_instance_id=1,
        followups=[followup],
    )


def _override_db():
    return DummyDB()


def _override_user():
    return _fake_user()


def _mock_contexts():
    return [
        {
            "source": "SOURCE_1",
            "text": "项目名称：AI Agent 测试项目。责任销售：李四。合作公司：测试客户。",
            "score": 0.91,
            "source_type": "form_field",
            "source_id": 123,
            "field_name": "project_summary",
            "created_at": datetime.utcnow().isoformat(),
        },
        {
            "source": "SOURCE_2",
            "text": "跟单阶段：商务沟通。当前进展：客户已确认需求，等待技术方案补充。",
            "score": 0.88,
            "source_type": "followup",
            "source_id": 9001,
            "field_name": "followup",
            "created_at": datetime.utcnow().isoformat(),
        },
    ]


def test_agent_analyze_happy_path(monkeypatch):
    fake_project = _fake_project()
    fake_model = SimpleNamespace(
        id=1,
        name="Mock Model",
        model_name="mock-model",
        base_url="http://mock.local/v1",
        api_key="test-key",
        timeout_seconds=10,
        temperature=0.2,
        max_tokens=1200,
    )

    monkeypatch.setattr(report_agent, "load_project_or_403", lambda project_id, db, current_user: fake_project)
    monkeypatch.setattr(report_agent, "_resolve_model", lambda db, model_id: fake_model)
    monkeypatch.setattr(
        agent_indexer,
        "get_context_for_project",
        lambda project_id,
        top_k=5,
        db=None,
        query_text=None,
        model_id=None: _mock_contexts())
    monkeypatch.setattr(
        agent_indexer,
        "build_index_for_project",
        lambda project_id,
        db=None,
        model_id=None: 2,
    )
    monkeypatch.setattr(
        report_agent,
        "_call_llm",
        lambda model, prompt: """
{"reliability_score":78.5,"sales_activity_score":66.0,"findings":[{"title":"资料较完整","detail":"核心资料和最近跟单记录都已存在。","score":82,"evidences":["SOURCE_1","SOURCE_2"]}],"recommendations":["继续补齐技术规格书并保持每周跟进"],"evidences":[{"source":"SOURCE_2","source_type":"followup","source_id":9001,"snippet":"客户已确认需求，等待技术方案补充。"}],"rule_basis":{"followup_count_30d":1,"has_tender_file":true}}
""".strip(),
    )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)
    try:
        response = client.post(
            "/api/agents/analyze",
            json={"project_id": 123, "analyze_types": ["reliability", "sales_activity"], "top_k": 5},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == 123
    assert body["reliability_score"] == 78.5
    assert body["sales_activity_score"] == 66.0
    assert body["findings"][0]["title"] == "资料较完整"
    assert body["findings"][0]["evidences"][0]["source_type"] == "form_field"
    assert body["evidences"][0]["source_type"] == "followup"


def test_agent_analyze_invalid_json(monkeypatch):
    fake_project = _fake_project()
    fake_model = SimpleNamespace(
        id=1,
        name="Mock Model",
        model_name="mock-model",
        base_url="http://mock.local/v1",
        api_key="test-key",
        timeout_seconds=10,
        temperature=0.2,
        max_tokens=1200,
    )
    calls = {"count": 0}

    def _bad_llm(model, prompt):
        calls["count"] += 1
        return "not-a-json-response"

    monkeypatch.setattr(report_agent, "load_project_or_403", lambda project_id, db, current_user: fake_project)
    monkeypatch.setattr(report_agent, "_resolve_model", lambda db, model_id: fake_model)
    monkeypatch.setattr(
        agent_indexer,
        "get_context_for_project",
        lambda project_id,
        top_k=5,
        db=None,
        query_text=None,
        model_id=None: _mock_contexts())
    monkeypatch.setattr(
        agent_indexer,
        "build_index_for_project",
        lambda project_id,
        db=None,
        model_id=None: 2,
    )
    monkeypatch.setattr(report_agent, "_call_llm", _bad_llm)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post(
            "/api/agents/analyze",
            json={"project_id": 123, "analyze_types": ["reliability"], "top_k": 3},
        )
    finally:
        app.dependency_overrides.clear()

    assert calls["count"] == 2
    assert response.status_code == 500
    assert response.json()["detail"] == "AI 模型返回了无效的 JSON"
