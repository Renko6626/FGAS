import os
from pathlib import Path

VERSION = os.getenv('FGAS_VERSION', 'dev')

def _read_git_sha():
    git = Path(__file__).resolve().parents[1] / '.git'
    try:
        head = (git / 'HEAD').read_text().strip()
        if head.startswith('ref: '):
            ref = head[5:]
            reference = git / ref
            if reference.is_file(): return reference.read_text().strip()[:12]
            for line in (git / 'packed-refs').read_text().splitlines():
                if line.endswith(' ' + ref): return line.split()[0][:12]
            return None
        return head[:12] or None
    except OSError:
        return None

def git_sha():
    return os.getenv('FGAS_GIT_SHA', '').strip()[:12] or _read_git_sha()
