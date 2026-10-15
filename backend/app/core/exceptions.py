"""
app/core/exceptions.py — 自定义异常 + 全局异常处理器
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse


# —— 自定义业务异常 ——
class AppError(Exception):
    """统一业务异常基类"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)

class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=404)

class PermissionError(AppError):
    def __init__(self, message: str = "权限不足"):
        super().__init__(message, code=403)

class ValidationError(AppError):
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(message, code=400)


# —— 注册全局异常处理器 ——
def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(AppError)
    async def handle_app_error(request, exc: AppError):
        return JSONResponse(
            status_code=exc.code,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": exc.detail, "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request, exc: RequestValidationError):
        # 把 Pydantic 的 422 改成更清晰的格式
        return JSONResponse(
            status_code=422,
            content={
                "code": 422,
                "message": "请求参数校验失败",
                "data": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request, exc):
        # 兜底：未知异常
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"服务器内部错误: {exc}", "data": None},
        )
