"""
CLI script to create a new TogoLM API key.

The plain-text key is shown ONCE at creation — it is never stored.
Only its SHA-256 hash is saved in the api_keys table.

Usage:
    python scripts/create_api_key.py --owner-name "Dev Togo" --owner-email "dev@example.com" --plan dev
    python scripts/create_api_key.py --owner-name "Ministère" --plan institution

Plans: free (100 req/day) | dev (1 000 req/day) | institution (100 000 req/day)
"""

import argparse
import hashlib
import os
import secrets
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "togolm"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD") or None,
    )


def create_key(owner_name: str, owner_email: str | None, plan: str) -> str:
    raw_key = "tlm_" + secrets.token_hex(32)  # 68-char key with prefix
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_keys (key_hash, owner_name, owner_email, plan)
                VALUES (%s, %s, %s, %s)
                RETURNING id::text, created_at
                """,
                (key_hash, owner_name, owner_email, plan),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("  TogoLM API Key Created")
    print("=" * 60)
    print(f"  Owner  : {owner_name}")
    print(f"  Email  : {owner_email or '—'}")
    print(f"  Plan   : {plan}")
    print(f"  Key ID : {row[0]}")
    print(f"  Created: {row[1]}")
    print()
    print("  API KEY (shown once — save it now):")
    print(f"  {raw_key}")
    print("=" * 60 + "\n")

    return raw_key


def revoke_key(key_id: str) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE api_keys SET is_active = FALSE WHERE id = %s RETURNING owner_name",
                (key_id,),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    if row:
        print(f"Key {key_id} revoked (owner: {row[0]})")
    else:
        print(f"Key {key_id} not found", file=sys.stderr)
        sys.exit(1)


def list_keys() -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, owner_name, owner_email, plan, is_active, created_at, last_used
                FROM api_keys ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("No API keys found.")
        return

    print(f"\n{'ID':<38} {'Owner':<20} {'Plan':<12} {'Active':<8} {'Last used'}")
    print("-" * 100)
    for r in rows:
        last = r[6].strftime("%Y-%m-%d") if r[6] else "never"
        active = "yes" if r[4] else "no"
        print(f"{r[0]!s:<38} {(r[1] or '-'):<20} {r[3]:<12} {active:<8} {last}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage TogoLM API keys")
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="Create a new API key")
    p_create.add_argument("--owner-name", required=True)
    p_create.add_argument("--owner-email", default=None)
    p_create.add_argument("--plan", choices=["free", "dev", "institution"], default="dev")

    # revoke
    p_revoke = sub.add_parser("revoke", help="Revoke an API key by ID")
    p_revoke.add_argument("key_id")

    # list
    sub.add_parser("list", help="List all API keys")

    args = parser.parse_args()

    if args.command == "create":
        create_key(args.owner_name, args.owner_email, args.plan)
    elif args.command == "revoke":
        revoke_key(args.key_id)
    elif args.command == "list":
        list_keys()
    else:
        parser.print_help()
