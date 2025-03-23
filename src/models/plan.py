from dataclasses import dataclass
from typing import Optional, List, Dict
import json
import os
from pathlib import Path


@dataclass
class Plan:
    """Represents a VPN service plan."""
    id: str
    name: str
    traffic_limit: int  # GB
    expiration_days: int
    price: float
    currency: str = "USD"
    description: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert plan to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "traffic_limit": self.traffic_limit,
            "expiration_days": self.expiration_days,
            "price": self.price,
            "currency": self.currency,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Plan':
        """Create a Plan from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            traffic_limit=data["traffic_limit"],
            expiration_days=data["expiration_days"],
            price=data["price"],
            currency=data.get("currency", "USD"),
            description=data.get("description")
        )


class PlanManager:
    """Manages VPN service plans."""
    
    def __init__(self, file_path: Optional[str] = None):
        """Initialize the plan manager."""
        if file_path is None:
            # Default path is data/plans.json in project root
            root_dir = Path(__file__).parent.parent.parent
            self.file_path = os.path.join(root_dir, "data", "plans.json")
        else:
            self.file_path = file_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
        # Load plans or create default ones if file doesn't exist
        if not os.path.exists(self.file_path):
            self.plans = self._create_default_plans()
            self.save_plans()
        else:
            self.plans = self._load_plans()
    
    def _create_default_plans(self) -> List[Plan]:
        """Create default plans."""
        return [
            Plan(
                id="basic",
                name="Basic Plan",
                traffic_limit=50,
                expiration_days=30,
                price=5.00,
                description="50GB traffic for 30 days"
            ),
            Plan(
                id="standard",
                name="Standard Plan",
                traffic_limit=100,
                expiration_days=30,
                price=9.00,
                description="100GB traffic for 30 days"
            ),
            Plan(
                id="premium",
                name="Premium Plan",
                traffic_limit=200,
                expiration_days=30,
                price=15.00,
                description="200GB traffic for 30 days"
            )
        ]
    
    def _load_plans(self) -> List[Plan]:
        """Load plans from file."""
        try:
            with open(self.file_path, 'r') as f:
                plans_data = json.load(f)
                return [Plan.from_dict(plan_data) for plan_data in plans_data]
        except (json.JSONDecodeError, FileNotFoundError):
            # If file is corrupt or missing, create default plans
            return self._create_default_plans()
    
    def save_plans(self) -> None:
        """Save plans to file."""
        with open(self.file_path, 'w') as f:
            json.dump([plan.to_dict() for plan in self.plans], f, indent=2)
    
    def get_all_plans(self) -> List[Plan]:
        """Get all available plans."""
        return self.plans
    
    def get_plan_by_id(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by its ID."""
        for plan in self.plans:
            if plan.id == plan_id:
                return plan
        return None
    
    def add_plan(self, plan: Plan) -> None:
        """Add a new plan."""
        # Check if plan with same ID already exists
        for i, existing_plan in enumerate(self.plans):
            if existing_plan.id == plan.id:
                # Replace existing plan
                self.plans[i] = plan
                break
        else:
            # No existing plan with this ID, add new one
            self.plans.append(plan)
        
        self.save_plans()
    
    def remove_plan(self, plan_id: str) -> bool:
        """Remove a plan by ID. Returns True if plan was removed."""
        for i, plan in enumerate(self.plans):
            if plan.id == plan_id:
                self.plans.pop(i)
                self.save_plans()
                return True
        return False
