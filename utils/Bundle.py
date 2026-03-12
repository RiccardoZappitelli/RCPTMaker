import os
import struct

class Bundle:

    MAGIC = b"RCPT"
    VERSION = 1

    def __init__(self, bundle_path: str | None = None):
        self.bundle_path = bundle_path
        self.index = {}

        if bundle_path:
            self._load_index()

    def pack(self, root_dir: str, output_file: str):
        files = []

        for root, _, filenames in os.walk(root_dir):
            for name in filenames:
                path = os.path.join(root, name)
                if os.path.getsize(path) == 0:
                    continue
                rel = os.path.relpath(path, root_dir)
                files.append((path, rel))

        with open(output_file, "wb") as out:

            out.write(self.MAGIC)
            out.write(struct.pack("<B", self.VERSION))
            out.write(struct.pack("<I", len(files)))

            for real_path, rel_path in files:

                rel_bytes = rel_path.encode("utf-8")
                size = os.path.getsize(real_path)

                out.write(struct.pack("<H", len(rel_bytes)))
                out.write(rel_bytes)
                out.write(struct.pack("<Q", size))

                with open(real_path, "rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)

    def _load_index(self):
        with open(self.bundle_path, "rb") as f:

            if f.read(4) != self.MAGIC:
                raise ValueError("Invalid bundle")

            version = struct.unpack("<B", f.read(1))[0]
            if version != self.VERSION:
                raise ValueError("Unsupported version")

            file_count = struct.unpack("<I", f.read(4))[0]

            for _ in range(file_count):

                name_len = struct.unpack("<H", f.read(2))[0]
                name = f.read(name_len).decode()

                size = struct.unpack("<Q", f.read(8))[0]

                data_offset = f.tell()

                self.index[name] = (data_offset, size)

                f.seek(size, 1)

    def unpack(self, output_dir: str):

        with open(self.bundle_path, "rb") as f:

            for name, (offset, size) in self.index.items():

                path = os.path.join(output_dir, name)
                os.makedirs(os.path.dirname(path), exist_ok=True)

                f.seek(offset)

                with open(path, "wb") as out:

                    remaining = size
                    while remaining > 0:
                        chunk = f.read(min(1024 * 1024, remaining))
                        out.write(chunk)
                        remaining -= len(chunk)

    def get_content(self, filename: str) -> bytes:
        if filename not in self.index:
            raise KeyError(filename)

        offset, size = self.index[filename]

        with open(self.bundle_path, "rb") as f:
            f.seek(offset)
            return f.read(size)