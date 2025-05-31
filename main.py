import json
from telepot import Bot
from shutil import rmtree
import customtkinter as ctk
from threading import Thread
from os import chdir, listdir
from os.path import isdir, join, abspath
from subprocess import Popen, PIPE, STDOUT

repo_name = abspath("RCPepTelegram")
venv_path = abspath("venv")
pip_path = join(venv_path, "Scripts", "pip.exe")
python_path = join(venv_path, "Scripts", "python.exe")
requirements_command = f"{pip_path} install -r requirements.txt"
compile_command = f"{python_path} -m nuitka {join(repo_name, 'pep2.py')} --standalone --windows-console-mode=disable --onefile --follow-imports --msvc=latest --include-data-dir=vfx=vfx --include-data-dir=sfx=sfx --include-data-dir=model=model --include-data-file=auth.json=auth.json"

class GUI:
    def __init__(self) -> None:
        self.root = ctk.CTk()
        self.root.resizable(False, False)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(2, weight=10)

        self.chatidentry = ctk.CTkEntry(self.root, placeholder_text="YOUR CHAT ID HERE")
        self.chatidentry.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        self.bottokenentry = ctk.CTkEntry(self.root, placeholder_text="YOUR BOT TOKEN HERE")
        self.bottokenentry.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")

        self.compile_button = ctk.CTkButton(self.root, text="COMPILE", command=Thread(target=self.compile_pep).start)
        self.compile_button.grid(row=1, column=0, sticky="nsew", columnspan=2, padx=12, pady=0)

        self.output = ctk.CTkTextbox(self.root)
        self.output.grid(row=2, column=0, columnspan=2, padx=12, pady=12, sticky="nsew")
        self.output.configure(state="disabled")
        self.output.tag_config("green", foreground="green")

        self.root.geometry("500x500")
        self.root.mainloop()

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
        return int(self.chatidentry.get())

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
        try:
            bot = Bot(token)
        except:
            bot = None
        with open("auth.json", "w") as authfile:
            json.dump(
                {
                    "token":token,
                    "chatid":chatid
                }, authfile)
        self.change_button_text("CHECKING REQUIREMENTS")
        self.run_command(requirements_command)
        self.change_button_text("COMPILING")
        self.run_command(compile_command)
        self.change_button_text("COMPILE")
        self.writetextbox("Compiling Done", tag="green")
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