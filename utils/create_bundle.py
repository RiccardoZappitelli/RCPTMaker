import os
import struct
import zlib

MAGIC = b"RCPT"

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

def make_bundle(root_dir: str, output_file: str):
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
    bundle.extend(MAGIC)
    bundle.extend(struct.pack("<I", len(index_entries)))

    for path, off, size in index_entries:
        path_bytes = path.encode()
        bundle.extend(struct.pack("<H", len(path_bytes)))  # path length
        bundle.extend(path_bytes)
        bundle.extend(struct.pack("<II", off, size))  # offset + size

    with open(output_file, "wb") as f:
        f.write(bundle)

    print(f"Bundle created: {output_file} ({len(bundle)} bytes, {len(files)} files)")

# Example usage
if __name__ == "__main__":
    make_bundle("assets", "assets.bin")