"""
Production entrypoint. Binds to the host/port the platform provides via $PORT
(Render, Railway, Fly, Heroku, etc. all inject this). Locally it defaults to 8000.

    python server.py
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
