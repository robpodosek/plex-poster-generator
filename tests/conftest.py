import pytest
from playwright.sync_api import Page, Route

@pytest.fixture(autouse=True)
def mock_api(page: Page):
    """
    Globally intercepts API routes to prevent real backend/plex mutations 
    and fast-tracks E2E testing using simulated data.
    """
    def handle_status(route: Route):
        route.fulfill(status=200, json={"plex_connected": True, "openai_configured": True})
        
    def handle_libraries(route: Route):
        route.fulfill(status=200, json=[
            {"id": "1", "title": "Movies - 4K"},
            {"id": "2", "title": "Movies - 1080p"}
        ])
        
    def handle_movies(route: Route):
        route.fulfill(status=200, json=[
            {"id": "test-movie-1", "title": "Mock Movie 1", "year": "2024", "poster_url": "/static/mock.jpg"},
            {"id": "test-movie-2", "title": "Mock Movie 2", "year": "2023", "poster_url": "/static/mock.jpg"}
        ])
        
    def handle_posters(route: Route):
        route.fulfill(status=200, json=[
            {"url": "/static/art1.jpg"},
            {"url": "/static/art2.jpg"}
        ])
        
    def handle_generate(route: Route):
        # Allow UI to show "PROCESSING..." by delaying briefly
        import time
        time.sleep(0.5)
        # 1x1 transparent gif to guarantee `onload` event fires in app.js
        b64 = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="
        route.fulfill(status=200, json={"image_url": b64})
        
    def handle_update(route: Route):
        route.fulfill(status=200, json={"status": "success"})

    page.route("**/api/status", handle_status)
    page.route("**/api/libraries", handle_libraries)
    page.route("**/api/libraries/*/movies", handle_movies)
    page.route("**/api/movies/*/posters", handle_posters)
    page.route("**/api/generate_poster", handle_generate)
    page.route("**/api/update_poster", handle_update)
