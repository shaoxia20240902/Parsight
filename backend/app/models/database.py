from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    # Import model modules before create_all so SQLAlchemy metadata includes
    # feature tables that are not referenced by startup code directly.
    from app.models import builder_session, business_knowledge, user_preference  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_db()


async def migrate_db():
    """为已有数据库补充新增列。"""
    migrations = [
        ("sheet_meta", "understanding_content", "TEXT"),
        ("sheet_meta", "understanding_updated_at", "DATETIME"),
        ("sheet_meta", "understanding_verification_status", "TEXT"),
        ("sheet_meta", "understanding_content_initial", "TEXT"),
        ("spaces", "relations_content_initial", "TEXT"),
        ("spaces", "relations_content", "TEXT"),
        ("spaces", "relations_verification_status", "TEXT"),
        ("spaces", "relations_updated_at", "DATETIME"),
        ("spaces", "seq_id", "INTEGER"),
        ("file_records", "bi_thinking_journal", "JSON"),
        ("chat_history", "mode", "TEXT"),
        ("chat_history", "session_id", "VARCHAR(36)"),
    ]
    async with engine.begin() as conn:
        for table, column, col_type in migrations:
            result = await conn.execute(
                text("""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = :table
                """),
                {"table": table},
            )
            existing = {row[0] for row in result.fetchall()}
            if column not in existing:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                )

        # 为已有空间回填 seq_id（按创建时间递增）
        result = await conn.execute(
            text("SELECT id FROM spaces WHERE seq_id IS NULL ORDER BY created_at ASC")
        )
        rows = result.fetchall()
        if rows:
            max_result = await conn.execute(text("SELECT COALESCE(MAX(seq_id), 0) FROM spaces"))
            next_seq = (max_result.scalar() or 0) + 1
            for (space_id,) in rows:
                await conn.execute(
                    text("UPDATE spaces SET seq_id = :seq WHERE id = :id"),
                    {"seq": next_seq, "id": space_id},
                )
                next_seq += 1
