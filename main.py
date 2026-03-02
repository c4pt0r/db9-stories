"""
db9 Stories - Share your db9 success stories
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os

app = FastAPI(
    title="db9 Stories",
    description="Share and discover db9 success stories",
    version="1.0.0"
)

# Serve static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# db9 config
DB9_API_URL = os.getenv("DB9_API_URL", "https://staging.db9.ai/api")
DB9_TOKEN = os.getenv("DB9_TOKEN")
DB9_ID = os.getenv("DB9_ID", "rkwkfa6enstb")

class StoryCreate(BaseModel):
    title: str
    content: str
    author: Optional[str] = "anonymous"
    code_snippet: Optional[str] = None
    tags: Optional[List[str]] = []

class Story(StoryCreate):
    id: int
    created_at: str
    updated_at: str

async def db9_sql(query: str) -> dict:
    """Execute SQL via db9 API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{DB9_API_URL}/customer/databases/{DB9_ID}/sql",
            headers={"Authorization": f"Bearer {DB9_TOKEN}"},
            json={"query": query}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"db9 error: {resp.text}")
        return resp.json()

@app.get("/")
async def root():
    """Serve the frontend"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/SKILL.md")
async def skill_md():
    """Serve the skill documentation"""
    skill_path = os.path.join(os.path.dirname(__file__), "SKILL.md")
    return FileResponse(skill_path, media_type="text/markdown")

@app.get("/api")
async def api_info():
    return {
        "service": "db9 Stories",
        "version": "1.0.0",
        "endpoints": {
            "list": "GET /stories",
            "search": "GET /stories/search?q=keyword",
            "get": "GET /stories/{id}",
            "create": "POST /stories"
        }
    }

def parse_rows(result: dict) -> list[dict]:
    """Parse db9 API response into list of dicts"""
    rows = result.get("rows", [])
    columns = result.get("columns", [])
    # columns is [{name: str, type: str}, ...]
    col_names = [c["name"] if isinstance(c, dict) else c for c in columns]
    return [dict(zip(col_names, row)) for row in rows]

@app.get("/stories")
async def list_stories(limit: int = Query(20, le=100), offset: int = 0):
    """List all stories, newest first"""
    query = f"""
        SELECT id, title, author, content, code_snippet, tags, 
               created_at::text, updated_at::text
        FROM stories 
        ORDER BY created_at DESC 
        LIMIT {limit} OFFSET {offset}
    """
    result = await db9_sql(query)
    stories = parse_rows(result)
    return {"stories": stories, "count": len(stories)}

@app.get("/stories/search")
async def search_stories(q: str = Query(..., min_length=1), limit: int = Query(20, le=100), offset: int = 0):
    """Full-text search stories (Chinese + English)"""
    # Escape single quotes
    safe_q = q.replace("'", "''")
    
    # Get total count first
    count_query = f"""
        SELECT COUNT(*) as total
        FROM stories
        WHERE to_tsvector('chinese', title || ' ' || content || ' ' || COALESCE(code_snippet, '')) 
              @@ plainto_tsquery('chinese', '{safe_q}')
    """
    count_result = await db9_sql(count_query)
    total = parse_rows(count_result)[0]["total"] if parse_rows(count_result) else 0
    
    query = f"""
        SELECT id, title, author, content, code_snippet, tags,
               created_at::text, updated_at::text,
               ts_rank(to_tsvector('chinese', title || ' ' || content || ' ' || COALESCE(code_snippet, '')), 
                       plainto_tsquery('chinese', '{safe_q}')) AS rank
        FROM stories
        WHERE to_tsvector('chinese', title || ' ' || content || ' ' || COALESCE(code_snippet, '')) 
              @@ plainto_tsquery('chinese', '{safe_q}')
        ORDER BY rank DESC, created_at DESC
        LIMIT {limit} OFFSET {offset}
    """
    result = await db9_sql(query)
    stories = parse_rows(result)
    return {"query": q, "stories": stories, "count": total}

@app.get("/stories/{story_id}")
async def get_story(story_id: int):
    """Get a single story by ID"""
    query = f"""
        SELECT id, title, author, content, code_snippet, tags,
               created_at::text, updated_at::text
        FROM stories WHERE id = {story_id}
    """
    result = await db9_sql(query)
    stories = parse_rows(result)
    
    if not stories:
        raise HTTPException(status_code=404, detail="Story not found")
    
    return stories[0]

@app.post("/stories", status_code=201)
async def create_story(story: StoryCreate):
    """Submit a new story"""
    # Escape single quotes
    title = story.title.replace("'", "''")
    content = story.content.replace("'", "''")
    author = (story.author or "anonymous").replace("'", "''")
    code = (story.code_snippet or "").replace("'", "''")
    tags = "{" + ",".join(f'"{t}"' for t in (story.tags or [])) + "}"
    
    query = f"""
        INSERT INTO stories (title, author, content, code_snippet, tags)
        VALUES ('{title}', '{author}', '{content}', 
                {f"'{code}'" if code else 'NULL'}, 
                '{tags}')
        RETURNING id, title, author, content, code_snippet, tags, 
                  created_at::text, updated_at::text
    """
    result = await db9_sql(query)
    stories = parse_rows(result)
    
    if not stories:
        raise HTTPException(status_code=500, detail="Failed to create story")
    
    return stories[0]

@app.get("/health")
async def health():
    """Health check"""
    try:
        result = await db9_sql("SELECT COUNT(*) FROM stories")
        count = result.get("rows", [[0]])[0][0]
        return {"status": "healthy", "story_count": count}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3458)
