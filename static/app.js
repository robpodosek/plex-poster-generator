document.addEventListener("DOMContentLoaded", () => {
  const librarySelect = document.getElementById("library-select");
  const moviesGrid = document.getElementById("movies-grid");
  const serverStatus = document.getElementById("server-status");
  
  // Modal elements
  const modal = document.getElementById("poster-modal");
  const closeBtn = document.getElementById("close-modal");
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

  // Initialize
  checkStatus();
  fetchLibraries();

  async function checkStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      if (data.plex_connected && data.openai_configured) {
        serverStatus.textContent = "● Connected";
        serverStatus.className = "server-status connected";
      } else {
        serverStatus.textContent = "● Configuration Missing";
        serverStatus.className = "server-status error";
      }
    } catch (e) {
      serverStatus.textContent = "● Backend Disconnected";
      serverStatus.className = "server-status error";
    }
  }

  async function fetchLibraries() {
    try {
      const res = await fetch("/api/libraries");
      if (!res.ok) throw new Error("Failed to load");
      const libs = await res.json();
      
      librarySelect.innerHTML = "<option value=''>Select a library...</option>";
      libs.forEach(lib => {
        const opt = document.createElement("option");
        opt.value = lib.id;
        opt.textContent = lib.title;
        librarySelect.appendChild(opt);
      });
      librarySelect.disabled = false;
    } catch (err) {
      librarySelect.innerHTML = "<option>Failed to load libraries</option>";
    }
  }

  librarySelect.addEventListener("change", async (e) => {
    const libId = e.target.value;
    if (!libId) return;
    
    moviesGrid.innerHTML = "<p>Loading movies...</p>";
    try {
      const res = await fetch(`/api/libraries/${libId}/movies`);
      const movies = await res.json();
      renderMovies(movies);
    } catch (err) {
      moviesGrid.innerHTML = "<p>Error loading movies.</p>";
    }
  });

  function renderMovies(movies) {
    moviesGrid.innerHTML = "";
    movies.forEach(movie => {
      const card = document.createElement("div");
      card.className = "movie-card";
      
      const img = document.createElement("img");
      img.className = "movie-poster";
      img.src = movie.poster_url || "/static/placeholder.jpg";
      img.alt = movie.title;
      img.onerror = () => { img.src = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs="; }; // transparent fallback
      
      const info = document.createElement("div");
      info.className = "movie-info";
      
      const title = document.createElement("div");
      title.className = "movie-title";
      title.textContent = movie.title;
      
      const year = document.createElement("div");
      year.className = "movie-year";
      year.textContent = movie.year || "Unknown";
      
      info.appendChild(title);
      info.appendChild(year);
      card.appendChild(img);
      card.appendChild(info);
      
      card.addEventListener("click", () => openModal(movie));
      moviesGrid.appendChild(card);
    });
  }

  function openModal(movie) {
    currentMovieId = movie.id;
    currentGeneratedUrl = null;
    selectedReferenceUrl = null;
    modalTitle.textContent = movie.title;
    currentPosterImg.src = movie.poster_url || "";
    
    // Reset generation state
    newPosterImg.classList.add("hidden");
    newPosterImg.src = "";
    newPosterPlaceholder.classList.add("active");
    loadingOverlay.classList.add("hidden");
    promptInput.value = "";
    applyBtn.classList.add("hidden");
    generateBtn.textContent = "Generate Image";
    generateBtn.disabled = false;
    
    // Load alternative posters
    referenceGallery.innerHTML = "<p style='color:var(--text-muted); font-size: 0.8rem;'>Loading posters...</p>";
    fetch(`/api/movies/${movie.id}/posters`)
      .then(r => r.json())
      .then(posters => {
        referenceGallery.innerHTML = "";
        
        const addReferenceItem = (url, isSelected) => {
          const img = document.createElement("img");
          img.src = url;
          img.className = "reference-item" + (isSelected ? " selected" : "");
          
          img.addEventListener("click", () => {
             document.querySelectorAll(".reference-item").forEach(el => el.classList.remove("selected"));
             if (selectedReferenceUrl === url) {
               selectedReferenceUrl = null; 
               currentPosterImg.src = movie.poster_url || "";
             } else {
               img.classList.add("selected");
               selectedReferenceUrl = url;
               currentPosterImg.src = url;
             }
          });
          referenceGallery.appendChild(img);
        };
        
        // Always place the active movie poster first and pre-select it
        if (movie.poster_url) {
          addReferenceItem(movie.poster_url, true);
          selectedReferenceUrl = movie.poster_url;
        }

        posters.forEach(p => {
          if (p.url !== movie.poster_url) {
            addReferenceItem(p.url, false);
          }
        });
      })
      .catch(e => {
        referenceGallery.innerHTML = "<p style='color:var(--text-muted); font-size: 0.8rem;'>No reference posters available.</p>";
      });

    modal.classList.add("active");
  }

  closeBtn.addEventListener("click", () => {
    modal.classList.remove("active");
  });
  
  // Close on backdrop click
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.remove("active");
    }
  });

  generateBtn.addEventListener("click", async () => {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      alert("Please enter a prompt for the AI.");
      return;
    }

    // Set loading state
    loadingOverlay.classList.remove("hidden");
    newPosterPlaceholder.classList.remove("active");
    generateBtn.disabled = true;
    generateBtn.textContent = "Generating...";

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
      
      // Update new poster image
      newPosterImg.src = currentGeneratedUrl;
      newPosterImg.classList.remove("hidden");
      applyBtn.classList.remove("hidden");
      generateBtn.textContent = "Generate Again";

    } catch (e) {
      alert("Error: " + e.message);
      newPosterPlaceholder.classList.add("active");
      generateBtn.textContent = "Generate Image";
    } finally {
      loadingOverlay.classList.add("hidden");
      generateBtn.disabled = false;
    }
  });

  applyBtn.addEventListener("click", async () => {
    if (!currentGeneratedUrl || !currentMovieId) return;
    
    applyBtn.disabled = true;
    applyBtn.textContent = "Applying...";

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
      
      alert("Success! The new poster has been applied to Plex.");
      
      // Update UI
      currentPosterImg.src = currentGeneratedUrl;
      
    } catch (e) {
      alert("Error applying poster: " + e.message);
    } finally {
      applyBtn.textContent = "Apply to Plex";
      applyBtn.disabled = false;
    }
  });
});
