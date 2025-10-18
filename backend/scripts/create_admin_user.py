"""
Script to create the first admin user for the GallagherMHP platform.

Usage:
    python scripts/create_admin_user.py

Environment Variables Required:
    DATABASE_URL - PostgreSQL connection string
    REDIS_URL - Redis connection string
    SECRET_KEY - Application secret key
"""

import asyncio
import sys
from getpass import getpass

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password, UserRole
from app.models.auth import User


async def create_admin_user():
    """Create the first admin user interactively."""
    print("=" * 60)
    print("GallagherMHP Admin User Creation")
    print("=" * 60)
    print()
    
    # Get user input
    username = input("Enter admin username [default: admin]: ").strip() or "admin"
    email = input("Enter admin email: ").strip()
    
    if not email:
        print("Error: Email is required")
        sys.exit(1)
    
    full_name = input("Enter admin full name [optional]: ").strip() or None
    
    # Get password securely
    while True:
        password = getpass("Enter admin password: ")
        password_confirm = getpass("Confirm admin password: ")
        
        if not password:
            print("Error: Password cannot be empty")
            continue
        
        if password != password_confirm:
            print("Error: Passwords do not match. Please try again.")
            continue
        
        if len(password) < 8:
            print("Warning: Password should be at least 8 characters")
            confirm = input("Use this password anyway? [y/N]: ").lower()
            if confirm != 'y':
                continue
        
        break
    
    print()
    print("Creating admin user...")
    
    try:
        async with AsyncSessionLocal() as db:
            # Check if admin already exists
            from sqlalchemy import select
            stmt = select(User).where(User.username == username)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"Error: User '{username}' already exists")
                sys.exit(1)
            
            # Create admin user
            admin = User(
                username=username,
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                role=UserRole.ADMIN,
                is_active=True,
            )
            
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            
            print()
            print("✅ Admin user created successfully!")
            print()
            print(f"Username: {admin.username}")
            print(f"Email: {admin.email}")
            print(f"Role: {admin.role}")
            print(f"ID: {admin.id}")
            print()
            print("You can now login at: POST /api/v1/auth/login")
            print()
    
    except Exception as e:
        print(f"Error creating admin user: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(create_admin_user())

