"""
backend/app/main.py — FastAPI 入口

Phase 2 交付物：
- FastAPI app 创建 + CORS 中间件 + 请求日志
- 全局异常处理器注册
- /api/health 健康检查端点
- /api/auth/* 占位路由（登录/注册/me）
- 启动时自动建表（从 models 导入各 ORM，然后 Base.metadata.create_all）

⚠️ 关键：models 导入是"为了触发各 model 文件的类定义被执行"，
但 models/__init__.py 只导出 Base，所以这里显式 import 每个 model 文件，
否则 Base.metadata 里没有任何表定义，create_all() 会是空操作。
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core.database import Base, engine
from app.core.exceptions import register_exception_handlers

settings = get_settings()
logger = logging.getLogger("app")

# 前端构建产物目录（SERVE_FRONTEND=true 时挂载）：backend/app/main.py → 项目根/frontend/dist
_SPA_DIST: Path | None = None


# ——— 导入所有 ORM model（注册到 Base.metadata）———
# 每个 import 必须在独立文件里，且 models/__init__.py 不聚合导入
import app.models.user          # noqa: F401
import app.models.contract      # noqa: F401
import app.models.review        # noqa: F401
import app.models.conversation  # noqa: F401
import app.models.category      # noqa: F401
import app.models.assistant     # noqa: F401
import app.models.audit         # noqa: F401
import app.models.template      # noqa: F401
import app.models.usage         # noqa: F401


# ——— lifespan（启动/关闭钩子）———
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    启动时：建表 + seed 默认 admin/user + 默认风险类别
    关闭时：关闭数据库连接池
    """
    # 启动
    logger.info("🚀 启动 FastAPI app ...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ 数据库表创建完成（或已存在）")

        # seed 默认数据（admin / user + 9 个默认风险类别）
        from sqlalchemy import select, func
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.security import hash_password, UserRole
        from app.models.user import User
        from app.models.category import RiskCategory

        async with AsyncSession(engine) as session:
            # —— seed users ——
            existing_count = (await session.execute(select(func.count(User.id)))).scalar()
            if existing_count == 0:
                admin = User(
                    username="admin",
                    hashed_password=hash_password("admin123"),
                    role=UserRole.ADMIN,
                )
                user = User(
                    username="user",
                    hashed_password=hash_password("user123"),
                    role=UserRole.USER,
                )
                session.add_all([admin, user])
                await session.commit()
                logger.info("✅ 已创建默认用户: admin/admin123, user/user123")

            # —— seed 默认风险类别 ——
            default_categories = [
                "条款缺失", "金额异常", "期限风险", "主体资格",
                "违约责任", "知识产权", "保密条款", "不可抗力", "争议解决",
            ]
            existing_cats = (await session.execute(select(RiskCategory.name))).scalars().all()
            for name in default_categories:
                if name not in existing_cats:
                    session.add(RiskCategory(name=name))
            if any(name not in existing_cats for name in default_categories):
                await session.commit()
                logger.info("✅ 已创建默认风险类别")

        # —— seed 默认审查模板 ——
        from app.services import template_service
        async with AsyncSession(engine) as session:
            await template_service.ensure_default_template(session)
            logger.info("✅ 审查模板已就绪")

        # —— 清理孤儿任务：进程重启后，内存里的后台任务已消失，
        #    DB 里残留的 RUNNING 会永远卡住，启动时统一标记失败 ——
        from sqlalchemy import update
        from app.models.review import Review as _Review, ReviewStatus as _RS
        from app.models.contract import Contract as _Contract, ContractStatus as _CS
        async with AsyncSession(engine) as session:
            res = await session.execute(
                update(_Review)
                .where(_Review.status == _RS.RUNNING)
                .values(
                    status=_RS.FAILED,
                    error_message="服务重启，后台任务已中断，请重新发起审查",
                )
            )
            cnt = res.rowcount or 0
            await session.execute(
                update(_Contract)
                .where(_Contract.status == _CS.REVIEWING)
                .values(status=_CS.PARSED)
            )
            await session.commit()
            if cnt:
                logger.info(f"🧹 清理了 {cnt} 条中断的审查任务")

    except Exception as e:
        logger.warning(f"⚠️ 启动初始化失败: {e}")

    yield

    # 关闭
    await engine.dispose()
    logger.info("👋 FastAPI app 关闭，数据库连接池已释放")


# ——— FastAPI app 实例 ———
app = FastAPI(
    title="合同智能审查系统 API",
    version="1.0.0",
    description="MVP：RAG + 多模态解析 + 对话追问的一体化合同审查平台",
    lifespan=lifespan,
)


# ——— CORS 中间件（Vite dev server + 生产 Nginx）———
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # Vite dev
        "http://127.0.0.1:5173",
        "http://localhost:80",        # 生产 Nginx
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ——— 全局异常处理器 ———
register_exception_handlers(app)


# ——— 请求日志（DEBUG 模式）———
@app.middleware("http")
async def request_logging(request: Request, call_next):
    if settings.DEBUG:
        logger.debug(f"📥 {request.method} {request.url.path}")
    response = await call_next(request)
    if settings.DEBUG:
        logger.debug(f"📤 {response.status_code} {request.url.path}")
    return response


# ——— 路由注册 ———
# Phase 2 有 auth；Phase 4 补 contracts；Phase 6 补 reviews；Phase 7 补 chat；Phase 8 补 admin
from app.routers import auth as auth_router               # noqa: E402
from app.routers import contracts as contracts_router     # noqa: E402
from app.routers import reviews as reviews_router         # noqa: E402
from app.routers import chat as chat_router               # noqa: E402
from app.routers import admin as admin_router             # noqa: E402
from app.routers import assistant as assistant_router     # noqa: E402
from app.routers import templates as templates_router     # noqa: E402
from app.routers import tasks as tasks_router             # noqa: E402

app.include_router(auth_router.router,       prefix="/api/auth",      tags=["认证"])
app.include_router(contracts_router.router,  prefix="/api/contracts", tags=["合同"])
app.include_router(reviews_router.router,    prefix="/api/reviews",   tags=["审查"])
app.include_router(chat_router.router,       prefix="/api/chat",      tags=["对话"])
app.include_router(admin_router.router,      prefix="/api/admin",     tags=["管理后台"])
app.include_router(assistant_router.router,  prefix="/api/assistant", tags=["法律问答"])
app.include_router(templates_router.router,  prefix="/api/templates", tags=["审查模板"])
app.include_router(tasks_router.router,      prefix="/api/tasks",     tags=["任务中心"])
app.include_router(chat_router.ws_router,                             tags=["对话WebSocket"])
app.include_router(assistant_router.ws_router,                        tags=["法律问答WebSocket"])


# ——— 健康检查 ———
@app.get("/api/health")
async def health():
    """最基础的健康检查"""
    return {
        "code": 0,
        "data": {
            "status": "ok",
            "version": "1.0.0",
            "database": settings.mysql_dsn.split("@")[-1].split("/")[0],  # 只显示 host:port
        },
        "message": "",
    }


# ——— 简单测试端点（未托管前端时返回服务信息）———
@app.get("/")
async def root():
    if _SPA_DIST is not None:
        return FileResponse(_SPA_DIST / "index.html")
    return JSONResponse({
        "code": 0,
        "data": {"service": "contract-review-api", "version": "1.0.0"},
        "message": "合同智能审查系统 API 运行中，访问 /api/health 检查状态",
    })


# ——— 可选：由 FastAPI 托管前端构建产物 ———
# 用途：内网穿透只映射 8000 一个端口 / 单机交付，不需要再起 vite 或 nginx。
# 开启：backend/.env 设 SERVE_FRONTEND=true，并先执行 cd frontend && npm run build
if settings.SERVE_FRONTEND:
    _candidate = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if (_candidate / "index.html").is_file():
        _SPA_DIST = _candidate
        _assets_dir = _candidate / "assets"
        if _assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            """SPA 兜底：静态文件优先，其余路径交给前端路由"""
            # API / WebSocket 前缀不接管，避免把 404 伪装成页面
            if full_path.startswith(("api/", "ws/")):
                return JSONResponse(
                    {"code": 404, "message": "接口不存在", "data": None},
                    status_code=404,
                )
            target = (_candidate / full_path).resolve()
            # 防目录穿越：解析后必须仍在 dist 内
            if str(target).startswith(str(_candidate.resolve())) and target.is_file():
                return FileResponse(target)
            return FileResponse(_candidate / "index.html")

        logger.info(f"🖼  已启用前端静态托管: {_candidate}")
    else:
        logger.warning(
            "SERVE_FRONTEND=true 但未找到 frontend/dist/index.html，请先执行 "
            "`cd frontend && npm run build`；当前仍以纯 API 模式运行"
        )
