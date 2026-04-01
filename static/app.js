document.addEventListener("DOMContentLoaded", () => {
  const librarySelect = document.getElementById("library-select");
  const moviesGrid = document.getElementById("movies-grid");
  const serverStatus = document.getElementById("server-status");
  
  // Inspector elements
  const inspectorPanel = document.getElementById("inspector-panel");
  const inspectorBackdrop = document.getElementById("inspector-backdrop");
  const closeBtn = document.getElementById("close-inspector");
  const modalTitle = document.getElementById("modal-movie-title");
  const currentPosterImg = document.getElementById("current-poster-img");
  const newPosterImg = document.getElementById("new-poster-img");
  const newPosterPlaceholder = document.getElementById("new-poster-placeholder");
  const loadingOverlay = document.getElementById("loading-overlay");
  const promptInput = document.getElementById("prompt-input");
  const generateBtn = document.getElementById("generate-btn");
  const applyBtn = document.getElementById("apply-btn");
  const referenceGallery = document.getElementById("reference-gallery");
  
  let currentMovieId = null;
  let currentGeneratedUrl = null;
  let selectedReferenceUrl = null;
  let previousFocusElement = null; 

  // Initialize
  checkStatus();
  fetchLibraries();

  async function checkStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      if (data.plex_connected && data.openai_configured) {
        serverStatus.textContent = "CONNECTED // ONLINE";
        serverStatus.className = "server-status connected";
      } else {
        serverStatus.textContent = "ERR // CONFIG MISSING";
        serverStatus.className = "server-status error";
      }
    } catch (e) {
      serverStatus.textContent = "ERR // NO CONNECTION";
      serverStatus.className = "server-status error";
    }
  }

  async function fetchLibraries() {
    try {
      const res = await fetch("/api/libraries");
      if (!res.ok) throw new Error("Failed to load");
      const libs = await res.json();
      
      librarySelect.innerHTML = "<option value='' disabled>AWAITING SELECTION...</option>";
      let moviesLibId = null;

      libs.forEach(lib => {
        const opt = document.createElement("option");
        opt.value = lib.id;
        opt.textContent = lib.title;
        if (lib.title === "Movies") {
          opt.selected = true;
          moviesLibId = lib.id;
        }
        librarySelect.appendChild(opt);
      });

      librarySelect.disabled = false;
      librarySelect.setAttribute("aria-busy", "false");

      // Auto-load if Movies was found
      if (moviesLibId) {
        loadMovies(moviesLibId);
      }
    } catch (err) {
      librarySelect.innerHTML = "<option>ERR // LOAD FAILED</option>";
      librarySelect.setAttribute("aria-busy", "false");
    }
  }

  async function loadMovies(libId) {
    if (!libId) return;
    moviesGrid.innerHTML = "<p>Retrieving database records...</p>";
    moviesGrid.setAttribute("aria-busy", "true");
    try {
      const res = await fetch(`/api/libraries/${libId}/movies`);
      const movies = await res.json();
      renderMovies(movies);
    } catch (err) {
      moviesGrid.innerHTML = "<p>ERR // Movie fetch failed.</p>";
    } finally {
      moviesGrid.setAttribute("aria-busy", "false");
    }
  }

  librarySelect.addEventListener("change", (e) => {
    loadMovies(e.target.value);
  });

  function renderMovies(movies) {
    moviesGrid.innerHTML = "";
    movies.forEach(movie => {
      // Changed div to button for semantic WCAG compliance
      const card = document.createElement("button");
      card.className = "movie-card";
      card.setAttribute("aria-label", `Edit poster for ${movie.title} (${movie.year || 'Unknown year'})`);
      
      const img = document.createElement("img");
      img.className = "movie-poster";
      img.src = movie.poster_url || "/static/placeholder.jpg";
      img.alt = ""; // Decorative, title is in the card
      img.onerror = () => { img.src = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="; }; 
      
      const info = document.createElement("div");
      info.className = "movie-info";
      
      const title = document.createElement("div");
      title.className = "movie-title";
      title.textContent = movie.title;
      
      const year = document.createElement("div");
      year.className = "movie-year";
      year.textContent = movie.year || "----";
      
      info.appendChild(title);
      info.appendChild(year);
      card.appendChild(img);
      card.appendChild(info);
      
      card.addEventListener("click", () => openInspector(movie, card));
      moviesGrid.appendChild(card);
    });
  }

  function openInspector(movie, sourceElement) {
    previousFocusElement = sourceElement; // Save focus
    currentMovieId = movie.id;
    currentGeneratedUrl = null;
    selectedReferenceUrl = null;
    modalTitle.textContent = movie.title;
    currentPosterImg.src = movie.poster_url || "";
    
    // Reset generation state
    newPosterImg.classList.add("hidden");
    newPosterImg.src = "";
    newPosterPlaceholder.classList.remove("hidden");
    newPosterPlaceholder.classList.add("active");
    loadingOverlay.classList.add("hidden");
    promptInput.value = "";
    applyBtn.classList.add("hidden");
    generateBtn.textContent = "EXECUTE RENDER";
    generateBtn.disabled = false;
    
    // Load alternative posters
    referenceGallery.innerHTML = "<p style='color:var(--text-muted); font-size: 0.8rem;'>Syncing variants...</p>";
    fetch(`/api/movies/${movie.id}/posters`)
      .then(r => r.json())
      .then(posters => {
        referenceGallery.innerHTML = "";
        
        const addReferenceItem = (url, isSelected, index) => {
          const btn = document.createElement("button");
          btn.className = `reference-item ${isSelected ? "selected" : ""}`;
          btn.setAttribute("role", "radio");
          btn.setAttribute("aria-checked", isSelected ? "true" : "false");
          btn.setAttribute("aria-label", `Base poster variant ${index}`);
          
          btn.style.backgroundImage = `url('${url}')`;
          btn.style.backgroundSize = 'cover';
          
          btn.addEventListener("click", () => {
             document.querySelectorAll(".reference-item").forEach(el => {
               el.classList.remove("selected");
               el.setAttribute("aria-checked", "false");
             });
             if (selectedReferenceUrl === url) {
               selectedReferenceUrl = null; 
               currentPosterImg.src = movie.poster_url || "";
             } else {
               btn.classList.add("selected");
               btn.setAttribute("aria-checked", "true");
               selectedReferenceUrl = url;
               currentPosterImg.src = url;
             }
          });
          referenceGallery.appendChild(btn);
        };
        
        // Always place the active movie poster first and pre-select it
        if (movie.poster_url) {
          addReferenceItem(movie.poster_url, true, 1);
          selectedReferenceUrl = movie.poster_url;
        }

        let idx = 2;
        posters.forEach(p => {
          if (p.url !== movie.poster_url) {
            addReferenceItem(p.url, false, idx++);
          }
        });
      })
      .catch(e => {
        referenceGallery.innerHTML = "<p style='color:var(--text-muted); font-size: 0.8rem;'>No reference variants available.</p>";
      });

    inspectorPanel.classList.add("active");
    inspectorBackdrop.classList.add("active");
    inspectorPanel.setAttribute("aria-hidden", "false");
    
    // Set focus to the first focusable element inside the inspector
    setTimeout(() => {
        closeBtn.focus();
    }, 100);
  }

  function closeInspector() {
    inspectorPanel.classList.remove("active");
    inspectorBackdrop.classList.remove("active");
    inspectorPanel.setAttribute("aria-hidden", "true");
    
    if (previousFocusElement) {
      previousFocusElement.focus();
    }
  }

  closeBtn.addEventListener("click", closeInspector);
  inspectorBackdrop.addEventListener("click", closeInspector);
  
  // Trap Focus and Escape key to close
  inspectorPanel.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
          closeInspector();
      }
      
      if (e.key === 'Tab') {
          const focusableElements = inspectorPanel.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
          const firstElement = focusableElements[0];
          const lastElement = focusableElements[focusableElements.length - 1];

          if (e.shiftKey) { 
              if (document.activeElement === firstElement) {
                  lastElement.focus();
                  e.preventDefault();
              }
          } else { 
              if (document.activeElement === lastElement) {
                  firstElement.focus();
                  e.preventDefault();
              }
          }
      }
  });

  generateBtn.addEventListener("click", async () => {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      alert("Please provide explicit visual parameters.");
      return;
    }

    loadingOverlay.classList.remove("hidden");
    newPosterPlaceholder.classList.remove("active");
    generateBtn.disabled = true;
    generateBtn.textContent = "PROCESSING...";

    try {
      const payload = { movie_id: currentMovieId, prompt };
      if (selectedReferenceUrl) {
        payload.reference_poster_url = selectedReferenceUrl;
      }

      const res = await fetch("/api/generate_poster", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Generation failed");
      }

      const data = await res.json();
      currentGeneratedUrl = data.image_url;
      
      newPosterImg.src = currentGeneratedUrl;
      newPosterImg.onload = () => {
         newPosterImg.classList.remove("hidden");
         applyBtn.classList.remove("hidden");
         generateBtn.textContent = "NEW ITERATION";
         applyBtn.focus(); // Shift focus down to apply
      }
    } catch (e) {
      alert("ERR: " + e.message);
      newPosterPlaceholder.classList.add("active");
      generateBtn.textContent = "EXECUTE RENDER";
    } finally {
      loadingOverlay.classList.add("hidden");
      generateBtn.disabled = false;
    }
  });

  applyBtn.addEventListener("click", async () => {
    if (!currentGeneratedUrl || !currentMovieId) return;
    applyBtn.disabled = true;
    applyBtn.textContent = "COMMITTING...";

    try {
      const res = await fetch("/api/update_poster", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ movie_id: currentMovieId, image_url: currentGeneratedUrl })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Update failed");
      }
      
      alert("COMMIT SUCCESS // Active poster overwritten.");
      currentPosterImg.src = currentGeneratedUrl;
      
    } catch (e) {
      alert("COMMIT ERR: " + e.message);
    } finally {
      applyBtn.textContent = "COMMIT TO SERVER";
      applyBtn.disabled = false;
    }
  });
});
