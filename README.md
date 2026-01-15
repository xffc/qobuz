# Qobuz bot with SquidWTF api
Simple telegram bot for downloading music via qobuz.squid.wtf

## Installation
1. Run `python3 -m venv qobuz && git clone https://github.com/xffc/qobuz && cd qobuz`
2. Activate python venv
3. Run `pip3 install -r requirements.txt`
4. Change contents of file `token` to bot's token
5. Run bot with `python3 main.py` (or systemd service, or ...)

## Usage
`/search <query>` - Search for track