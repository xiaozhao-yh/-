"""初始化数据库：建库、建表、结构迁移、写入种子数据（管理员/演示用户/Prompt模板/AI模型配置）

用法：python init_db.py
幂等可重复执行。
"""
import sys

import pymysql

sys.path.insert(0, ".")

from app.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import AiConfig, PromptTemplate, Resume, User  # noqa: E402
from app.seed_data import DEFAULT_AI_CONFIG, PROMPT_TEMPLATES, SAMPLE_RESUME  # noqa: E402
from app.security import hash_password  # noqa: E402


def migrate_prompt_templates(conn):
    """prompt_templates 结构迁移：补 scene/status 列"""
    with conn.cursor() as cur:
        cur.execute(f"SHOW COLUMNS FROM {DB_NAME}.prompt_templates")
        cols = {row[0] for row in cur.fetchall()}
        if "scene" not in cols:
            cur.execute(
                f"ALTER TABLE {DB_NAME}.prompt_templates "
                "ADD COLUMN scene VARCHAR(20) NOT NULL DEFAULT 'score', "
                "ADD INDEX ix_prompt_templates_scene (scene)"
            )
            print("  - 已迁移：prompt_templates 增加 scene 列")
        if "status" not in cols:
            cur.execute(
                f"ALTER TABLE {DB_NAME}.prompt_templates "
                "ADD COLUMN status TINYINT(1) NOT NULL DEFAULT 1"
            )
            print("  - 已迁移：prompt_templates 增加 status 列")


def main():
    # 1. 建库
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, charset="utf8mb4")
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS {DB_NAME} "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        print(f"[1/5] 数据库 {DB_NAME} 就绪")
    finally:
        conn.close()

    # 2. 建表
    Base.metadata.create_all(engine)
    print("[2/5] 数据表创建完成")

    # 3. 结构迁移（prompt_templates: scene/status）
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
                           database=DB_NAME, charset="utf8mb4")
    try:
        migrate_prompt_templates(conn)
        conn.commit()
        print("[3/5] 结构迁移完成")
    finally:
        conn.close()

    # 4. 种子数据
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(username="admin", password_hash=hash_password("123456"),
                        nickname="系统管理员", role="admin"))
            print("  - 已创建管理员 admin / 123456")
        demo = db.query(User).filter(User.username == "demo").first()
        if not demo:
            demo = User(username="demo", password_hash=hash_password("123456"),
                        nickname="演示用户", role="user")
            db.add(demo)
            db.flush()
            db.add(Resume(user_id=demo.id, title="张三-后端开发简历", target_position="Python后端开发工程师",
                          job_desc="熟悉 Python/Flask/FastAPI，熟悉 MySQL、Redis，了解消息队列与分布式基础",
                          original_text=SAMPLE_RESUME, current_text=SAMPLE_RESUME, file_name=""))
            print("  - 已创建演示用户 demo / 123456（含示例简历）")

        # Prompt 模板：删除旧版小写编码模板，按 code upsert 新版模板
        old_codes = ["score", "analysis", "suggestion", "rewrite", "interview"]
        n = db.query(PromptTemplate).filter(PromptTemplate.code.in_(old_codes)).delete(synchronize_session=False)
        if n:
            print(f"  - 已清理旧版小写编码模板 {n} 个")
        for t in PROMPT_TEMPLATES:
            row = db.query(PromptTemplate).filter(PromptTemplate.code == t["code"]).first()
            if row is None:
                db.add(PromptTemplate(code=t["code"], name=t["name"], scene=t["scene"], content=t["content"]))
                print(f"  - 已写入模板 {t['code']}")
            else:
                row.name, row.scene, row.content = t["name"], t["scene"], t["content"]
                print(f"  - 已更新模板 {t['code']}")

        if db.query(AiConfig).count() == 0:
            db.add(AiConfig(**DEFAULT_AI_CONFIG))
            print("  - 已写入默认 AI 模型配置（qwen-plus，已启用）")
        db.commit()
        print("[4/5] 种子数据写入完成")
    finally:
        db.close()

    print("[5/5] 初始化完成！启动后端：python run.py")


if __name__ == "__main__":
    main()
