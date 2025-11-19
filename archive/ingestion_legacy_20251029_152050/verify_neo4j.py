#!/usr/bin/env python3
"""
verify_neo4j.py - Verify Neo4j connectivity with environment credentials
"""
import os
import sys
import time

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: neo4j driver not installed. Run: pip install neo4j", file=sys.stderr)
    sys.exit(1)


def verify_connection(uri: str, user: str, password: str, max_retries: int = 10):
    """Verify Neo4j connection with retries."""
    print(f"Connecting to Neo4j at {uri}...")
    print(f"User: {user}")
    print(f"Password: {'*' * len(password)}")

    for attempt in range(1, max_retries + 1):
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))

            with driver.session() as session:
                result = session.run("RETURN 'Connection successful!' AS result")
                message = result.single()["result"]
                print(f"\n✓ {message}")
                print(f"  Attempt: {attempt}/{max_retries}")
                print(f"  URI: {uri}")
                print(f"  User: {user}")

            driver.close()
            return True

        except Exception as e:
            print(f"Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                print(f"Retrying in 3 seconds...")
                time.sleep(3)
            else:
                print(f"\n✗ Connection failed after {max_retries} attempts")
                return False


def main():
    # Get credentials from environment
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')

    # Try both internal and external URIs
    uris = [
        "bolt://n8n_TTRPG_neo4j:7687",  # Internal (from container)
        "bolt://localhost:9005"          # External (from host)
    ]

    for uri in uris:
        print(f"\n{'=' * 60}")
        print(f"Testing: {uri}")
        print('=' * 60)

        if verify_connection(uri, neo4j_user, neo4j_password):
            print(f"\n✓ Neo4j is healthy and configured correctly")
            sys.exit(0)
        else:
            print(f"\n✗ Failed to connect to {uri}")

    print(f"\n✗ All connection attempts failed")
    sys.exit(1)


if __name__ == '__main__':
    main()
