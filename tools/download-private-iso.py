#!/usr/bin/env python3
"""Download a private, unmodified PAL Mario Kart Wii ISO for a private build.
Requires google-auth and requests; credentials come from ADC, never CLI.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import sys

SCOPE = "https://www.googleapis.com/auth/drive.readonly"
ID = re.compile(r"[A-Za-z0-9_-]{10,200}")
MAX_BYTES = 5 * 1024**3
WII_MAGIC = bytes.fromhex("5d1c9ea3")

def verify_header(header):
    if len(header) < 28 or header[:6] != b"RMCP01" or header[24:28] != WII_MAGIC:
        raise ValueError("Expected a raw Wii ISO with PAL game ID RMCP01")
    if header[7] != 0:
        raise ValueError("Expected disc revision 0; upstream verification remains mandatory")

def download(file_id, destination, expected_sha256=None):
    if not ID.fullmatch(file_id):
        raise ValueError("Invalid Drive file ID")
    if expected_sha256 and not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
        raise ValueError("Invalid expected SHA-256")
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    credentials, _ = google.auth.default(scopes=[SCOPE])
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if destination.exists() or partial.exists():
        raise ValueError("Refusing to overwrite existing ISO or partial download")
    try:
        with AuthorizedSession(credentials) as session:
            url = "https://www.googleapis.com/drive/v3/files/" + file_id
            with session.get(url, params={"fields":"size,mimeType,trashed","supportsAllDrives":"true"}, timeout=(20,60)) as response:
                if not response.ok:
                    raise ValueError(f"Drive metadata request failed (HTTP {response.status_code})")
                meta = response.json()
            size = int(meta.get("size",0))
            if meta.get("trashed") or not 28 <= size <= MAX_BYTES:
                raise ValueError("Unexpected file size or deleted file")
            digest = hashlib.sha256()
            total = 0
            with session.get(url, params={"alt":"media","supportsAllDrives":"true"}, stream=True, timeout=(20,120)) as response:
                if not response.ok:
                    raise ValueError(f"Drive download failed (HTTP {response.status_code})")
                with partial.open("xb") as output:
                    header = bytearray()
                    for block in response.iter_content(4*1024**2):
                        if not block:
                            continue
                        total += len(block)
                        if total > size or total > MAX_BYTES:
                            raise ValueError("Download exceeds advertised size")
                        if len(header)<28:
                            header.extend(block[:28-len(header)])
                            if len(header)==28:
                                verify_header(header)
                        digest.update(block)
                        output.write(block)
            if total != size:
                raise ValueError("Incomplete ISO download")
            verify_header(header)
            if expected_sha256 and digest.hexdigest().lower() != expected_sha256.lower():
                raise ValueError("ISO SHA-256 mismatch")
            partial.rename(destination)
        print("PAL ISO downloaded and header checked; upstream verification still required.")
    finally:
        partial.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    try:
        download(os.environ.get("MKW_DRIVE_FILE_ID",""),args.destination,os.environ.get("MKW_ISO_SHA256"))
    except Exception as e:
        # Do not print exceptions from network/auth libraries: may include URLs or identifiers.
        print("ISO retrieval failed: "+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr)
        return 1
    return 0

if __name__=="__main__":
    sys.exit(main())
