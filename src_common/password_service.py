# password_service.py
"""
FR-DB-001: Password hashing service using bcrypt
"""

from passlib.context import CryptContext
from passlib.hash import bcrypt
from cryptography.fernet import Fernet
import os
import random
import string


class PasswordService:
    """Service for password hashing and verification"""
    
    def __init__(self):
        """Initialize password context with bcrypt"""
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12  # Good balance of security and performance
        )
    
    def hash_password(self, password: str) -> str:
        """
        Hash a plain text password using bcrypt
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain text password against a hash
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Stored password hash
            
        Returns:
            True if password matches hash
        """
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def needs_update(self, hashed_password: str) -> bool:
        """
        Check if password hash needs updating (deprecated scheme)
        
        Args:
            hashed_password: Stored password hash
            
        Returns:
            True if hash should be updated
        """
        return self.pwd_context.needs_update(hashed_password)
    
    def generate_token(self, length: int = 32) -> str:
        """
        Generate a secure random token
        
        Args:
            length: Token length in bytes
            
        Returns:
            Hex-encoded secure random token
        """
        return os.urandom(length).hex()


class TokenEncryption:
    """Service for token encryption using Fernet"""
    
    def __init__(self, key: str = None):
        """
        Initialize token encryption
        
        Args:
            key: Base64-encoded Fernet key (generated if None)
        """
        if key:
            self.fernet = Fernet(key.encode() if isinstance(key, str) else key)
        else:
            # Generate a new key - should be stored securely
            key = Fernet.generate_key()
            self.fernet = Fernet(key)
            print(f"Generated Fernet key: {key.decode()}")
            print("Store this key securely in FERNET_KEY environment variable!")
    
    def encrypt_token(self, token: str) -> str:
        """
        Encrypt a token
        
        Args:
            token: Plain text token
            
        Returns:
            Encrypted token (base64 encoded)
        """
        return self.fernet.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt a token
        
        Args:
            encrypted_token: Encrypted token (base64 encoded)
            
        Returns:
            Plain text token
        """
        return self.fernet.decrypt(encrypted_token.encode()).decode()
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key"""
        return Fernet.generate_key().decode()