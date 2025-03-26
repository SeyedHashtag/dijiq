from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import Optional


class PaymentStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class Purchase:
    user_id: int
    amount: float
    payment_id: str
    status: PaymentStatus = PaymentStatus.PENDING
    invoice_url: Optional[str] = None
    created_at: str = None
    completed_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self):
        """Convert purchase to dictionary."""
        return {
            "user_id": self.user_id,
            "amount": self.amount,
            "payment_id": self.payment_id,
            "status": self.status.value,
            "invoice_url": self.invoice_url,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a Purchase object from dictionary."""
        return cls(
            user_id=data["user_id"],
            amount=data["amount"],
            payment_id=data["payment_id"],
            status=PaymentStatus(data["status"]),
            invoice_url=data.get("invoice_url"),
            created_at=data["created_at"],
            completed_at=data.get("completed_at")
        )
    
    def mark_as_paid(self):
        """Mark the purchase as completed."""
        self.status = PaymentStatus.CONFIRMED
        self.completed_at = datetime.now().isoformat()
    
    def mark_as_failed(self):
        """Mark the purchase as failed."""
        self.status = PaymentStatus.FAILED
    
    def mark_as_expired(self):
        """Mark the purchase as expired."""
        self.status = PaymentStatus.EXPIRED
