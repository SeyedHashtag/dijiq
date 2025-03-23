from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import os
from pathlib import Path


@dataclass
class Purchase:
    """Represents a VPN plan purchase."""
    purchase_id: str
    telegram_id: int
    plan_id: str
    amount: float
    currency: str
    payment_id: Optional[str]
    status: str  # "pending", "completed", "cancelled", "failed"
    created_at: str
    completed_at: Optional[str] = None
    vpn_username: Optional[str] = None
    vpn_password: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert purchase to dictionary."""
        return {
            "purchase_id": self.purchase_id,
            "telegram_id": self.telegram_id,
            "plan_id": self.plan_id,
            "amount": self.amount,
            "currency": self.currency,
            "payment_id": self.payment_id,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "vpn_username": self.vpn_username,
            "vpn_password": self.vpn_password
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Purchase':
        """Create a Purchase from dictionary."""
        return cls(
            purchase_id=data["purchase_id"],
            telegram_id=data["telegram_id"],
            plan_id=data["plan_id"],
            amount=data["amount"],
            currency=data["currency"],
            payment_id=data.get("payment_id"),
            status=data["status"],
            created_at=data["created_at"],
            completed_at=data.get("completed_at"),
            vpn_username=data.get("vpn_username"),
            vpn_password=data.get("vpn_password")
        )


class PurchaseManager:
    """Manages VPN service purchases."""
    
    def __init__(self, file_path: Optional[str] = None):
        """Initialize the purchase manager."""
        if file_path is None:
            # Default path is data/purchases.json in project root
            root_dir = Path(__file__).parent.parent.parent
            self.file_path = os.path.join(root_dir, "data", "purchases.json")
        else:
            self.file_path = file_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
        # Create empty purchases file if it doesn't exist
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump([], f)
        
        self.purchases = self._load_purchases()
    
    def _load_purchases(self) -> List[Purchase]:
        """Load purchases from file."""
        try:
            with open(self.file_path, 'r') as f:
                purchases_data = json.load(f)
                return [Purchase.from_dict(purchase_data) for purchase_data in purchases_data]
        except (json.JSONDecodeError, FileNotFoundError):
            # If file is corrupt or missing, create empty list
            return []
    
    def save_purchases(self) -> None:
        """Save purchases to file."""
        with open(self.file_path, 'w') as f:
            json.dump([purchase.to_dict() for purchase in self.purchases], f, indent=2)
    
    def add_purchase(self, purchase: Purchase) -> None:
        """Add a new purchase."""
        self.purchases.append(purchase)
        self.save_purchases()
    
    def get_purchase_by_id(self, purchase_id: str) -> Optional[Purchase]:
        """Get a purchase by its ID."""
        for purchase in self.purchases:
            if purchase.purchase_id == purchase_id:
                return purchase
        return None
    
    def update_purchase(self, purchase: Purchase) -> bool:
        """Update an existing purchase. Returns True if successful."""
        for i, existing_purchase in enumerate(self.purchases):
            if existing_purchase.purchase_id == purchase.purchase_id:
                self.purchases[i] = purchase
                self.save_purchases()
                return True
        return False
    
    def get_user_purchases(self, telegram_id: int) -> List[Purchase]:
        """Get all purchases for a user."""
        return [p for p in self.purchases if p.telegram_id == telegram_id]
    
    def get_pending_purchases(self) -> List[Purchase]:
        """Get all pending purchases."""
        return [p for p in self.purchases if p.status == "pending"]
