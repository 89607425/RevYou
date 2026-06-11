"""Seed script: create default admin user and demo project."""
import asyncio
from sqlalchemy import select
from app.core.database import async_session
from app.core.security import hash_password
from app.models.user import User
from app.models.project import Project, ProjectMember


async def seed():
    async with async_session() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Admin user already exists, skipping seed.")
            return

        # Create admin user
        admin = User(
            user_id="USR-ADMIN-001",
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="管理员",
            email="admin@revyou.com",
            role="ADMIN",
            status="ACTIVE",
        )
        db.add(admin)

        # Create demo PM user
        pm = User(
            user_id="USR-PM-001",
            username="pm",
            password_hash=hash_password("pm123"),
            display_name="产品经理",
            email="pm@revyou.com",
            role="PM",
            status="ACTIVE",
        )
        db.add(pm)

        # Create demo Dev user
        dev = User(
            user_id="USR-DEV-001",
            username="dev",
            password_hash=hash_password("dev123"),
            display_name="开发负责人",
            email="dev@revyou.com",
            role="DEV",
            status="ACTIVE",
        )
        db.add(dev)

        # Create demo QA user
        qa = User(
            user_id="USR-QA-001",
            username="qa",
            password_hash=hash_password("qa123"),
            display_name="测试工程师",
            email="qa@revyou.com",
            role="QA",
            status="ACTIVE",
        )
        db.add(qa)

        await db.flush()

        # Create demo project
        import json
        default_config = {
            "text_model": "deepseek-v3",
            "multimodal_model": "qwen-vl-max",
            "auto_switch_model": True,
            "confidence_threshold_low": 0.5,
            "confidence_threshold_high": 0.8,
            "max_review_rounds_deterministic": 1,
            "max_review_rounds_autonomous": 3,
            "max_follow_up_questions": 5,
            "max_issues_per_agent": 30,
            "session_timeout_deterministic_min": 5,
            "session_timeout_autonomous_min": 10,
        }

        project = Project(
            project_id="PRJ-DEMO-001",
            name="电商平台（演示项目）",
            config=default_config,
            status="ACTIVE",
            created_by="USR-ADMIN-001",
        )
        db.add(project)
        await db.flush()

        # Add members to project
        members = [
            ProjectMember(project_id="PRJ-DEMO-001", user_id="USR-ADMIN-001", role="ADMIN"),
            ProjectMember(project_id="PRJ-DEMO-001", user_id="USR-PM-001", role="PM"),
            ProjectMember(project_id="PRJ-DEMO-001", user_id="USR-DEV-001", role="DEV"),
            ProjectMember(project_id="PRJ-DEMO-001", user_id="USR-QA-001", role="QA"),
        ]
        for m in members:
            db.add(m)

        await db.commit()
        print("Seed completed: admin/admin123, pm/pm123, dev/dev123, qa/qa123")


if __name__ == "__main__":
    asyncio.run(seed())
