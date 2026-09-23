"""One server for Docker, Python hosting and local demos."""
import os
import uvicorn
from run import load_environment

if __name__ == "__main__":
    load_environment()
    port = int(os.getenv("PORT", "8520"))
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535")
    uvicorn.run("backend.hosted:app", host=os.getenv("HOST", "127.0.0.1"), port=port,
                proxy_headers=False)
