---
description: Kill the background dev server if it was started by the agent
---

Hard-kill any uvicorn process running in the background (started by the agent, not the integrated terminal).

// turbo
1. Kill -9 the background server:
```bash
pkill -9 -f "uvicorn main:app" || true
```
