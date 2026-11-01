"""Resolve the actual executable before spawning or hashing it on desktop CI."""
from pathlib import Path

def resolve_binary(path):
    binary=Path(path).resolve()
    if binary.is_file():
        return binary
    executable=binary.with_suffix('.exe')
    if executable.is_file():
        return executable
    raise FileNotFoundError('No executable at '+str(binary)+' or '+str(executable))
