from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel

class Address(SQLModel, table=True):
    """
    Address table.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    address: str = Field(nullable=False, unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Sync metadata
    sync_status: str = Field(default="UNSYNCED")  # Could be UNSYNCED, IN_PROGRESS, DONE, ERROR
    last_synced_at: Optional[datetime] = None
    last_synced_offset: int = Field(default=0)

    balance: float = Field(default=0.0)

class Transaction(SQLModel, table=True):
    """
    Simple Transaction table referencing Address by ID.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    tx_hash: str = Field(nullable=False, index=True)
    amount: float = Field(default=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    address_id: int = Field(foreign_key="address.id")