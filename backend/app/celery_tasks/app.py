"""
app/celery_tasks/app.py — Celery 应用实例

Docker 部署形态下，审查任务交给独立 worker 执行（REVIEW_EXECUTION_MODE=celery）。
本地开发默认走进程内后台任务，不需要 Redis。
"""
from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "contract_review",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.celery_tasks.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    worker_max_tasks_per_child=50,
)
