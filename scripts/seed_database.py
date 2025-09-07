#!/usr/bin/env python3
"""
FR-DB-001: Database Seeding Script
Creates default roles, permissions, and admin user
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
env_file = Path(__file__).parent.parent / "env" / "dev" / "config" / ".env"
if env_file.exists():
    load_dotenv(env_file)

from src_common.db import get_engine, get_session
from src_common.models_simple import Role, Permission, RolePermission, User, UserRole_
from src_common.password_service import PasswordService


def create_default_permissions():
    """Create default system permissions"""
    permissions_data = [
        # User management permissions
        {"name": "users.read", "resource": "users", "action": "read", "description": "View user information"},
        {"name": "users.write", "resource": "users", "action": "write", "description": "Create and update users"},
        {"name": "users.delete", "resource": "users", "action": "delete", "description": "Delete users"},
        {"name": "users.admin", "resource": "users", "action": "admin", "description": "Full user administration"},
        
        # Role management permissions
        {"name": "roles.read", "resource": "roles", "action": "read", "description": "View roles"},
        {"name": "roles.write", "resource": "roles", "action": "write", "description": "Create and update roles"},
        {"name": "roles.delete", "resource": "roles", "action": "delete", "description": "Delete roles"},
        {"name": "roles.assign", "resource": "roles", "action": "assign", "description": "Assign roles to users"},
        
        # Game management permissions
        {"name": "games.read", "resource": "games", "action": "read", "description": "View games"},
        {"name": "games.write", "resource": "games", "action": "write", "description": "Create and update games"},
        {"name": "games.delete", "resource": "games", "action": "delete", "description": "Delete games"},
        {"name": "games.manage", "resource": "games", "action": "manage", "description": "Full game management"},
        
        # Source management permissions
        {"name": "sources.read", "resource": "sources", "action": "read", "description": "View sources"},
        {"name": "sources.write", "resource": "sources", "action": "write", "description": "Create and update sources"},
        {"name": "sources.delete", "resource": "sources", "action": "delete", "description": "Delete sources"},
        {"name": "sources.access", "resource": "sources", "action": "access", "description": "Grant source access"},
        
        # System permissions
        {"name": "system.admin", "resource": "system", "action": "admin", "description": "System administration"},
        {"name": "system.maintenance", "resource": "system", "action": "maintenance", "description": "System maintenance"},
    ]
    
    permissions = []
    with get_session() as session:
        for perm_data in permissions_data:
            # Check if permission already exists
            existing = session.query(Permission).filter_by(name=perm_data["name"]).first()
            if not existing:
                permission = Permission(**perm_data)
                session.add(permission)
                permissions.append(permission)
        
        session.commit()
        print(f"Created {len(permissions)} permissions")
    
    return permissions


def create_default_roles():
    """Create default system roles"""
    roles_data = [
        {
            "name": "admin",
            "description": "System administrator with full access",
            "is_system": True,
            "permissions": [
                "users.admin", "roles.read", "roles.write", "roles.assign",
                "games.manage", "sources.read", "sources.write", "sources.access",
                "system.admin", "system.maintenance"
            ]
        },
        {
            "name": "gm",
            "description": "Game Master role for running games",
            "is_system": True,
            "permissions": [
                "users.read", "games.read", "games.write", "games.manage",
                "sources.read", "sources.access"
            ]
        },
        {
            "name": "player",
            "description": "Player role for participating in games",
            "is_system": True,
            "permissions": [
                "users.read", "games.read", "sources.read"
            ]
        },
        {
            "name": "user",
            "description": "Basic user role",
            "is_system": True,
            "permissions": [
                "users.read", "games.read", "sources.read"
            ]
        }
    ]
    
    roles = []
    with get_session() as session:
        # Get all permissions for assignment
        all_permissions = {p.name: p for p in session.query(Permission).all()}
        
        for role_data in roles_data:
            # Check if role already exists
            existing = session.query(Role).filter_by(name=role_data["name"]).first()
            if not existing:
                # Create role
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"],
                    is_system=role_data["is_system"]
                )
                session.add(role)
                session.flush()  # Get the role ID
                
                # Assign permissions to role
                for perm_name in role_data["permissions"]:
                    if perm_name in all_permissions:
                        role_perm = RolePermission(
                            role_id=role.id,
                            permission_id=all_permissions[perm_name].id
                        )
                        session.add(role_perm)
                
                roles.append(role)
        
        session.commit()
        print(f"Created {len(roles)} roles")
    
    return roles


def create_admin_user():
    """Create default admin user"""
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@ttrpg-center.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin123!")
    
    with get_session() as session:
        # Check if admin user already exists
        existing = session.query(User).filter_by(username=admin_username).first()
        if existing:
            print(f"Admin user '{admin_username}' already exists")
            return existing
        
        # Hash password
        password_service = PasswordService()
        password_hash = password_service.hash_password(admin_password)
        
        # Create admin user
        admin_user = User(
            username=admin_username,
            email=admin_email,
            password_hash=password_hash,
            full_name="System Administrator",
            is_active=True
        )
        session.add(admin_user)
        session.flush()  # Get the user ID
        
        # Assign admin role
        admin_role = session.query(Role).filter_by(name="admin").first()
        if admin_role:
            user_role = UserRole_(
                user_id=admin_user.id,
                role_id=admin_role.id
            )
            session.add(user_role)
        
        session.commit()
        print(f"Created admin user: {admin_username}")
        
        return admin_user


def run_seed():
    """Run the complete database seeding process"""
    print("Starting database seeding...")
    
    # Create engine and ensure tables exist
    engine = get_engine()
    
    try:
        # Import SQLModel here to trigger table creation
        from src_common.models_simple import SQLModel
        SQLModel.metadata.create_all(engine)
        print("Database tables ensured")
        
        # Run seeding steps
        create_default_permissions()
        create_default_roles()
        create_admin_user()
        
        print("Database seeding completed successfully!")
        
    except Exception as e:
        print(f"Error during seeding: {e}")
        raise


if __name__ == "__main__":
    run_seed()