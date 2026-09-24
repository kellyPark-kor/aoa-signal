import os, requests
from dotenv import load_dotenv
load_dotenv()
t=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
if not t:
    raise SystemExit('TELEGRAM_BOT_TOKEN이 없습니다. .env에 입력하세요.')
r=requests.get(f'https://api.telegram.org/bot{t}/getUpdates',timeout=10)
r.raise_for_status(); data=r.json()
for u in data.get('result',[]):
    m=u.get('message') or u.get('edited_message') or u.get('channel_post')
    if m and m.get('chat'):
        c=m['chat']; print(f"chat_id={c['id']} type={c.get('type')} title={c.get('title') or c.get('username') or c.get('first_name')}")
if not data.get('result'):
    print('업데이트가 없습니다. Telegram에서 봇에게 /start를 보낸 뒤 다시 실행하세요.')
