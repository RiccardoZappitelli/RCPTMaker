import json
from git import Repo
from telepot import Bot
from shutil import rmtree
import customtkinter as ctk
from threading import Thread
from os import chdir, listdir
from subprocess import Popen, PIPE, STDOUT
from os.path import isdir, join, abspath, isfile

repo_name = abspath("RCPepTelegram")
venv_path = abspath("venv")
pip_path = join(venv_path, "Scripts", "pip.exe")
python_path = join(venv_path, "Scripts", "python.exe")
requirements_command = f"{pip_path} install -r requirements.txt"
compile_command = f"{python_path} -m nuitka {join(repo_name, 'pep2.py')} --windows-console-mode=disable --standalone --onefile --follow-imports --msvc=latest --include-data-dir=assets/vfx=assets/vfx --include-data-dir=assets/sfx=assets/sfx --include-data-dir=assets/model=assets/model --include-data-file=auth.json=auth.json"

with open(join(repo_name, "pep2.py"), "r", encoding="utf-8") as fi:
    __version__ = fi.read().split("\n")[10]

class GUI:
    def __init__(self) -> None:
        self.root = ctk.CTk()
        self.root.title(f"Builder for RCPepTelegram v{__version__}")
        self.root.resizable(False, False)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(3, weight=10)

        self.chatidentry = ctk.CTkEntry(self.root, placeholder_text="YOUR CHAT ID HERE")
        self.chatidentry.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        self.bottokenentry = ctk.CTkEntry(self.root, placeholder_text="YOUR BOT TOKEN HERE")
        self.bottokenentry.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")

        self.ngroktokenentry = ctk.CTkEntry(self.root, placeholder_text="YOUR NGROK TOKEN HERE")
        self.ngroktokenentry.grid(row=1, column=0, padx=12, pady=12, sticky="nsew", columnspan=2)

        self.compile_button = ctk.CTkButton(self.root, text="COMPILE", command=self.compiling_thread)
        self.compile_button.grid(row=2, column=0, sticky="nsew", columnspan=2, padx=12, pady=0)

        self.output = ctk.CTkTextbox(self.root)
        self.output.grid(row=3, column=0, columnspan=2, padx=12, pady=12, sticky="nsew")
        self.output.configure(state="disabled")
        self.output.tag_config("green", foreground="green")
        self.output.tag_config("red", foreground="red")

        self.root.geometry("500x500")
        authfilename = join(repo_name, "auth.json")
        if isfile(authfilename):
            with open(authfilename,  "r") as authfile:
                var = json.load(authfile)
                token = var["token"].strip()
                chatid = var["chatid"]
                ngrok_token = var["ngrok_token"].strip()
                self.bottokenentry.insert(0, token)
                self.chatidentry.insert(0, chatid)
                self.ngroktokenentry.insert(0, ngrok_token)
        self.root.mainloop()
    
    def compiling_thread(self) -> None:
        Thread(target=self.compile_pep).start()

    def change_button_text(self, text: str) -> None:
        self.compile_button.configure(text=text)

    def run_command(self, command:str) -> None:
        p=Popen(command.split(), stdout=PIPE, stderr=STDOUT)
        while p.poll() is None:
            msg = p.stdout.readline().strip()
            self.writetextbox(msg+b"\n")

    def remove_temp(self) -> None:
        for file in listdir(repo_name):
            if isdir(file) and file.startswith("pep2"):
                rmtree(file)

    def gettoken(self) -> str:
        return self.bottokenentry.get()

    def getchatid(self) -> int:
        return self.chatidentry.get()

    def getngroktoken(self) -> str:
        return self.ngroktokenentry.get()

    def enable_all(self) -> None:
        for w in (self.bottokenentry, self.chatidentry, self.compile_button):
            w.configure(state="normal")

    def disable_all(self) -> None:
        for w in (self.bottokenentry, self.chatidentry, self.compile_button):
            w.configure(state="disabled")

    def compile_pep(self) -> None:
        chdir(repo_name)
        self.disable_all()
        token = self.gettoken()
        chatid = self.getchatid()
        ngrok_token = self.getngroktoken()
        if not all((token, chatid)):
            self.writetextbox("You must have a chatid and a bottoken.", tag="red")
            self.enable_all()
            return
        try:
            bot = Bot(token)
        except:
            bot = None
        with open("auth.json", "w") as authfile:
            json.dump(
                {
                    "token":token,
                    "chatid":int(chatid),
                    "ngrok_token":ngrok_token
                }, authfile)
        self.change_button_text("CHECKING REQUIREMENTS")
        self.run_command(requirements_command)
        self.change_button_text("COMPILING")
        self.run_command(compile_command)
        self.change_button_text("COMPILE")
        self.writetextbox("Compiling completed", tag="green")
        self.enable_all()
        self.remove_temp()
        if isinstance(bot, Bot):
            bot.sendMessage(chatid, "Your bot has been compiled")

    def writetextbox(self, content: str, tag=None) -> None:
        self.output.configure(state="normal")
        self.output.insert(ctk.END, content, tags=tag)
        self.output.configure(state="disabled")
        self.output.yview(ctk.END)

def main() -> None:
    if isdir(repo_name):
        gui = GUI()
    else:
        print(f"You forgot to copy {repo_name}, here's a link: https://github.com/RiccardoZappitelli/{repo_name}")


if __name__ == "__main__":
    main()