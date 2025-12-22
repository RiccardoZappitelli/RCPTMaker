# RCPTMaker
Use it to build [RCPepTelegram](https://github.com/RiccardoZappitelli/RCPepTelegram) faster.


## Instructions

### Clone the repository
```bash
git clone https://github.com/RiccardoZappitelli/RCPTMaker
```

### Download RCPepTelegram
```bash
cd RCPTMaker
git clone https://github.com/RiccardoZappitelli/RCPepTelegram
```

### Install the requirements
```bash
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
cd RCPepTelegram
pip install -r requirements.txt
```

### Run the code
```bash
python3 main.py
```

### Compiling more files at the same time
```bash
mkdir auths
touch auths\bot1.json
touch auths\bot2.json
touch auths\bot3.json
```