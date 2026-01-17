import re

HUMAN_READABLE_SIZE_TO_BYTES = {"TB": 1024 ** 4, "GB": 1024 ** 3, "MB": 1024 ** 2, "KB": 1024 ** 1}


def human_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024


def from_human_size_to_bytes(size: str) -> int:
    value, unit = re.match(r"(\d+)([ A-Za-z]+)", size).groups()
    if not value:
        raise ValueError("size must be in format: number [TB|GB|MB|KB]")
    value = int(value)
    unit = unit.upper().strip()

    if not unit:
        return value
    if unit in HUMAN_READABLE_SIZE_TO_BYTES:
        return value * HUMAN_READABLE_SIZE_TO_BYTES[unit]
    raise ValueError("size must be in format: number [TB|GB|MB|KB]")
