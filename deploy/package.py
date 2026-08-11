"""Quick packaging using Python (best Unicode support)
Usage: python package.py
"""
import os
import sys
import shutil
import tarfile
import tempfile
from pathlib import Path

# Project root - uses raw string for Chinese path support
PROJECT_ROOT = Path(r"z:\soft-RED\hermes\开发软件\渠道项目登记")

# Directories to exclude
EXCLUDE_DIRS = {
    "deploy", "node_modules", ".venv", "__pycache__", ".git",
    "dist", "static", ".docx_lib", "channel_code",
    "frontend/node_modules", "backend/.venv",
}

# File patterns to exclude
EXCLUDE_FILE_PATTERNS = {
    "*.pyc", "*.bak", "*.log", "*.zip", "*.docx",
    "*.tar.gz", "*.tmp", "*.db",
    "data.db", "data.db.bak*",
    "uvicorn.out.log", "uvicorn.err.log", "app_debug.log",
}


def should_exclude_dir(dirname: str, parent_rel: str) -> bool:
    """Check if directory should be excluded"""
    full_rel = f"{parent_rel}/{dirname}" if parent_rel else dirname
    if dirname in EXCLUDE_DIRS:
        return True
    if full_rel in EXCLUDE_DIRS:
        return True
    return False


def should_exclude_file(filename: str) -> bool:
    """Check if file should be excluded"""
    from fnmatch import fnmatch
    for pattern in EXCLUDE_FILE_PATTERNS:
        if fnmatch(filename, pattern):
            return True
    return False


def collect_files(root: Path):
    """Recursively collect files to include"""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Compute relative path for filtering
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")

        # Filter dirs in-place (prevents descending)
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d, rel_dir)]

        # Filter files
        for f in filenames:
            if should_exclude_file(f):
                continue
            full_path = Path(dirpath) / f
            files.append(full_path)

    return files


def main():
    print(f"[INFO] Source: {PROJECT_ROOT}")

    if not PROJECT_ROOT.exists():
        print(f"[ERROR] Project root not found: {PROJECT_ROOT}")
        sys.exit(1)

    # Collect files
    files = collect_files(PROJECT_ROOT)
    print(f"[INFO] Found {len(files)} files to package")

    if len(files) == 0:
        print("[ERROR] No files found! Check directory structure.")
        sys.exit(1)

    # Create temp staging dir
    staging = Path(tempfile.mkdtemp(prefix="channel-stage-"))
    print(f"[INFO] Staging at: {staging}")

    # Copy files
    for src in files:
        rel = src.relative_to(PROJECT_ROOT)
        dst = staging / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Show stats
    total_size = sum(f.stat().st_size for f in files) / (1024 * 1024)
    print(f"[INFO] Total size: {total_size:.2f} MB")

    # Create tarball
    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d%H%M%S")
    tar_path = Path(tempfile.gettempdir()) / f"channel-project-{timestamp}.tar.gz"

    print(f"[INFO] Creating tarball: {tar_path}")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(staging, arcname=".")

    tar_size = tar_path.stat().st_size / (1024 * 1024)
    print(f"[INFO] Tarball size: {tar_size:.2f} MB")

    # Cleanup staging
    shutil.rmtree(staging, ignore_errors=True)

    print()
    print(f"[INFO] Ready to upload: {tar_path}")
    print()
    print("Upload command:")
    print(f'  sshpass -p "PASSWORD" scp "{tar_path}" admin001@172.16.10.92:/tmp/channel-project.tar.gz')


if __name__ == "__main__":
    main()