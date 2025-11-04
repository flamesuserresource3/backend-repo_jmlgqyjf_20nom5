import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    name: str = Field(default="My Site")
    style: str = Field(default="modern")
    primary: str = Field(default="indigo")
    prompt: str
    api_key: str | None = None


class GenerateResponse(BaseModel):
    html: str


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"

def build_system_prompt(name: str, style: str, primary: str) -> str:
    return (
        "You are a professional web designer and developer. "
        "Generate a single, self-contained HTML document that uses Tailwind via CDN. "
        "It must include <html>, <head>, and <body>. "
        "Do not include markdown code fences. "
        "Use a cohesive palette and typography. "
        f"Brand: {name}. Style: {style}. Primary color family: {primary}. "
        "Sections that are commonly useful: hero, features, testimonials, pricing, FAQ, and footer. "
        "Add subtle animations and accessible markup. "
    )


@app.post("/generate-site", response_model=GenerateResponse)
def generate_site(req: GenerateRequest):
    api_key = req.api_key or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing DeepSeek API key. Provide in request or set DEEPSEEK_API_KEY env var.")

    system_prompt = build_system_prompt(req.name, req.style, req.primary)

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 3000,
    }

    try:
        r = requests.post(
            DEEPSEEK_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text[:500])
        data = r.json()
        # DeepSeek style compatible with OpenAI
        html = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not html:
            raise HTTPException(status_code=502, detail="No content returned from DeepSeek")
        # Ensure it's a complete HTML document; if not, wrap minimally
        if "<html" not in html.lower():
            html = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width, initial-scale=1'/>\n<link href='https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css' rel='stylesheet'>\n<title>{req.name}</title></head><body class='bg-white'>{html}</body></html>"""
        return GenerateResponse(html=html)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:500])


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
