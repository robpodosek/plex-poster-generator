import re
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"

def test_baseline_render_and_connection(page: Page):
    """Verifies that the core DOM renders and network connection is processed."""
    page.goto(BASE_URL)
    
    # 1. Connection Status: API mocked to return True, True
    status_locator = page.locator("#server-status")
    expect(status_locator).to_have_text("CONNECTED // ONLINE")
    expect(status_locator).to_have_class(re.compile(r"connected"))

def test_database_simulation(page: Page):
    """Verifies that library selection dynamically fetches movies and renders Semantic HTML layout."""
    page.goto(BASE_URL)
    
    # Wait for libraries to load
    select = page.locator("#library-select")
    expect(select).not_to_be_disabled()
    
    # Select library (should trigger movie fetch)
    select.select_option(value="1")
    
    # Verify movies appear
    movies_grid = page.locator("#movies-grid")
    cards = movies_grid.locator(".movie-card")
    expect(cards).to_have_count(2)
    
    # Check proper rendering
    expect(cards.first.locator(".movie-title")).to_have_text("Mock Movie 1")

def test_modal_focus_and_accessibility(page: Page):
    """Verifies that clicking a movie surfaces the dialog and forces focus inside (a11y)."""
    page.goto(BASE_URL)
    page.locator("#library-select").select_option(value="1")
    
    card = page.locator(".movie-card").first
    card.click()
    
    panel = page.locator("#inspector-panel")
    expect(panel).to_have_class(re.compile(r"active"))
    
    # Check title
    expect(page.locator("#modal-movie-title")).to_have_text("Mock Movie 1")
    
    # Focus should be trapped / element interactive
    close_btn = page.locator("#close-inspector")
    expect(close_btn).to_be_focused()
    
    # Test Escape closes it
    page.keyboard.press("Escape")
    expect(panel).not_to_have_class(re.compile(r"active"))

def test_generation_execution_pipeline(page: Page):
    """Verifies that rendering triggers 'PROCESSING...' text, delays, then exposes the POST COMMIT button."""
    page.goto(BASE_URL)
    page.locator("#library-select").select_option(value="1")
    page.locator(".movie-card").first.click()
    
    # Fill prompt
    prompt_input = page.locator("#prompt-input")
    prompt_input.fill("Cyberpunk neon style")
    
    # Generate
    generate_btn = page.locator("#generate-btn")
    generate_btn.click()
    
    # Should say PROCESSING...
    expect(generate_btn).to_have_text("PROCESSING...")
    
    # After mock delay, should update to NEW ITERATION and show COMMIT button
    apply_btn = page.locator("#apply-btn")
    expect(apply_btn).not_to_have_class(re.compile(r"hidden"), timeout=5000)
    expect(generate_btn).to_have_text("NEW ITERATION")
