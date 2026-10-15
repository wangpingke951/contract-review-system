"""快速 seed 脚本：建 admin + user + 9 个风险类别"""
import sys, asyncio
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), ".."))

from app.core.database import Base, engine
from app.core.security import hash_password, UserRole
from app.models.user import User
from app.models.category import RiskCategory
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

async def main():
    async with AsyncSession(engine) as session:
        cnt = (await session.execute(select(func.count(User.id)))).scalar()
        print(f"当前 users 数: {cnt}")
        if cnt == 0:
            session.add_all([
                User(username="admin", hashed_password=hash_password("admin123"), role=UserRole.ADMIN),
                User(username="user",  hashed_password=hash_password("user123"),  role=UserRole.USER),
            ])
            await session.commit()
            print("✅ 已创建 admin/admin123 + user/user123")

        cats = ["条款缺失","金额异常","期限风险","主体资格","违约责任","知识产权","保密条款","不可抗力","争议解决"]
        existing = (await session.execute(select(RiskCategory.name))).scalars().all()
        for n in cats:
            if n not in existing:
                session.add(RiskCategory(name=n))
        await session.commit()
        print(f"✅ 风险类别数: {len(cats)}")
    await engine.dispose()

asyncio.run(main())
