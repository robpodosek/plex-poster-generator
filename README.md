# 🎬 Plex Poster Generator

Transform your Plex library with high-quality, AI-generated custom movie posters. This tool uses Google's **Imagen 3** (via Gemini API) to create stunning alternative artwork tailored to your favorite films, and it synchronizes them directly back to your Plex Media Server.

![Custom Poster Demo](https://images.unsplash.com/photo-1536440136628-849c177e76a1?q=80&w=1000&auto=format&fit=crop)

## ✨ Features

- **AI-Driven Creativity**: Leverage Gemini's Imagen 3 model to generate custom posters from simple prompts.
- **Direct Plex Integration**: Browse your existing Plex library and instantly upload new posters with one click.
- **Smart Aspect Ratios**: Automatically generates images in a 3:4 portrait ratio to fit perfectly within Plex UI.
- **Local Persistence**: AI-generated posters are stored locally in the `static/` directory for fast serving and easy backup.
- **Modern Python Stack**: Built with FastAPI and managed by `uv` for lightning-fast performance and clean dependency management.

## 🛠️ Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/)
- **AI Model**: [Google Imagen 3 via Gemini API](https://ai.google.dev/gemini-api/docs/imagen)
- **Library Management**: [PlexAPI](https://github.com/pmsipilot/PlexAPI)
- **Package Manager**: [uv](https://github.com/astral-sh/uv)

## 🚀 Getting Started

### Prerequisites

- A **Plex Media Server** and your [Plex Token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).
- A **Google Gemini API Key** (Get one at [Google AI Studio](https://aistudio.google.com/)).

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/plex-poster-generator.git
   cd plex-poster-generator
   ```

2. **Setup environment variables**:
   Copy the example environment file and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and provide your `PLEX_URL`, `PLEX_TOKEN`, and `GEMINI_API_KEY`.

3. **Install dependencies**:
   ```bash
   uv sync
   ```

### Running the Application

Start the development server:
```bash
uv run uvicorn main:app --reload
```

Open your browser to `http://localhost:8000` to start re-imagining your library!

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

## 📜 License

[MIT License](LICENSE)
