# -*- coding: utf-8 -*-
"""
매일 뉴스 요약 전송 서비스
- 텔레그램 Webhook 방식
- startup 시 네트워크 호출 없이 FastAPI 먼저 기동 후 백그라운드에서 봇 초기화
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import socket
from pathlib import Path

# ---------- [Hugging Face DNS 우회 임시 스크립트] ----------
# Hugging Face 일부 무료 컨테이너에서 api.telegram.org DNS를 못 찾는 현상(Errno -5) 우회
_orig_getaddrinfo = socket.getaddrinfo

def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == 'api.telegram.org':
        # Telegram API 서버 공식 고정 IPv4 할당
        host = '149.154.167.220'
        family = socket.AF_INET
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = patched_getaddrinfo
# -----------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from telegram import Bot, Update

from config import (
    DAILY_HOUR,
    DAILY_MINUTE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TIMEZONE,
)
from storage import is_seen, mark_seen
from summarizer import summarize_news_stream
from news_fetcher import fetch_rss_news, fetch_article_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── 환경변수 ──────────────────────────────────────────────────────────
_host = (
    os.environ.get("SPACE_HOST")
    or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    or os.environ.get("WEBHOOK_HOST")
    or ""
)
WEBHOOK_URL = f"https://{_host}/webhook" if _host else ""
PORT = int(os.environ.get("PORT", "7860"))

# 전역 변수
_send_chat_id: str | None = TELEGRAM_CHAT_ID or None
_bot: Bot | None = None           
_bot_ready = False                 

fastapi_app = FastAPI()

async def _send_telegram(chat_id: str, text: str):
    if not _bot:
        logger.warning("봇 미초기화 상태에서 전송 시도")
        return
    for i in range(0, len(text), 4096):
        await _bot.send_message(chat_id=chat_id, text=text[i:i + 4096])

async def _do_summarize_and_send(chat_id: str):
    if not _bot:
        return
    try:
        news_items = fetch_rss_news()
        new_ones = [n for n in news_items if not is_seen(n.url)]
        
        if not new_ones:
            await _send_telegram(chat_id, "🆕 새로 요약할 주요 뉴스가 없습니다.")
            return

        await _send_telegram(chat_id, f"📰 새 뉴스 {len(new_ones)}건 요약을 시작합니다...")

        for idx, news in enumerate(new_ones, 1):
            header = (
                f"📰 [{idx}/{len(new_ones)}] {news.publisher}\n"
                f"제목: {news.title}\n"
                f"{news.url}\n\n"
                f"📝 요약 중..."
            )
            try:
                sent = await _bot.send_message(chat_id=chat_id, text=header)
            except Exception as e:
                logger.error("텔레그램 메시지 전송 실패: %s", e)
                continue
            
            msg_id = sent.message_id
            text_content = fetch_article_text(news.url)
            
            # 본문 추출 실패시(리다이렉트나 차단 등) 최후의 보루로 API에서 받은 요약문을 본문으로 사용!
            if len(text_content.strip()) < 50:
                if getattr(news, "description", "").strip():
                    text_content = news.description.strip()
                else:
                    text_content = f"{news.title} (기사 본문 접근 불가능)"
            
            accumulated = ""
            last_sent_len = 0

            async def on_chunk(part: str, _msg_id=msg_id, _idx=idx, _news=news):
                nonlocal accumulated, last_sent_len
                accumulated += part
                new_chars = len(accumulated) - last_sent_len
                ends_sentence = accumulated and accumulated[-1] in (".", "!", "?", "\n")
                if new_chars >= 80 or ends_sentence:
                    preview = (
                        f"📰 [{_idx}/{len(new_ones)}] {_news.publisher}\n"
                        f"제목: {_news.title}\n"
                        f"{_news.url}\n\n"
                        f"📝 요약 중...\n{accumulated}▌"
                    )
                    try:
                        await _bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=_msg_id,
                            text=preview[:4096],
                        )
                        last_sent_len = len(accumulated)
                    except Exception:
                        pass

            try:
                summary = await summarize_news_stream(text_content, news.title, news.publisher, on_chunk)
                mark_seen(news.url, news.title, news.publisher)
            except Exception as e:
                logger.exception("뉴스 요약 실패: %s", news.url)
                summary = f"(요약 실패: {e})"
                mark_seen(news.url, news.title, news.publisher)

            final_text = (
                f"📰 [{idx}/{len(new_ones)}] {news.publisher}\n"
                f"제목: {news.title}\n"
                f"{news.url}\n\n"
                f"✅ 요약 완료:\n{summary}"
            )
            try:
                await _bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=final_text[:4096],
                )
            except Exception:
                await _send_telegram(chat_id, final_text)

        await _send_telegram(chat_id, f"✅ 전체 {len(new_ones)}건의 뉴스 요약 전송이 완료되었습니다!")

    except Exception as e:
        logger.exception("뉴스 요약·전송 실패")
        await _send_telegram(chat_id, f"❌ 뉴스 요약 중 오류가 발생했습니다: {e}")

async def _daily_job():
    cid = _send_chat_id or TELEGRAM_CHAT_ID
    if not cid:
        return
    logger.info("일일 뉴스 요약 전송 시작")
    await _do_summarize_and_send(cid)

async def _handle_update(update: Update):
    global _send_chat_id
    try:
        if not update.message or not update.message.text:
            return

        chat_id = str(update.effective_chat.id)
        text = update.message.text.strip()

        if not _send_chat_id:
            _send_chat_id = chat_id

        text_lower = text.lower()
        triggers = ("요약", "뉴스", "summary", "/summary", "/start", "start", "새 뉴스")
        if any(t in text_lower for t in triggers):
            await _bot.send_message(chat_id=chat_id, text="🔄 새 뉴스 요약을 시작합니다...")
            await _do_summarize_and_send(chat_id)

    except Exception as e:
        logger.exception("_handle_update 에러: %s", e)

async def _init_bot_with_retry():
    global _bot, _bot_ready
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN 시크릿이 설정되지 않았습니다!")
        return

    # IPv6 DNS 매칭 오류([Errno -5])를 완벽히 피하기 위해 커스텀 HTTPXRequest 생성
    from telegram.request import HTTPXRequest
    import httpx
    import socket

    # IPv4 기반의 연결을 강제하는 소켓 패치 수준의 우회나 넉넉한 타임아웃
    custom_request = HTTPXRequest(connection_pool_size=8, read_timeout=30)
    
    _bot = Bot(token=TELEGRAM_BOT_TOKEN, request=custom_request)
    await asyncio.sleep(3)

    attempt = 0
    while True:
        attempt += 1
        try:
            me = await _bot.get_me()
            _bot_ready = True
            logger.info("✅ 텔레그램 봇 초기화 성공: @%s", me.username)
            
            # 수동 설정값 또는 HuggingFace SPACE_HOST 환경변수 확인
            host = WEBHOOK_URL
            
            # SPACE_ID를 통한 URL 직접 조립 (대체 방안)
            if not host and os.environ.get("SPACE_ID"):
                space_id = os.environ.get("SPACE_ID").replace("/", "-").lower()
                host = f"https://{space_id}.hf.space/webhook"
                
            if host:
                await _bot.set_webhook(url=host)
                logger.info("🔗 Webhook 등록 완료: %s", host)
            else:
                logger.error("❌ WEBHOOK_URL을 찾지 못하여 Webhook 등록을 실패했습니다.")
            return
        except Exception as e:
            logger.warning("봇 초기화 시도 %d 실패: %s. 10초 후 재시도...", attempt, e)
            await asyncio.sleep(10)

@fastapi_app.api_route("/", methods=["GET", "HEAD"])
async def health_check():
    return {
        "status": "ok",
        "bot_ready": _bot_ready,
        "webhook_url": WEBHOOK_URL or "not set",
    }

@fastapi_app.get("/setup-webhook")
async def setup_webhook():
    if not _bot:
        return {"ok": False, "error": "봇 미초기화"}
    if not WEBHOOK_URL:
        return {"ok": False, "error": "웹훅 호스트 미설정"}
    try:
        result = await _bot.set_webhook(url=WEBHOOK_URL)
        return {"ok": result, "webhook_url": WEBHOOK_URL}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@fastapi_app.post("/webhook")
async def telegram_webhook(request: Request):
    if not _bot:
        return {"ok": False, "error": "bot not ready"}
    try:
        data = await request.json()
        update = Update.de_json(data, _bot)
        asyncio.create_task(_handle_update(update))
    except Exception as e:
        pass
    return {"ok": True}

@fastapi_app.on_event("startup")
async def on_startup():
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        _daily_job,
        CronTrigger(hour=DAILY_HOUR, minute=DAILY_MINUTE),
        id="daily_news_summary",
    )
    scheduler.start()
    asyncio.create_task(_init_bot_with_retry())

@fastapi_app.on_event("shutdown")
async def on_shutdown():
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)
