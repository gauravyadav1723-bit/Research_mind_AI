import os
os.environ["PYDANTIC_DISABLE_PLUGINS"] = "true"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
