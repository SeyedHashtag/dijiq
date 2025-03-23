import sqlite3
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = None):
        """Initialize database connection."""
        if db_path is None:
            # Use default path in data directory
            data_dir = Path(__file__).parent.parent.parent / 'data'
            if not data_dir.exists():
                data_dir.mkdir(parents=True)
            db_path = str(data_dir / "dijiq.db")
        
        self.db_path = db_path
        self.conn = None
        self.create_tables()
    
    def _get_connection(self):
        """Get SQLite connection, creating if needed."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def create_tables(self):
        """Create necessary database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create Plans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            traffic_limit INTEGER NOT NULL,
            duration_days INTEGER NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USDT',
            active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create Payments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            payment_id TEXT UNIQUE,
            payment_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES plans (id)
        )
        ''')
        
        # Create Client Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    # Plan management methods
    def add_plan(self, name: str, description: str, traffic_limit: int, 
                 duration_days: int, price: float, currency: str = 'USDT') -> int:
        """Add a new plan to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO plans (name, description, traffic_limit, duration_days, price, currency)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, traffic_limit, duration_days, price, currency))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_plan(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """Get a plan by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM plans WHERE id = ?', (plan_id,))
        plan = cursor.fetchone()
        
        if plan:
            return dict(plan)
        return None
    
    def get_all_plans(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all plans, optionally filtered by active status."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if active_only:
            cursor.execute('SELECT * FROM plans WHERE active = 1 ORDER BY price ASC')
        else:
            cursor.execute('SELECT * FROM plans ORDER BY price ASC')
        
        plans = cursor.fetchall()
        return [dict(plan) for plan in plans]
    
    def update_plan(self, plan_id: int, **kwargs) -> bool:
        """Update a plan's attributes."""
        if not kwargs:
            return False
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build the SQL update statement dynamically
        fields = []
        values = []
        
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        # Add plan_id to values
        values.append(plan_id)
        
        sql = f"UPDATE plans SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(sql, values)
        
        conn.commit()
        return cursor.rowcount > 0
    
    def delete_plan(self, plan_id: int) -> bool:
        """Delete a plan (or mark as inactive)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Mark as inactive instead of deleting (soft delete)
        cursor.execute('UPDATE plans SET active = 0 WHERE id = ?', (plan_id,))
        
        conn.commit()
        return cursor.rowcount > 0
    
    # Payment methods
    def create_payment(self, user_id: int, plan_id: int, amount: float, 
                      currency: str, status: str = 'pending') -> int:
        """Create a new payment record."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO payments (user_id, plan_id, amount, currency, status)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, plan_id, amount, currency, status))
        
        conn.commit()
        return cursor.lastrowid
    
    def update_payment(self, payment_id: int, payment_data: Dict[str, Any]) -> bool:
        """Update payment with data from payment processor."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Update payment with external payment ID and URL
        if 'external_id' in payment_data:
            cursor.execute('''
            UPDATE payments 
            SET payment_id = ?, payment_url = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''', (payment_data['external_id'], payment_data.get('payment_url', ''), 
                  payment_data.get('status', 'pending'), payment_id))
        else:
            cursor.execute('''
            UPDATE payments 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''', (payment_data.get('status', 'pending'), payment_id))
        
        conn.commit()
        return cursor.rowcount > 0
    
    def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """Get payment details by internal ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM payments WHERE id = ?', (payment_id,))
        payment = cursor.fetchone()
        
        if payment:
            return dict(payment)
        return None
    
    def get_payment_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Get payment details by external payment processor ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM payments WHERE payment_id = ?', (external_id,))
        payment = cursor.fetchone()
        
        if payment:
            return dict(payment)
        return None
    
    def get_user_payments(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get a user's payment history."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT p.*, pl.name as plan_name, pl.traffic_limit, pl.duration_days
        FROM payments p
        JOIN plans pl ON p.plan_id = pl.id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
        LIMIT ?
        ''', (user_id, limit))
        
        payments = cursor.fetchall()
        return [dict(payment) for payment in payments]
    
    # Client management methods
    def add_client(self, telegram_id: int, username: str = None, 
                  first_name: str = None, last_name: str = None) -> int:
        """Add a new client or update if exists."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if client exists
        cursor.execute('SELECT id FROM clients WHERE telegram_id = ?', (telegram_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update client information
            cursor.execute('''
            UPDATE clients 
            SET username = ?, first_name = ?, last_name = ?, is_active = 1
            WHERE telegram_id = ?
            ''', (username, first_name, last_name, telegram_id))
            client_id = existing['id']
        else:
            # Create new client
            cursor.execute('''
            INSERT INTO clients (telegram_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ''', (telegram_id, username, first_name, last_name))
            client_id = cursor.lastrowid
        
        conn.commit()
        return client_id
    
    def get_client(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get client details by Telegram ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM clients WHERE telegram_id = ?', (telegram_id,))
        client = cursor.fetchone()
        
        if client:
            return dict(client)
        return None
