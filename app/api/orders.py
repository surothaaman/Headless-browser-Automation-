
from uuid import uuid4
from fastapi import APIRouter, HTTPException

from app.schemas.order import OrderRequest

router = APIRouter()

# Temporary in-memory storage for development
orders = {}


@router.post("/")
def create_order(order: OrderRequest):
    order_id = str(uuid4())

    orders[order_id] = {
        "order_id": order_id,
        "status": "received",
        "provider": order.product.provider,
        "customer": order.customer.first_name,
        "message": "Order request received successfully"
    }

    return orders[order_id]


@router.get("/{order_id}")
def get_order_status(order_id: str):
    if order_id not in orders:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return orders[order_id]
