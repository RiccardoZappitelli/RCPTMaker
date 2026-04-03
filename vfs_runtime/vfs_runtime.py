import sys
import os
import builtins
import importlib.abc
import importlib.util
from io import BytesIO
import struct
import zlib
import tempfile
import atexit
from collections.abc import Callable

from . import conf

try:
    import cv2
    cv2_installed = True
except ImportError:
    cv2_installed = False

FROZEN = getattr(sys, "frozen", False)

vfs = None

# =========================
# LOGGING
# =========================
def vfs_log(func, msg):
    print(f"[VFS][{func}] {msg}")

# =========================
# TEMP FILE HANDLER
# =========================
_temp_files = []

def extract_temp(path_in_bundle):
    vfs_log("extract_temp", f"extracting {path_in_bundle}")
    fp = vfs.read(path_in_bundle)
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(fp)
    tmp.close()
    _temp_files.append(tmp.name)
    vfs_log("extract_temp", f"-> {tmp.name}")
    return tmp.name

def cleanup_temp_files():
    for f in _temp_files:
        try:
            os.unlink(f)
            vfs_log("cleanup", f"deleted {f}")
        except Exception as e:
            vfs_log("cleanup", f"failed {f}: {e}")

def _norm(path: str) -> str:
    if not isinstance(path, str):
        return path
    path = path.replace("\\", "/").strip()
    if path == ".":
        return ""
    return path.strip("/")

# =========================
# HELPERS
# =========================
def resolve_bundle_path():
    candidates = []
    name = conf.BUNDLE_NAME or "assets.bin"

    if conf.BUNDLE_PATH:
        candidates.append(conf.BUNDLE_PATH)

    candidates.append(os.path.abspath(name))

    if hasattr(sys, "argv") and sys.argv[0]:
        main_path = os.path.abspath(sys.argv[0])
        candidates.append(os.path.join(os.path.dirname(main_path), name))

    exe_dir = os.path.dirname(sys.executable)
    candidates.append(os.path.join(exe_dir, name))

    candidates.append(sys.executable)

    vfs_log("resolve_bundle_path", f"candidates: {candidates}")

    seen = set()

    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)

        vfs_log("resolve_bundle_path", f"checking {path}")

        if not os.path.exists(path):
            vfs_log("resolve_bundle_path", f"not found {path}")
            continue

        try:
            if conf.decryption_function:
                with open(path, "rb") as f:
                    try:
                        data = f.read()
                        #APPLY DECRYPTION IF AVAILABLE
                        data = conf.decryption_function(data)
                        vfs_log("resolve_bundle_path", f"decrypted {path}")
                    except Exception as e:
                        vfs_log("resolve_bundle_path", f"decrypt failed {path}: {e}")
                        continue  # skip this candidate
            else:
                with open(path, "rb") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(size - 4096, 0), 0)
                    data = f.read()

            if conf.BUNDLE_MAGIC_BYTES in data:
                vfs_log("resolve_bundle_path", f"FOUND bundle in {path}")
                return path
            else:
                vfs_log("resolve_bundle_path", f"magic not found in {path}")

        except Exception as e:
            vfs_log("resolve_bundle_path", f"error {path}: {e}")

    vfs_log("resolve_bundle_path", "NO BUNDLE FOUND")
    return None

# =========================
# VFS CORE
# =========================
class VFS:
    MAGIC = conf.BUNDLE_MAGIC_BYTES

    def __init__(self, decryption_function: Callable | None = None):
        self.index = {}
        self.fp = None
        self.decryption_function = decryption_function
        vfs_log("VFS.__init__", "initializing")
        self._load_bundle()

    def _load_bundle(self):
        path = resolve_bundle_path()
        if not path:
            vfs_log("_load_bundle", "no bundle path found")
            return

        vfs_log("_load_bundle", f"loading {path}")

        with open(path, "rb") as f:
            data = f.read()

        if self.decryption_function:
            try:
                data = self.decryption_function(data)
                vfs_log("_load_bundle", "decryption applied")
            except Exception as e:
                vfs_log("_load_bundle", f"decryption failed: {e}")
                return

        pos = data.rfind(self.MAGIC)
        if pos == -1:
            vfs_log("_load_bundle", "magic not found")
            return

        self.fp = data
        offset = pos + len(self.MAGIC)

        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        vfs_log("_load_bundle", f"{count} files found")

        for _ in range(count):
            path_len = struct.unpack_from("<H", data, offset)[0]
            offset += 2

            path_str = data[offset:offset + path_len].decode()
            offset += path_len

            file_offset, file_size = struct.unpack_from("<II", data, offset)
            offset += 8

            self.index[path_str] = (file_offset, file_size)

        vfs_log("_load_bundle", f"index built ({len(self.index)} entries)")

    def exists(self, path: str) -> bool:
        path = _norm(path)

        if path in self.index:
            vfs_log("exists", f"{path} -> file")
            return True

        for p in self.index:
            if p.startswith(path + "/"):
                vfs_log("exists", f"{path} -> dir")
                return True

        vfs_log("exists", f"{path} -> false")
        return False

    def read(self, path: str) -> bytes:
        path = _norm(path)

        if path not in self.index:
            vfs_log("read", f"{path} not found")
            raise FileNotFoundError(path)

        off, size = self.index[path]
        raw = self.fp[off:off + size]

        try:
            data = zlib.decompress(raw)
            vfs_log("read", f"{path} -> {len(data)} bytes (decompressed)")
            return data
        except:
            vfs_log("read", f"{path} -> {len(raw)} bytes (raw)")
            return raw

    def open_file(self, path: str):
        vfs_log("open_file", path)
        return BytesIO(self.read(path))

    def listdir(self, path: str):
        path = _norm(path)
        out = set()

        for p in self.index:
            if path and not p.startswith(path + "/"):
                continue
            rest = p[len(path)+1:] if path else p
            if rest:
                out.add(rest.split("/")[0])

        vfs_log("listdir", f"{path} -> {len(out)} entries")
        return list(out)

def init_vfs():
    global vfs
    vfs_log("init_vfs", "initializing with current conf")
    vfs = VFS(decryption_function=conf.decryption_function)

# =========================
# PATCH
# =========================
_real_open = builtins.open
_real_exists = os.path.exists
_real_listdir = os.listdir
if cv2_installed:
    _real_imread = cv2.imread

def vfs_open(path, *args, **kwargs):
    norm = _norm(path)
    if (vfs and isinstance(norm, str)) and vfs.exists(norm):
        vfs_log("open", f"{norm} (VFS)")
        return vfs.open_file(norm)
    vfs_log("open", f"{path} (real)")
    return _real_open(path, *args, **kwargs)

def vfs_exists(path):
    if vfs and vfs.exists(path):
        result = vfs.exists(path)
    else:
        result = _real_exists(path)
    vfs_log("exists_patch", f"{path} -> {result}")
    return result

def vfs_listdir(path):
    if vfs and vfs.exists(path):
        vfs_log("listdir_patch", f"{path} (VFS)")
        return vfs.listdir(path)
    vfs_log("listdir_patch", f"{path} (real)")
    return _real_listdir(path)

def vfs_imread(path, *args, **kwargs):
    if not cv2_installed:
        return
    if vfs and vfs.exists(path):
        tmp = extract_temp(path)
        vfs_log("imread", f"{path} -> {tmp}")
        return _real_imread(tmp, *args, **kwargs)
    vfs_log("imread", f"{path} (real)")
    return _real_imread(path, *args, **kwargs)

builtins.open = vfs_open

exists = vfs_exists
listdir = vfs_listdir
if cv2_installed:
    imread = vfs_imread

# =========================
# IMPORT HOOK
# =========================
class VFSLoader(importlib.abc.Loader):
    def exec_module(self, module):
        vfs_log("import", f"exec {module.__name__}")
        code = vfs.read(module.__spec__.origin)
        exec(compile(code, module.__spec__.origin, "exec"), module.__dict__)

class VFSFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        rel = fullname.replace(".", "/") + ".py"

        if vfs and vfs.exists(rel):
            vfs_log("import", f"module {fullname}")
            return importlib.util.spec_from_loader(fullname, VFSLoader(), origin=rel)

        rel_init = fullname.replace(".", "/") + "/__init__.py"
        if vfs and vfs.exists(rel_init):
            vfs_log("import", f"package {fullname}")
            return importlib.util.spec_from_loader(fullname, VFSLoader(), origin=rel_init, is_package=True)

        return None

sys.meta_path.insert(0, VFSFinder())
atexit.register(cleanup_temp_files)
