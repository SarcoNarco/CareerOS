from pathlib import Path


def sanitize_filename(file_name: str) -> str:
    candidate = Path(file_name).name.strip()
    if not candidate:
        return "upload.bin"
    return candidate.replace("/", "_").replace("\\", "_")

