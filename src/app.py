from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlmodel import SQLModel, create_engine, Session, select, func

from models import Address, Transaction
from services import sync_transactions_for_address

DATABASE_URL = "sqlite:///./cointracker_demo.db"
engine = create_engine(DATABASE_URL, echo=True)

app = FastAPI()

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# Schema for adding addresses
class AddressCreate(BaseModel):
    address: str

@app.post("/addresses")
def create_address(payload: AddressCreate):
    with Session(engine) as session:
        # Check if address already exists
        stmt = select(Address).where(Address.address == payload.address)
        existing = session.exec(stmt).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Address {payload.address} already exists (id={existing.id})"
            )

        new_address = Address(address=payload.address)
        session.add(new_address)
        session.commit()
        session.refresh(new_address)
        return {
            "id": new_address.id,
            "address": new_address.address,
            "created_at": new_address.created_at
        }

@app.get("/addresses/lookup")
def get_id_for_address(address: str):
    """
    Returns the integer 'id' for the given BTC address.
    Example usage: GET /addresses/lookup?address=<some address>
    """
    with Session(engine) as session:
        stmt = select(Address).where(Address.address == address)
        address_obj = session.exec(stmt).first()
        if not address_obj:
            raise HTTPException(status_code=404, detail="Address not found")

        return {
            "id": address_obj.id,
            "address": address_obj.address
        }

@app.delete("/addresses/{id}")
def delete_address(id: int):
    with Session(engine) as session:
        address_obj = session.get(Address, id)
        if not address_obj:
            raise HTTPException(status_code=404, detail="Address not found")

        session.delete(address_obj)
        session.commit()

    return {"detail": f"Address with id={id} deleted successfully"}


@app.post("/addresses/{id}/sync")
async def sync_address(id: int, background_tasks: BackgroundTasks):
    """
    Trigger the incremental sync for a particular address asynchronously.
    This will return immediately, and the background task will
    handle the actual sync operation.
    """
    # First, quickly mark the address as "IN_PROGRESS" so the user knows it's being synced
    with Session(engine) as session:
        address_obj = session.get(Address, id)
        if not address_obj:
            raise HTTPException(status_code=404, detail="Address not found")

        # Mark as IN_PROGRESS (so the user sees the immediate status if they check)
        address_obj.sync_status = "IN_PROGRESS"
        session.add(address_obj)
        session.commit()

    # Add background task to do the real sync
    background_tasks.add_task(_sync_address_in_background, id)

    return {"detail": f"Sync triggered for address id={id}"}


def _sync_address_in_background(id: int):
    """
    The heavy lifting of syncing transactions runs here in the background.
    """
    with Session(engine) as session:
        address_obj = session.get(Address, id)
        if not address_obj:
            # If somehow the record was deleted before we start:
            return

        # This function is synchronous, but since it runs in a background task,
        # it won't block the HTTP request.
        sync_transactions_for_address(session, address_obj)

@app.get("/addresses/{id}")
def get_address_details(id: int):
    """
    Return the basic address info + currently stored balance.
    """
    with Session(engine) as session:
        address_obj = session.get(Address, id)
        if not address_obj:
            raise HTTPException(status_code=404, detail="Address not found")

        # Count how many transactions belong to this address
        tx_count_stmt = select(func.count(Transaction.id)).where(Transaction.address_id == address_obj.id)
        transaction_count = session.exec(tx_count_stmt).one()

        return {
            "id": address_obj.id,
            "address": address_obj.address,
            "balance": address_obj.balance,
            "transaction_count": transaction_count,  # <-- new field
            "sync_status": address_obj.sync_status,
            "last_synced_at": address_obj.last_synced_at
        }

@app.get("/addresses/{id}/transactions")
def get_address_transactions(
    id: int,
    limit: int = Query(10, gt=0),
    offset: int = Query(0, ge=0)
):
    """
    Paginated retrieval of transactions from the Transaction table,
    ordered by newest first.
    """
    with Session(engine) as session:
        address_obj = session.get(Address, id)
        if not address_obj:
            raise HTTPException(status_code=404, detail="Address not found")

        tx_stmt = (
            select(Transaction)
            .where(Transaction.address_id == address_obj.id)
            .order_by(Transaction.timestamp.desc())  # <-- descending
            .offset(offset)
            .limit(limit)
        )
        txs = session.exec(tx_stmt).all()

        # Count total transactions for this address
        total_stmt = select(Transaction).where(Transaction.address_id == address_obj.id)
        total_txs = len(session.exec(total_stmt).all())

        transactions_data = [
            {
                "id": tx.id,
                "tx_hash": tx.tx_hash,
                "amount": tx.amount,
                "timestamp": tx.timestamp
            }
            for tx in txs
        ]

        return {
            "id": address_obj.id,
            "address": address_obj.address,
            "limit": limit,
            "offset": offset,
            "total_transactions": total_txs,
            "transactions": transactions_data
        }