import os
import uvicorn
import base64
import uuid
import requests
from requests.exceptions import RequestException
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from plexapi.server import PlexServer
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# Configure logging to output to console
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("plex-studio")

load_dotenv(override=True)

PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

missing = [name for name, val in [("PLEX_URL", PLEX_URL), ("PLEX_TOKEN", PLEX_TOKEN), ("GEMINI_API_KEY", GEMINI_API_KEY)] if not val]
if missing:
    logger.error(f"Missing required environment variables: {', '.join(missing)}")
    raise SystemExit(1)

try:
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    plex.library.sections()  # Validate the connection
except Exception as e:
    logger.error(f"Failed to connect to Plex at {PLEX_URL}: {e}")
    raise SystemExit(1)

# Using direct REST API for Gemini
def call_gemini_api(model: str, payload: dict) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize application directories
    Path("static").mkdir(parents=True, exist_ok=True)
    Path("data/generated").mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(
    title="Plex Poster Generator",
    description="Studio for custom AI-generated Plex posters.",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/generated", StaticFiles(directory="data/generated"), name="generated")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/api/status")
def get_status():
    return {
        "plex_connected": plex is not None,
        "gemini_configured": bool(GEMINI_API_KEY)
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
    except Exception:
        raise HTTPException(status_code=404, detail="Library not found")

    # TBD: In a real app we might paginate or search. Currently limits to default fetch.
    movies = section.all()
    
    results = []
    for m in movies:
        results.append({
            "id": m.ratingKey,
            "title": m.title,
            "year": m.year,
            "poster_url": (plex.url(m.thumb) + f"?X-Plex-Token={PLEX_TOKEN}") if m.thumb else None
        })
    return results

@app.get("/api/movies/{movie_id}/posters")
def get_movie_posters(movie_id: int):
    if not plex:
        raise HTTPException(status_code=500, detail="Plex not connected")

    try:
        movie = plex.fetchItem(movie_id)
        posters = movie.posters()
        results = []
        seen_keys = set()
        
        for p in posters:
            if p.key in seen_keys:
                continue
            seen_keys.add(p.key)
            
            if len(results) >= 10:
                break
                
            if p.key.startswith("http"):
                url = p.key
            else:
                url = plex.url(p.key)
                if "X-Plex-Token=" not in url:
                    op = "&" if "?" in url else "?"
                    url += f"{op}X-Plex-Token={PLEX_TOKEN}"
            results.append({
                "key": p.key,
                "url": url
            })
        return results
    except Exception as e:
        logger.error(f"Error fetching posters for movie {movie_id}: {e}")
        raise HTTPException(status_code=404, detail="Movie not found in Plex")
    
def extract_image_data(content: str) -> Optional[str]:
    """Extract Base64 image data from model response."""
    if not content:
        return None
    
    # Check for direct Data URI
    import re
    match = re.search(r"data:image/[^;]+;base64,([^\"\'\s>]+)", content)
    if match:
        return match.group(1)
    
    # Fallback to raw Base64 if no prefix
    # Simple heuristic: long string without whitespace
    stripped = content.strip()
    if len(stripped) > 1000 and not any(c in stripped[:100] for c in " \n\t"):
        return stripped
    
    return None

class GenerateRequest(BaseModel):
    movie_id: int
    prompt: str
    reference_poster_url: Optional[str] = None

@app.post("/api/generate_poster")
async def generate_poster(req: GenerateRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    if not plex:
        raise HTTPException(status_code=500, detail="Plex not connected")

    try:
        movie = await run_in_threadpool(plex.fetchItem, req.movie_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Movie not found in Plex")

    # Step 1: Vision Analysis (if reference provided)
    enhanced_prompt_details = ""
    if req.reference_poster_url:
        try:
            r = await run_in_threadpool(requests.get, req.reference_poster_url, timeout=10)
            r.raise_for_status()
            img_b64 = base64.b64encode(r.content).decode("utf-8")

            vision_payload = {
                "contents": [{
                    "parts": [
                        {"text": f"Analyze the following movie poster for technical details (layout, lighting, palette). Then, generate a high-quality movie poster prompt for the title '{movie.title}' that incorporates the following user request: '{req.prompt}'. Ensure the prompt explicitly includes the exact title '{movie.title}' in the final poster design with premium typography. Output ONLY the prompt."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                    ]
                }]
            }
            
            vision_response = await run_in_threadpool(call_gemini_api, "gemini-1.5-flash-latest", vision_payload)
            enhanced_prompt_details = vision_response["candidates"][0]["content"]["parts"][0]["text"].strip()
            logger.info(f"Gemini 1.5 Vision Prompt: {enhanced_prompt_details}")
        except Exception as e:
            logger.error(f"Failed to process reference image: {e}")

    # Step 2: Magic Prompt Expansion (if no vision, or to further refine)
    if not enhanced_prompt_details:
        magic_payload = {
            "contents": [{
                "parts": [{"text": f"Generate a professional, cinematic movie poster generation prompt for the movie title '{movie.title}'. Incorporate the user's stylistic request: '{req.prompt}'. The final image MUST clearly and artistically display the title '{movie.title}'. Focus on 8k hyper-realistic film grain, dramatic lighting, and studio-grade composition. Output ONLY the prompt."}]
            }]
        }
        try:
            magic_response = await run_in_threadpool(call_gemini_api, "gemini-1.5-flash-latest", magic_payload)
            enhanced_prompt = magic_response["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.error(f"Magic prompt expansion failed: {e}")
            enhanced_prompt = f"A professional movie poster for '{movie.title}'. {req.prompt}"
    else:
        enhanced_prompt = enhanced_prompt_details

    # Step 3: Image Generation with Gemini 3.1 Flash Image Preview
    try:
        image_payload = {
            "contents": [{
                "parts": [{"text": enhanced_prompt}]
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": "2:3",
                    "imageSize": "1K"
                }
            }
        }
        
        image_response = await run_in_threadpool(call_gemini_api, "gemini-3.1-flash-image-preview", image_payload)
        
        # Response structure for Gemini 3.1 Image Preview
        parts = image_response.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        image_b64 = None
        for part in parts:
            if "inlineData" in part:
                image_b64 = part["inlineData"]["data"]
                break
            elif "inline_data" in part:
                image_b64 = part["inline_data"]["data"]
                break

        if not image_b64:
            logger.error(f"No image data in response: {image_response}")
            raise HTTPException(status_code=400, detail="Image generation failed: No image data returned.")

        image_data = base64.b64decode(image_b64)
        
        safe_title = "".join([c for c in movie.title if c.isalnum() or c.isspace()]).strip().replace(" ", "_").lower()
        if not safe_title: safe_title = "poster"
        
        filename = f"{safe_title}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = Path("data/generated") / filename
        await run_in_threadpool(filepath.write_bytes, image_data)
            
        return {"image_url": f"/generated/{filename}", "enhanced_prompt": enhanced_prompt}
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
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
        if req.image_url.startswith("/generated/"):
            filepath = req.image_url.replace("/generated/", "data/generated/")
            movie.uploadPoster(filepath=filepath)
        elif req.image_url.startswith("/static/"):
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
