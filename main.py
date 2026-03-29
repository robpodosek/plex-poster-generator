import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import uuid
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from plexapi.server import PlexServer
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    plex = PlexServer(PLEX_URL, PLEX_TOKEN) if PLEX_URL and PLEX_TOKEN else None
except Exception as e:
    print(f"Failed to connect to Plex: {e}")
    plex = None

if GEMINI_API_KEY:
    openai_client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
else:
    openai_client = None

app = FastAPI(title="Plex Poster Generator")

# Serve static files from the 'static' directory
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

@app.get("/api/status")
def get_status():
    return {
        "plex_connected": plex is not None,
        "openai_configured": openai_client is not None
    }

@app.get("/api/libraries")
def get_libraries():
    if not plex:
        raise HTTPException(status_code=500, detail="Plex not connected")
    sections = plex.library.sections()
    # Filter only movie libraries for simplicity
    movie_libs = [s for s in sections if s.type == "movie"]
    return [
        {"id": s.key, "title": s.title} for s in movie_libs
    ]

@app.get("/api/libraries/{library_id}/movies")
def get_movies(library_id: str):
    if not plex:
        raise HTTPException(status_code=500, detail="Plex not connected")
    
    # PlexAPI matches libraries either by exact section ID, title, etc.
    # The key returned as s.key is usually numeric
    try:
        section = plex.library.sectionByID(int(library_id))
    except Exception as e:
        raise HTTPException(status_code=404, detail="Library not found")

    # Fetch recently added movies or all movies (we'll limit to 50 for performance preview)
    # TBD: In a real app we might paginate or search
    movies = section.all()
    # Let's take the first 100 for now
    movies = movies[:100]
    
    results = []
    for m in movies:
        results.append({
            "id": m.ratingKey,
            "title": m.title,
            "year": m.year,
            "poster_url": m.posterUrl if m.thumb else None
        })
    return results

class GenerateRequest(BaseModel):
    movie_id: int
    prompt: str

@app.post("/api/generate_poster")
def generate_poster(req: GenerateRequest):
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI API not configured")
    if not plex:
        raise HTTPException(status_code=500, detail="Plex not connected")

    try:
        movie = plex.fetchItem(req.movie_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Movie not found in Plex")

    # Enhance the prompt slightly to ensure it feels like a movie poster
    enhanced_prompt = f"A high-quality, professional movie poster for '{movie.title}'. {req.prompt}. No text or typography if possible, just the artwork."
    
    try:
        response = openai_client.images.generate(
            model="imagen-3.0-generate-002",
            prompt=enhanced_prompt,
            size="1024x1408", # 3:4 ratio for movie posters
            response_format="b64_json",
            n=1,
        )
        image_b64 = response.data[0].b64_json
        image_data = base64.b64decode(image_b64)
        
        filename = f"{uuid.uuid4().hex}.jpg"
        filepath = os.path.join("static", filename)
        with open(filepath, "wb") as f:
            f.write(image_data)
            
        return {"image_url": f"/static/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateRequest(BaseModel):
    movie_id: int
    image_url: str

@app.post("/api/update_poster")
def update_poster(req: UpdateRequest):
    if not plex:
        raise HTTPException(status_code=500, detail="Plex not connected")

    try:
        movie = plex.fetchItem(req.movie_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Movie not found in Plex")

    try:
        if req.image_url.startswith("/static/"):
            filepath = req.image_url.lstrip("/")
            movie.uploadPoster(filepath=filepath)
        else:
            # uploading an external URL as the new custom poster
            movie.uploadPoster(url=req.image_url)
            
        # refresh the item to ensure plex sees the new metadata
        movie.reload()
        return {"success": True, "new_poster_url": movie.posterUrl}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply poster to Plex: {e}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
