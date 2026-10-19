"""app/celery_tasks/tasks.py — Celery 任务定义"""
from __future__ import annotations

import asyncio

from app.celery_tasks.app import celery_app


@celery_app.task(name="review.execute", bind=True, max_retries=0)
def execute_review_task(self, review_id: int, contract_id: int) -> dict:
    """
    执行一次合同审查。

    复用 review_service.execute_review —— 它自带状态机：
    成功置 done、超时/异常置 failed 并写 error_message。
    """
    from app.services.review_service import execute_review

    asyncio.run(execute_review(review_id, contract_id))
    return {"review_id": review_id, "contract_id": contract_id}
