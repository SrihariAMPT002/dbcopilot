#!/usr/bin/env python3
"""
Generate a fresh Fernet encryption key for use in .env
"""

from cryptography.fernet import Fernet

key = Fernet.generate_key().decode()
print("\n🔑 Generated Fernet Key:")
print(f"\n   {key}\n")
print("Add this to your .env file:")
print(f"   ENCRYPTION_KEY={key}\n")
print("  Keep this key safe — losing it means losing access to stored credentials.\n")
