
from fastapi import FastAPI
from app.api.orders import router as orders_router

app = FastAPI(
    title="Provider XX Order Automation",
    description="API for managing Provider XX order automation",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Provider XX Order Automation API is running",
        "status": "success"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Provider XX Order Automation"
    }


app.include_router(orders_router, prefix="/api/orders", tags=["Orders"])
