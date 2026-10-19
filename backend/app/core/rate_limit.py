"""
app/core/rate_limit.py — 进程内滑动窗口限流

用途：防止单个账号把 LLM 配额刷爆（尤其公开部署时）。
进程内实现，多 worker 下各自独立计数——对「防误操作」够用；
需要严格全局限流时把 hits 换成 Redis 计数即可。
"""
from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, window_seconds: int = 60):
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int) -> tuple[bool, int]:
        """
        返回 (是否放行, 需等待秒数)。
        limit <= 0 表示不限流。
        """
        if limit <= 0:
            return True, 0

        now = time.monotonic()
        q = self._hits[key]
        # 丢掉窗口外的记录
        while q and now - q[0] > self.window:
            q.popleft()

        if len(q) >= limit:
            wait = int(self.window - (now - q[0])) + 1
            return False, max(wait, 1)

        q.append(now)
        return True, 0

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._hits.clear()
        else:
            self._hits.pop(key, None)


# 两个场景各一个实例
review_limiter = SlidingWindowLimiter(window_seconds=60)
chat_limiter = SlidingWindowLimiter(window_seconds=60)
