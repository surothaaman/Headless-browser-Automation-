
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.order import OrderRequest
from app.database.connection import get_db
from app.database.models import Order

router = APIRouter()


@router.post("/")
def create_order(
    order: OrderRequest,
    db: Session = Depends(get_db)
):
    order_id = str(uuid4())

    order_data = order.model_dump(mode="json")

    db_order = Order(
        order_id=order_id,
        status="received",
        provider=order.product.provider,
        customer=order.customer.first_name,
        order_details=order_data
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    return {
        "order_id": db_order.order_id,
        "status": db_order.status,
        "provider": db_order.provider,
        "customer": db_order.customer,
        "order_details": db_order.order_details,
        "created_at": db_order.created_at.isoformat(),
        "message": "Order request saved successfully"
    }


@router.get("/{order_id}")
def get_order_status(
    order_id: str,
    db: Session = Depends(get_db)
):
    db_order = db.query(Order).filter(
        Order.order_id == order_id
    ).first()

    if db_order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return {
        "order_id": db_order.order_id,
        "status": db_order.status,
        "provider": db_order.provider,
        "customer": db_order.customer,
        "order_details": db_order.order_details,
        "created_at": db_order.created_at.isoformat()
    }
