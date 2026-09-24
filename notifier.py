from __future__ import annotations
import logging, os, time
from dataclasses import dataclass
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

@dataclass
class NotificationResult:
    ok: bool
    channel: str
    error: Optional[str] = None

class Notifier:
    def __init__(self, config: dict, dry_run: bool = False):
        self.cfg = config.get("notifications", {})
        self.dry_run = dry_run or bool(self.cfg.get("dry_run", False))
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.ntfy_topic = os.getenv("NTFY_TOPIC", "").strip()

    def send(self, message: str) -> NotificationResult:
        if self.dry_run:
            print("\n--- DRY RUN NOTIFICATION ---\n" + message + "\n--- END ---\n")
            return NotificationResult(True, "dry-run")
        results=[]
        if self.cfg.get("telegram_enabled", True):
            results.append(self._telegram(message))
        if self.cfg.get("ntfy_enabled", False):
            results.append(self._ntfy(message))
        if not results:
            log.warning("알림 채널이 모두 비활성화되어 있습니다.")
            return NotificationResult(False, "none", "no enabled channel")
        ok=any(r.ok for r in results)
        err="; ".join(r.error or "" for r in results if not r.ok) or None
        return NotificationResult(ok, ",".join(r.channel for r in results), err)

    def _telegram(self, message: str) -> NotificationResult:
        if not self.telegram_token or not self.telegram_chat_id:
            return NotificationResult(False, "telegram", "TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없습니다.")
        url=f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload={"chat_id": self.telegram_chat_id, "text": message}
        for attempt in range(1,4):
            try:
                r=requests.post(url, json=payload, timeout=10)
                if r.ok:
                    return NotificationResult(True, "telegram")
                err=f"HTTP {r.status_code}: {r.text[:300]}"
            except Exception as e:
                err=str(e)
            if attempt < 3:
                time.sleep(2 ** (attempt-1))
        log.error("Telegram 전송 실패(3회): %s", err)
        return NotificationResult(False, "telegram", err)

    def _ntfy(self, message: str) -> NotificationResult:
        if not self.ntfy_topic:
            return NotificationResult(False, "ntfy", "NTFY_TOPIC이 없습니다.")
        try:
            r=requests.post(f"https://ntfy.sh/{self.ntfy_topic}", data=message.encode("utf-8"), timeout=10)
            if r.ok: return NotificationResult(True, "ntfy")
            return NotificationResult(False, "ntfy", f"HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            return NotificationResult(False, "ntfy", str(e))
