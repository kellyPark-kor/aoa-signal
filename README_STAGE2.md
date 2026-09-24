# AOA Signal — Stage 2

## 이번 단계의 규칙 A

**A = 돌파 + 거래량 + 추세 이벤트 알림**입니다.

LONG:
- EMA20 > EMA50 > EMA200
- 거래량 / 20봉 평균 >= 1.5
- MACD histogram > 0
- 직전 20봉 고점 돌파

SHORT:
- EMA20 < EMA50 < EMA200
- 거래량 / 20봉 평균 >= 1.5
- MACD histogram < 0
- 직전 20봉 저점 이탈

RSI는 알림 조건에서 사용하지 않습니다. 기존 앱의 RSI 계산 자체는 그대로 유지합니다.

> **검증되지 않은 연구용 규칙, 수익 근거 없음.**
> AOA가 실제로 이 규칙을 사용했다는 의미가 아닙니다.

## 안전 범위
- 주문 기능 없음
- Binance API 키 없음
- 공개 시세만 사용
- Telegram은 알림 전송에만 사용

## 신호 확정
- Binance kline의 `k.x == true`인 마감 봉만 신호에 사용합니다.
- REST 백필에서도 최신 미완성 봉을 제거합니다.
- 같은 국면에서 LONG→LONG 또는 SHORT→SHORT가 이어지는 동안 재알림하지 않습니다.
- WAIT→LONG / WAIT→SHORT로 새로 켜질 때만 알립니다.
- SQLite에 `(symbol, kline_open, direction)`을 저장해 재시작 후에도 중복을 막습니다.

## Binance 연결
Binance Spot 문서상 공개 REST 시장데이터는 `https://api.binance.com` 또는 `https://data-api.binance.vision`을 사용할 수 있습니다. WebSocket Spot 시장 스트림은 문서의 market-stream endpoint를 사용합니다.

## 설치

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
```

## Telegram 설정

1. Telegram에서 `@BotFather` 검색
2. `/newbot` 실행
3. 봇 이름/username 지정
4. 받은 Bot Token을 `.env`의 `TELEGRAM_BOT_TOKEN`에 입력
5. 만든 봇을 Telegram에서 열고 `/start` 전송
6. 아래 명령으로 chat_id를 확인할 수 있습니다.

```bash
python get_chat_id.py
```

7. 출력된 chat_id를 `.env`의 `TELEGRAM_CHAT_ID`에 입력

## 테스트

실제 Telegram으로 테스트:

```bash
python worker.py --test-notify
```

실제 전송 없이 콘솔 테스트:

```bash
python worker.py --test-notify --dry-run
```

단위/리플레이 테스트:

```bash
pytest -q
```

## 실행

```bash
python worker.py
```

실제 주문은 절대 수행하지 않습니다.

## 미검증 사항

이 개발 환경에서는 실제 Binance WebSocket 장시간 연결과 실제 Telegram 계정으로의 메시지 수신을 완료 검증하지 않았습니다. 사용자가 실행 후 `--test-notify`와 worker 로그를 확인해야 합니다.
