"""Запускается владельцем: сохраняет токен без показа на экране."""
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit
import os
import secrets

path=Path(__file__).resolve().parent.parent/'.env'
if path.exists():
    raise SystemExit('Файл .env уже существует. Сначала проверьте его вручную, чтобы не потерять настройки.')
print('Настройки остаются только в .env на этом компьютере. В GitHub этот файл не попадёт.')
origin=input('HTTPS-адрес приложения: ').strip().rstrip('/')
parsed=urlsplit(origin)
if parsed.scheme!='https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
    raise SystemExit('Нужен HTTPS-адрес без пути, параметров и пробелов.')
token=getpass('Токен зарегистрированного бота MAX (ввод скрыт): ').strip()
if not token or any(c.isspace() for c in token) or any(c in token for c in '\r\n#"\'`$'):
    raise SystemExit('Токен пустой или содержит недопустимые символы. Файл не сохранён.')
secret=secrets.token_urlsafe(32)
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:
    f.write(f'APP_ORIGIN={origin}\nMAX_BOT_TOKEN={token}\nMAX_WEBHOOK_SECRET={secret}\n')
print('Настройки сохранены. Никаких сообщений и запросов в MAX не отправлено.')
