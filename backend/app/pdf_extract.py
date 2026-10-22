"""Isolated bounded PDF extraction. Invoked as a subprocess, never imports the app DB."""

import io
import json
import resource
import sys
from pypdf import PdfReader

resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
try:
    raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024 or not raw.startswith(b"%PDF-"):
        raise ValueError()
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted or len(reader.pages) > 30:
        raise ValueError()
    content = "\n\n".join((page.extract_text() or "")[:12000] for page in reader.pages)[:100000]
    print(json.dumps({"text": content}))
except Exception:
    print(json.dumps({"error": "Use an unencrypted PDF with extractable text and at most 30 pages."}))
    sys.exit(1)
