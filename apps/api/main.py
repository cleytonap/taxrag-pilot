from fastapi import FastAPI

app = FastAPI(title="TaxRAG API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is alive; dependency checks come later."""
    return {"status": "ok"}
