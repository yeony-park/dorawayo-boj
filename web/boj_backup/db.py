from pathlib import Path
import sqlite3
import json

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "boj.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def parse_problem_row(row):
    problem = dict(row)

    try:
        problem["tags"] = json.loads(problem["tags"])
    except json.JSONDecodeError:
        problem["tags"] = []

    try:
        problem["examples"] = json.loads(problem.get("examples", "[]"))
    except (json.JSONDecodeError, TypeError):
        problem["examples"] = []

    return problem

def get_problem_count():
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS count FROM boj_problem").fetchone()
        return row["count"]
    finally:
        conn.close()

def get_problem_list(query="", tier="", tag="", page=1, page_size=50):
    offset = (page - 1) * page_size

    where_clauses = []
    params = []

    if query:
        if query.isdigit():
            where_clauses.append("problem_id = ?")
            params.append(int(query))
        else:
            where_clauses.append("title LIKE ?")
            params.append(f"%{query}%")

    if tier:
        if tier == "Unrated":
            where_clauses.append("level = 0")
        else:
            where_clauses.append("level_name LIKE ?")
            params.append(f"%{tier}%")

    if tag:
        where_clauses.append("tags LIKE ?")
        params.append(f"%{tag}%")

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    conn = get_connection()
    try:
        count_sql = f"SELECT COUNT(*) AS count FROM boj_problem {where_sql}"
        total_count = conn.execute(count_sql, params).fetchone()["count"]

        list_sql = f"""
            SELECT
                problem_id,
                title,
                level,
                level_name,
                tags,
                time_limit,
                mem_limit
            FROM boj_problem
            {where_sql}
            ORDER BY problem_id
            LIMIT ? OFFSET ?
        """

        rows = conn.execute(list_sql, params + [page_size, offset]).fetchall()
        problems = [parse_problem_row(row) for row in rows]

        return {
            "problems": problems,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": max((total_count + page_size - 1) // page_size, 1),
        }
    finally:
        conn.close()

def get_problem_detail(problem_id):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                problem_id,
                title,
                level,
                level_name,
                tags,
                description,
                input_desc,
                output_desc,
                time_limit,
                mem_limit,
                source,
                source_category,
                COALESCE(examples, '[]') as examples
            FROM boj_problem
            WHERE problem_id = ?
            """,
            [problem_id],
        ).fetchone()

        if row is None:
            return None

        return parse_problem_row(row)
    finally:
        conn.close()