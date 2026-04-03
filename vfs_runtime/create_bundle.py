import os
import struct
from typing import Callable
import zlib
from collections.abc import Callable

from . import conf


def compress_file(path: str) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    return zlib.compress(data)

def gather_files(root_dir: str):
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            full_path = os.path.join(dirpath, f)
            rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
            files.append((rel_path, full_path))
    return files

def make_bundle(root_dir: str, output_file: str, encryption_function: Callable|None = None):
    files = gather_files(root_dir)

    blob_data = bytearray()
    index_entries = []

    # write file data sequentially
    offset = 0
    for rel_path, full_path in files:
        data = compress_file(full_path)
        blob_data.extend(data)
        size = len(data)
        index_entries.append((rel_path, offset, size))
        offset += size

    # write index at the end
    bundle = bytearray()
    bundle.extend(blob_data)

    # index
    bundle.extend(conf.BUNDLE_MAGIC_BYTES)
    bundle.extend(struct.pack("<I", len(index_entries)))

    for path, off, size in index_entries:
        path_bytes = path.encode()
        bundle.extend(struct.pack("<H", len(path_bytes)))  # path length
        bundle.extend(path_bytes)
        bundle.extend(struct.pack("<II", off, size))  # offset + size

    with open(output_file, "wb") as f:
        if conf.encryption_function or encryption_function:
            try:
                print(f"[make_bundle] USING ENCRYPTION FUNCTION")
                ef = conf.encryption_function or encryption_function
                bundle = ef(bytes(bundle))
            except Exception as e:
                print(f"[make_bundle] error while encrypting bundle:\n{e}")
                return
        f.write(bundle)

    print(f"Bundle created: {output_file} ({len(bundle)} bytes, {len(files)} files)")
