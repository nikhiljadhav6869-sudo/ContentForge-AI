"""Create local Compose configuration without printing or overwriting secrets."""
from pathlib import Path
import secrets
import os
root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    print('Existing .env preserved. Edit it to change local configuration.')
else:
    content = (root / '.env.example').read_text().replace('POSTGRES_PASSWORD=\n', 'POSTGRES_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output: output.write(content)
    print('Created private .env with a generated local database password.')
