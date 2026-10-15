# -*- coding: utf-8 -*-
"""
财务催收定时调度器（后台轮询）

每 TICK_SECONDS 秒扫一次 FinanceReceivable / FinanceTrust 表中
"remind_start_at + frequency" 已配置且在提醒窗口内的记录，到点就调用
send_sms_for_record 触发催收。

设计要点：
- 不用 APScheduler，避免新依赖；用 FastAPI lifespan 起一个 asyncio 任务
  跑循环，每 tick 的工作放到线程里执行（send_sms_for_record 是同步 + 网络 IO，
  不能阻塞事件循环）。
- 用独立的 `last_fired_at` 字段做"同一边界已发"门控，不复用
  `last_reminder_at`（后者只在真正发成功时被写入，用于用户展示；调度器
  即使发送失败也要写门控，避免 30s 重试死循环）。
- 频率语义：once=到点发一次；daily/weekly/monthly=按 start 的时分 + 匹配日
  重复发；remind_end_at 之后停止；end_at 为空则一直按频率发。
- 调度器的"到期"判断使用本地时间 datetime.now()，与前端录入 remind_start_at
  时的语义一致；send_sms_for_record 内部的 remind_end_at 校验仍用 utcnow()
  （保持原行为，不在本次改动）。
"""
import asyncio
import calendar as _cal
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from app.database import SessionLocal
from app.models import FinanceReceivable, FinanceTrust
from app.services.finance_excel import send_sms_for_record

log = logging.getLogger("reminder_scheduler")

TICK_SECONDS = 30
# 调度发送默认走 sms_custom 通道（finance_excel 中唯一真实实现的短信通道）
SCHED_CHANNELS = ["sms_custom"]
VALID_FREQ = {"once", "daily", "weekly", "monthly"}


def _naive(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


def _last_day_of_month(year: int, month: int) -> int:
    return _cal.monthrange(year, month)[1]


def _compute_next_boundary(rec, now: datetime) -> Optional[datetime]:
    """返回当前时刻下"本应已触发"的那个边界时刻（<= now 且在窗口内），
    若还未到下一次边界则返回 None。
    """
    start = _naive(rec.remind_start_at)
    if start is None:
        return None
    freq = (rec.frequency or "once").lower()
    if freq not in VALID_FREQ:
        return None
    end = _naive(rec.remind_end_at)

    # 已超过结束时间 -> 不再发
    if end is not None and now > end:
        return None

    if freq == "once":
        return start if now >= start else None

    # 周期型：计算最近一次"匹配日 + 时分"且 >= start 的边界
    tod = start.time()
    if freq == "daily":
        cand = datetime.combine(now.date(), tod)
    elif freq == "weekly":
        wd = start.weekday()
        delta_days = (now.weekday() - wd) % 7
        target_date = now.date() - timedelta(days=delta_days)
        cand = datetime.combine(target_date, tod)
    elif freq == "monthly":
        day = min(start.day, _last_day_of_month(now.year, now.month))
        cand = datetime.combine(date(now.year, now.month, day), tod)
    else:
        return None

    if cand < start:        # 首次触发日还没到
        return None
    if cand > now:          # 今天的时-分 还没到
        return None
    return cand


def _is_due(rec, now: datetime) -> Optional[datetime]:
    """返回该记录本 tick 是否到期；若到期则同时返回边界时刻（用于写门控）。"""
    boundary = _compute_next_boundary(rec, now)
    if boundary is None:
        return None
    last = _naive(getattr(rec, "last_fired_at", None))
    if last is not None and last >= boundary:
        return None
    return boundary


def _scan_one_table(db, model, record_type: str, now: datetime):
    """扫描一张表，挑出到期的记录并触发发送。返回触发条数。"""
    rows = (
        db.query(model)
        .filter(model.remind_start_at.isnot(None))
        .filter(model.frequency.in_(list(VALID_FREQ)))
        .all()
    )
    fired = 0
    for rec in rows:
        try:
            boundary = _is_due(rec, now)
            if boundary is None:
                continue
            # 先关门控再发，避免失败时的 30s 死循环；并 commit 一次
            rec.last_fired_at = boundary
            db.commit()
            try:
                send_sms_for_record(
                    db,
                    record_type,
                    rec,
                    rec.frequency or "once",
                    operator=None,
                    channels=SCHED_CHANNELS,
                    custom_template=None,
                )
            except Exception as e:
                log.warning(
                    "[reminder] 发送异常 record_id=%s type=%s err=%s",
                    getattr(rec, "id", "?"), record_type, e,
                )
            fired += 1
        except Exception as e:
            log.warning("[reminder] 处理单条异常: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
    return fired


def _tick():
    """单次扫描+触发；放到线程里跑。"""
    now = datetime.now()
    db = SessionLocal()
    try:
        n1 = _scan_one_table(db, FinanceReceivable, "receivables", now)
        n2 = _scan_one_table(db, FinanceTrust, "trust", now)
        if n1 or n2:
            log.info("[reminder] tick fired receivables=%d trust=%d", n1, n2)
    except Exception as e:
        log.warning("[reminder] tick 异常: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass


async def reminder_loop():
    """调度主循环：每 TICK_SECONDS 触发一次 _tick（在线程里执行，不阻塞事件循环）。"""
    log.info("[reminder] 调度器已启动 tick=%ds", TICK_SECONDS)
    while True:
        try:
            await asyncio.to_thread(_tick)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("[reminder] loop 异常: %s", e)
        try:
            await asyncio.sleep(TICK_SECONDS)
        except asyncio.CancelledError:
            raise


def start_reminder_scheduler() -> asyncio.Task:
    """在 FastAPI 启动时调用，返回后台 asyncio.Task。"""
    return asyncio.create_task(reminder_loop())


async def stop_reminder_scheduler(task: Optional[asyncio.Task]):
    """在 FastAPI 关闭时调用，安全取消任务。"""
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    log.info("[reminder] 调度器已停止")
