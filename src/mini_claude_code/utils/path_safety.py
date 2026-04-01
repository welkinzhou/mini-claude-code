from pathlib import Path


def get_workdir() -> Path:
    return Path.cwd()


def safe_path(p: str) -> Path:
    workdir = get_workdir()
    path = (workdir / p).resolve()
    if not path.is_relative_to(workdir):
        raise ValueError(f"Path escapes workspace: {p}")
    return path
