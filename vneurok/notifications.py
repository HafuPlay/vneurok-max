"""Inspect an outbox by default; --send makes real external MAX requests."""
import argparse
import json
import os
from .core import Store
from .max_api import flush_outbox


def main():
    parser=argparse.ArgumentParser(description='Очередь уведомлений MAX; по умолчанию без отправки')
    parser.add_argument('--db',required=True)
    parser.add_argument('--send',action='store_true',help='РЕАЛЬНАЯ отправка: только после разрешения на подключение и сообщения')
    args=parser.parse_args()
    print(json.dumps(flush_outbox(Store(args.db),os.getenv('MAX_BOT_TOKEN'),args.send),ensure_ascii=False))

if __name__=='__main__':
    main()
