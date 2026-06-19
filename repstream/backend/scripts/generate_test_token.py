"""
Generate a test JWT token for RepStream API testing.

Usage:
    python scripts/generate_test_token.py
    python scripts/generate_test_token.py --rep-id REP001 --territory TERR-001

The printed token can be pasted directly into Swagger UI (Authorize button)
or used as `Authorization: Bearer <token>` in curl / Postman / the frontend.
"""
import argparse
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.utils.auth import create_access_token


def main():
    parser = argparse.ArgumentParser(description="Generate a RepStream test JWT token")
    parser.add_argument("--rep-id",    default="REP001",   help="Rep ID claim (default: REP001)")
    parser.add_argument("--territory", default="TERR-001", help="Territory ID claim (default: TERR-001)")
    parser.add_argument("--email",     default="rahulpandarp1998@gmail.com", help="Email claim")
    parser.add_argument("--name",      default="Rahul Pandarp", help="Full name claim")
    parser.add_argument("--hours",     default=48, type=int, help="Token lifetime in hours (default: 48)")
    args = parser.parse_args()

    token = create_access_token(
        data={
            "sub": args.rep_id,
            "territory_id": args.territory,
            "email": args.email,
            "full_name": args.name,
            "role": "rep",
        },
        expires_delta=timedelta(hours=args.hours),
    )

    print("\n" + "=" * 60)
    print("  RepStream Test JWT Token")
    print("=" * 60)
    print(f"  Rep ID    : {args.rep_id}")
    print(f"  Territory : {args.territory}")
    print(f"  Expires   : {args.hours} hours from now")
    print("=" * 60)
    print("\nToken (copy everything below this line):\n")
    print(token)
    print("\n" + "=" * 60)
    print("Usage in Swagger UI (/api/docs):")
    print('  Click "Authorize" → paste the token → click Authorize')
    print("\nUsage in curl:")
    print(f'  curl -H "Authorization: Bearer {token[:30]}..." http://localhost:8000/api/v1/territory/summary')
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
