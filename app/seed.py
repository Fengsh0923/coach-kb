"""One-shot seed script: load /app/content/*.md → DB + embeddings.

Usage: docker exec coach-kb-backend python seed.py
"""
import asyncio
import sys
from pathlib import Path
import frontmatter

sys.path.insert(0, str(Path(__file__).parent))
from lib import db, llm

CONTENT_DIR = Path(__file__).parent / "content"


async def main():
    db.init_schema()
    files = sorted(CONTENT_DIR.glob("competency_*.md"))
    if not files:
        print("⚠️  no markdown files found in", CONTENT_DIR)
        return
    print(f"loading {len(files)} files…")

    with db.connect() as conn:
        # 1. Upsert source row (ICF official)
        src = conn.execute(
            "INSERT INTO source (type, title, author, url, license) VALUES "
            "('icf_official', 'ICF Core Competencies (Updated 2019)', 'ICF', "
            "'https://coachingfederation.org/credentials-and-standards/core-competencies', 'public') "
            "ON CONFLICT DO NOTHING RETURNING id"
        ).fetchone()
        source_id = src["id"] if src else conn.execute(
            "SELECT id FROM source WHERE title LIKE 'ICF Core%' LIMIT 1"
        ).fetchone()["id"]

        # 2. Upsert each doc
        for f in files:
            post = frontmatter.load(f)
            doc_id = db.upsert_doc(
                conn,
                slug=f.stem,
                title=post.get("zh_name", f.stem),
                category=post.get("category", ""),
                content_md=post.content,
                meta={
                    "icf_competency": post.get("icf_competency"),
                    "en_name": post.get("en_name"),
                    "levels": post.get("levels", []),
                },
                source_id=source_id,
            )
            print(f"  ✓ {f.stem} → doc_id={doc_id}")
        db.rebuild_fts(conn)
        print("FTS rebuilt.")

        # 3. Compute embeddings (batch)
        docs = db.all_docs(conn)
        texts = [f"{d['title']}\n\n{d['content_md']}" for d in docs]
        print(f"embedding {len(texts)} docs…")
        embeddings = await llm.embed(texts)
        for d, e in zip(docs, embeddings):
            db.upsert_vec(conn, d["id"], e)
        conn.commit()
        print(f"✅ seeded {len(docs)} docs with embeddings.")


if __name__ == "__main__":
    asyncio.run(main())
