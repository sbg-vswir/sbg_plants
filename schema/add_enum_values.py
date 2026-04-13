#!/usr/bin/env python3
"""
Add new values to existing PostgreSQL enum types in the vswir_plants schema.

Usage:
    python add_enum_values.py --secret-arn <ARN> [--env staging|production] [--dry-run] <input.yaml>

Input YAML format:
    Sensor_name:
      - "NEW_SENSOR_1"
      - "NEW_SENSOR_2"
    TAXA:
      - "Quercus robur"

Behaviour:
    - Only supports ADDING new values (ALTER TYPE ... ADD VALUE).
      PostgreSQL does not support removing or renaming enum values without
      recreating the type.
    - Values already present in the enum are skipped (idempotent).
    - Run against staging first, verify, then run against production.
    - Each ADD VALUE is executed in its own transaction — if one fails,
      earlier values in the same run are still committed (PostgreSQL
      does not allow transactional DDL for enum mutations).

Notes:
    - New enum values are appended to the end of the sort order.
      If specific ordering relative to existing values is required,
      the enum type must be recreated — this script does not do that.
    - After adding values, the QAQC lambda will pick them up automatically
      on its next warm start (load_enums is cached per container, so a
      Lambda redeploy or cold start may be needed to invalidate the cache).
    - The frontend viewConfig.js ENUMS dict is a MANUAL DUPLICATE of the
      DB enum values used for query filter dropdowns. After adding new
      enum values here, update viewConfig.js accordingly.
"""

import argparse
import json
import sys

import boto3
import psycopg2
import yaml


def get_secret(secret_arn: str, region: str = "us-west-2") -> dict:
    client = boto3.client("secretsmanager", region_name=region)
    resp = client.get_secret_value(SecretId=secret_arn)
    return json.loads(resp["SecretString"])


def get_existing_enum_values(cursor, schema: str, enum_type: str) -> set:
    cursor.execute(
        """
        SELECT e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON e.enumtypid = t.oid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = %s AND t.typname = %s
        ORDER BY e.enumsortorder
        """,
        (schema, enum_type),
    )
    return {row[0] for row in cursor.fetchall()}


def add_enum_value(cursor, schema: str, enum_type: str, value: str, dry_run: bool) -> bool:
    """
    Add a single value to an enum type. Returns True if the value was added,
    False if it already existed.
    """
    # Quote the schema-qualified type name safely
    stmt = f'ALTER TYPE {schema}."{enum_type}" ADD VALUE IF NOT EXISTS %s'
    if dry_run:
        print(f"  [DRY RUN] Would execute: ALTER TYPE {schema}.\"{enum_type}\" ADD VALUE '{value}'")
        return True
    cursor.execute(stmt, (value,))
    return True


def main():
    parser = argparse.ArgumentParser(description="Add new values to PostgreSQL enum types")
    parser.add_argument("input", help="YAML file mapping enum_type_name → [new_values]")
    parser.add_argument("--secret-arn", required=True, help="AWS Secrets Manager ARN for DB credentials")
    parser.add_argument("--env", choices=["staging", "production"], default="staging",
                        help="Target environment (default: staging)")
    parser.add_argument("--region", default="us-west-2", help="AWS region (default: us-west-2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print SQL statements without executing them")
    args = parser.parse_args()

    # Load the YAML input
    with open(args.input) as fh:
        additions: dict[str, list[str]] = yaml.safe_load(fh)

    if not isinstance(additions, dict):
        print("ERROR: Input YAML must be a mapping of enum_type → [values]", file=sys.stderr)
        sys.exit(1)

    # Connect to the database
    creds = get_secret(args.secret_arn, region=args.region)
    conn = psycopg2.connect(
        host=creds["host"],
        port=creds.get("port", 5432),
        dbname=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
        connect_timeout=10,
    )
    conn.autocommit = True  # Required: ALTER TYPE ... ADD VALUE cannot run inside a transaction block

    schema = "vswir_plants"
    print(f"Connected to {creds['host']}/{creds['dbname']} (env={args.env})")
    if args.dry_run:
        print("[DRY RUN mode — no changes will be made]\n")

    total_added   = 0
    total_skipped = 0
    total_errors  = 0

    with conn.cursor() as cur:
        for enum_type, new_values in additions.items():
            print(f"\nEnum type: {enum_type}")
            existing = get_existing_enum_values(cur, schema, enum_type)

            if not existing and not args.dry_run:
                print(f"  WARNING: enum type '{enum_type}' not found in schema '{schema}' — skipping")
                total_errors += 1
                continue

            for value in new_values:
                if value in existing:
                    print(f"  SKIP  '{value}' (already exists)")
                    total_skipped += 1
                    continue
                try:
                    add_enum_value(cur, schema, enum_type, value, dry_run=args.dry_run)
                    print(f"  ADD   '{value}'")
                    total_added += 1
                except Exception as exc:
                    print(f"  ERROR adding '{value}': {exc}", file=sys.stderr)
                    total_errors += 1

    conn.close()

    print(f"\nDone. Added: {total_added}, Skipped: {total_skipped}, Errors: {total_errors}")
    if total_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
