import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload


def _backend_dir() -> str:
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


BACKEND_DIR = _backend_dir()
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models import AIModelConfig, FormInstance, Project

log = logging.getLogger("agent_indexer")

COLLECTION_NAME = "project_agent_chunks"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
LOCAL_EMBEDDING_MODEL = "all-mpnet-base-v2"
DEFAULT_TOP_K = 5
RETRY_ATTEMPTS = 2


def _load_yaml_config() -> dict:
    backend_dir = _backend_dir()
    config_path = os.path.join(backend_dir, "config.yaml")
    if not os.path.exists(config_path):
        return {}
    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        log.exception("读取 config.yaml 失败")
        return {}


@lru_cache(maxsize=1)
def _get_chroma_dir() -> str:
    config = _load_yaml_config()
    raw = (
        os.getenv("CHROMA_DIR")
        or config.get("CHROMA_DIR")
        or config.get("agent", {}).get("CHROMA_DIR")
        or config.get("agent", {}).get("chroma_dir")
        or os.path.join(_backend_dir(), "chroma_store")
    )
    path = os.path.abspath(raw)
    os.makedirs(path, exist_ok=True)
    return path


def _get_default_top_k() -> int:
    try:
        return max(1, int(os.getenv("AGENT_DEFAULT_TOP_K", DEFAULT_TOP_K)))
    except Exception:
        return DEFAULT_TOP_K


def _with_retry(func, description: str):
    last_error = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            log.warning("%s 失败，第 %s/%s 次重试：%s", description, attempt, RETRY_ATTEMPTS, exc)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(0.5)
    raise last_error


def _load_chromadb():
    try:
        import chromadb

        return chromadb
    except Exception as exc:
        raise RuntimeError("缺少 chromadb 依赖，请先安装 backend/requirements.txt") from exc


@lru_cache(maxsize=1)
def _get_local_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(LOCAL_EMBEDDING_MODEL)
    except Exception as exc:
        raise RuntimeError("缺少 sentence-transformers 依赖，无法使用本地 embedding") from exc


def _resolve_default_ai_model(db: Session) -> Optional[AIModelConfig]:
    return (
        db.query(AIModelConfig)
        .filter(AIModelConfig.is_enabled.is_(True))
        .order_by(AIModelConfig.is_default.desc(), AIModelConfig.id.asc())
        .first()
    )


def _resolve_embedding_model(db: Session, model_id: Optional[int] = None) -> Optional[AIModelConfig]:
    query = db.query(AIModelConfig).filter(AIModelConfig.is_enabled.is_(True))
    if model_id is not None:
        requested = query.filter(AIModelConfig.id == model_id).first()
        if requested:
            return requested
    return _resolve_default_ai_model(db)


def _get_embedding_provider(
    db: Session,
    model: Optional[AIModelConfig] = None,
    model_id: Optional[int] = None,
) -> str:
    provider = (os.getenv("AGENT_EMBEDDING_PROVIDER") or "auto").strip().lower()
    if provider in {"openai", "local"}:
        return provider
    chosen_model = model or _resolve_embedding_model(db, model_id)
    if chosen_model and chosen_model.provider == "openai_compatible" and chosen_model.api_key:
        return "openai"
    return "local"


def _build_openai_client(model: Optional[AIModelConfig]):
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("缺少 openai 依赖，无法使用 OpenAI embedding/LLM") from exc

    base_url = os.getenv("OPENAI_BASE_URL") or (model.base_url if model and model.base_url else None)
    api_key = os.getenv("OPENAI_API_KEY") or (model.api_key if model and model.api_key else None)
    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY，且数据库模型配置中也没有 api_key")
    timeout = float(model.timeout_seconds if model and model.timeout_seconds else 30)
    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)


def _embed_texts_via_openai(texts: List[str], db: Session, model: Optional[AIModelConfig] = None) -> List[List[float]]:
    chosen_model = model or _resolve_default_ai_model(db)
    client = _build_openai_client(chosen_model)
    embedding_model = os.getenv("AGENT_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL

    def _call():
        response = client.embeddings.create(model=embedding_model, input=texts)
        return [item.embedding for item in response.data]

    return _with_retry(_call, "OpenAI embedding 调用")


def _embed_texts_via_local(texts: List[str]) -> List[List[float]]:
    model = _get_local_embedding_model()

    def _call():
        vectors = model.encode(texts, normalize_embeddings=True)
        return [list(item) for item in vectors]

    return _with_retry(_call, "本地 embedding 计算")


def _embed_texts(
    texts: List[str],
    db: Session,
    model: Optional[AIModelConfig] = None,
    model_id: Optional[int] = None,
) -> List[List[float]]:
    chosen_model = model or _resolve_embedding_model(db, model_id)
    provider = _get_embedding_provider(db, chosen_model, model_id)
    if provider == "openai":
        try:
            return _embed_texts_via_openai(texts, db, chosen_model)
        except Exception:
            log.warning("OpenAI embedding 失败，自动回退到本地 sentence-transformers")
    return _embed_texts_via_local(texts)


@lru_cache(maxsize=1)
def _get_chroma_client():
    chromadb = _load_chromadb()

    def _create():
        return chromadb.PersistentClient(path=_get_chroma_dir())

    return _with_retry(_create, "Chroma 客户端初始化")


def _get_collection():
    client = _get_chroma_client()

    def _create():
        return client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    return _with_retry(_create, "Chroma collection 初始化")


def _split_text(text: str, max_length: int = 320) -> List[str]:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return []
    sentences = [item.strip() for item in re.split(r"[。！？；\n\r]+", clean) if item.strip()]
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
            continue
        if len(current) + len(sentence) + 1 <= max_length:
            current = f"{current}。{sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks or [clean[:max_length]]


def _safe_json_loads(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _enum_str(value) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _project_brief(project: Project) -> str:
    fields = [
        f"项目名称：{project.project_name}",
        f"项目编号：{project.project_code or '未填写'}",
        f"项目类型：{project.project_type.value if hasattr(project.project_type, 'value') else project.project_type}",
        f"项目来源：{'自营项目' if project.source == 'self' else '渠道项目'}",
        f"责任销售：{project.responsible_sales or '未填写'}",
        f"合作公司：{project.partner_company or '未填写'}",
        f"项目金额：{float(project.project_amount or 0):.2f}",
        f"预计金额：{float(project.expected_amount or 0):.2f}",
        f"费用金额：{float(project.fee_amount or 0):.2f}",
        f"审批状态：{_enum_str(project.approval_status)}",
        f"中标状态：{_enum_str(project.win_bid_status)}",
        f"招标日期：{project.tender_time.isoformat() if project.tender_time else '未填写'}",
        f"投标日期：{project.bid_time.isoformat() if project.bid_time else '未填写'}",
        f"项目概述：{project.project_overview or '未填写'}",
        f"招标文件：{project.tender_file or project.tender_folder or '未上传'}",
        f"投标文件：{project.bid_file or project.bid_folder or '未上传'}",
    ]
    return "\n".join(fields)


def _build_documents(project: Project, form_instance: Optional[FormInstance]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    project_created_at = project.created_at.isoformat() if project.created_at else datetime.utcnow().isoformat()

    docs.append(
        {
            "id": f"project-{project.id}-summary",
            "text": _project_brief(project),
            "metadata": {
                "project_id": project.id,
                "source_type": "form_field",
                "source_id": project.id,
                "field_name": "project_summary",
                "created_at": project_created_at,
            },
        }
    )

    field_items = [
        ("project_name", "项目名称", project.project_name),
        ("project_code", "项目编号", project.project_code),
        ("project_type", "项目类型", project.project_type.value if hasattr(
            project.project_type, "value") else project.project_type),
        ("responsible_sales", "责任销售", project.responsible_sales),
        ("partner_company", "合作公司", project.partner_company),
        ("project_amount", "项目金额", project.project_amount),
        ("expected_amount", "预计金额", project.expected_amount),
        ("fee_amount", "费用金额", project.fee_amount),
        ("project_overview", "项目概述", project.project_overview),
    ]
    for field_name, field_label, value in field_items:
        if value in (None, ""):
            continue
        docs.append(
            {
                "id": f"project-{project.id}-{field_name}",
                "text": f"{field_label}：{value}",
                "metadata": {
                    "project_id": project.id,
                    "source_type": "form_field",
                    "source_id": project.id,
                    "field_name": field_name,
                    "created_at": project_created_at,
                },
            }
        )

    file_items = [
        ("tender_file", "招标资料", project.tender_file or project.tender_folder),
        ("bid_file", "投标文件", project.bid_file or project.bid_folder),
    ]
    for field_name, field_label, value in file_items:
        if not value:
            continue
        docs.append(
            {
                "id": f"project-{project.id}-{field_name}",
                "text": f"{field_label}位置：{value}",
                "metadata": {
                    "project_id": project.id,
                    "source_type": "file",
                    "source_id": project.id,
                    "field_name": field_name,
                    "created_at": project_created_at,
                },
            }
        )

    if form_instance:
        data = _safe_json_loads(form_instance.data)
        for key, value in data.items():
            if value in (None, "", [], {}):
                continue
            text = f"表单字段 {key}：{value}"
            created_at = (
                form_instance.created_at.isoformat()
                if form_instance.created_at
                else project_created_at
            )
            docs.append({
                "id": f"form-{form_instance.id}-{key}",
                "text": text,
                "metadata": {
                    "project_id": project.id,
                    "source_type": "form_field",
                    "source_id": form_instance.id,
                    "field_name": str(key),
                    "created_at": created_at,
                },
            })

    for followup in sorted(project.followups, key=lambda item: item.created_at or datetime.min):
        parts = [
            f"跟单阶段：{followup.stage.value if hasattr(followup.stage, 'value') else followup.stage}",
            f"当前进展：{followup.progress or '未填写'}",
            f"风险与支持：{followup.risks or '未填写'}",
            f"下一步计划：{followup.next_plan or '未填写'}",
            f"责任人：{followup.next_owner or '未填写'}",
            f"预计金额：{float(followup.expected_amount or 0):.2f}",
            f"预计签单日期：{followup.expected_sign_date.isoformat() if followup.expected_sign_date else '未填写'}",
        ]
        followup_text = "\n".join(parts)
        for index, chunk in enumerate(_split_text(followup_text)):
            docs.append(
                {
                    "id": f"followup-{followup.id}-{index}",
                    "text": chunk,
                    "metadata": {
                        "project_id": project.id,
                        "source_type": "followup",
                        "source_id": followup.id,
                        "field_name": "followup",
                        "created_at": followup.created_at.isoformat() if followup.created_at else project_created_at,
                    },
                }
            )
    return docs


def _load_project_bundle(db: Session, project_id: int):
    project = (
        db.query(Project)
        .options(joinedload(Project.followups))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise ValueError(f"项目 {project_id} 不存在")
    form_instance = None
    if project.form_instance_id:
        form_instance = db.query(FormInstance).filter(FormInstance.id == project.form_instance_id).first()
    return project, form_instance


def build_index_for_project(
    project_id: int,
    db: Optional[Session] = None,
    model_id: Optional[int] = None,
) -> int:
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True
    try:
        project, form_instance = _load_project_bundle(db, project_id)
        docs = _build_documents(project, form_instance)
        collection = _get_collection()
        delete_project_index(project_id)
        embeddings = _embed_texts(
            [item["text"] for item in docs], db, model_id=model_id,
        )

        def _add():
            collection.add(
                ids=[item["id"] for item in docs],
                documents=[item["text"] for item in docs],
                metadatas=[item["metadata"] for item in docs],
                embeddings=embeddings,
            )

        _with_retry(_add, "Chroma 写入索引")
        log.info("项目 %s 索引完成，共 %s 条文档", project_id, len(docs))
        return len(docs)
    finally:
        if own_db:
            db.close()


def delete_project_index(project_id: int) -> None:
    collection = _get_collection()

    def _delete():
        collection.delete(where={"project_id": project_id})

    _with_retry(_delete, "Chroma 删除索引")


def get_context_for_project(
    project_id: int,
    top_k: Optional[int] = None,
    db: Optional[Session] = None,
    query_text: Optional[str] = None,
    model_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True
    try:
        collection = _get_collection()
        top_k = max(1, top_k or _get_default_top_k())
        query_payload = query_text
        if not query_payload:
            project, _ = _load_project_bundle(db, project_id)
            query_payload = _project_brief(project)
        query_embeddings = _embed_texts(
            [query_payload], db, model_id=model_id,
        )

        def _query():
            return collection.query(
                query_embeddings=query_embeddings,
                n_results=top_k,
                where={"project_id": project_id},
                include=["documents", "metadatas", "distances"],
            )

        result = _with_retry(_query, "Chroma 查询上下文")
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        contexts: List[Dict[str, Any]] = []
        for index, doc in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            contexts.append(
                {
                    "source": f"SOURCE_{index + 1}",
                    "text": doc,
                    "score": None if distance is None else max(0.0, 1 - float(distance)),
                    "source_type": metadata.get("source_type") or "form_field",
                    "source_id": metadata.get("source_id"),
                    "field_name": metadata.get("field_name"),
                    "created_at": metadata.get("created_at"),
                }
            )
        return contexts
    finally:
        if own_db:
            db.close()


def _cli() -> None:
    parser = argparse.ArgumentParser(description="项目 Agent 索引工具")
    parser.add_argument("--build", type=int, help="为指定 project_id 构建索引")
    parser.add_argument("--delete", type=int, help="删除指定 project_id 的索引")
    parser.add_argument("--get", type=int, help="获取指定 project_id 的上下文")
    parser.add_argument("--top-k", type=int, default=_get_default_top_k(), help="返回的上下文数量")
    parser.add_argument("--query", type=str, default=None, help="用于检索的查询问题")
    args = parser.parse_args()

    if not any([args.build, args.delete, args.get]):
        parser.error("请传入 --build / --delete / --get 之一")

    if args.build:
        count = build_index_for_project(args.build)
        print(json.dumps({"project_id": args.build, "indexed": count}, ensure_ascii=False))
        return
    if args.delete:
        delete_project_index(args.delete)
        print(json.dumps({"project_id": args.delete, "deleted": True}, ensure_ascii=False))
        return
    if args.get:
        contexts = get_context_for_project(args.get, top_k=args.top_k, query_text=args.query)
        print(json.dumps({"project_id": args.get, "contexts": contexts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
