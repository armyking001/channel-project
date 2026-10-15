import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents import report_agent
from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import (
    AgentAnalyzeRequest,
    AgentAnalyzeResponse,
    AgentQueryRequest,
    AgentQueryResponse,
)
from app.services import agent_indexer

router = APIRouter(prefix="/api/agents", tags=["AI Agent"])
log = logging.getLogger("agents")


@router.post("/analyze", response_model=AgentAnalyzeResponse)
def analyze_project(
    data: AgentAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = report_agent.load_project_or_403(data.project_id, db, current_user)
    contexts = agent_indexer.get_context_for_project(
        project.id, top_k=data.top_k, db=db, model_id=data.model_id,
    )
    if not contexts:
        log.info("项目 %s 尚未建立索引，开始自动构建", project.id)
        agent_indexer.build_index_for_project(project.id, db=db, model_id=data.model_id)
        contexts = agent_indexer.get_context_for_project(
            project.id, top_k=data.top_k, db=db, model_id=data.model_id,
        )
    return report_agent.analyze(
        project_id=project.id,
        contexts=contexts,
        analyze_types=data.analyze_types,
        model_id=data.model_id,
        db=db,
        current_user=current_user,
        query=data.query,
    )


@router.post("/query", response_model=AgentQueryResponse)
def query_project_agent(
    data: AgentQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = report_agent.load_project_or_403(data.project_id, db, current_user)
    contexts = agent_indexer.get_context_for_project(
        project.id,
        top_k=data.top_k,
        db=db,
        query_text=data.question,
        model_id=data.model_id,
    )
    if not contexts:
        log.info("项目 %s 尚未建立索引，开始自动构建", project.id)
        agent_indexer.build_index_for_project(project.id, db=db, model_id=data.model_id)
        contexts = agent_indexer.get_context_for_project(
            project.id,
            top_k=data.top_k,
            db=db,
            query_text=data.question,
            model_id=data.model_id,
        )
    return report_agent.query(
        project_id=project.id,
        question=data.question,
        contexts=contexts,
        model_id=data.model_id,
        db=db,
        current_user=current_user,
    )
