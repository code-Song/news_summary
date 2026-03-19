# -*- coding: utf-8 -*-
"""설정: .env 또는 환경변수에서 로드."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

_DATA_DIR = Path("/data") if Path("/data").exists() else Path(__file__).parent

# 구글 뉴스는 최근 스크래핑을 차단하여 원본 기사 주소를 숨기므로,
# 본문 추출이 매우 용이한 국내 다이렉트 언론사 RSS로 기본 동작 변경
NEWS_RSS_URLS = [
    x.strip()
    for x in os.environ.get(
        "NEWS_RSS_URLS", 
        "https://fs.jtbc.co.kr/RSS/newsflash.xml,https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=14&plink=RSSREADER"
    ).split(",")
    if x.strip()
]

# Gemini (요약용)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

# Telegram
# 여러 환경에서 발생할 수 있는 특수문자, 따옴표, 띄어쓰기 등 잘못된 입력값 필터링
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(" \n\r\"'")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip(" \n\r\"'")

# 스케줄 (매일 6시, 한국 시간)
DAILY_HOUR = int(os.environ.get("DAILY_HOUR", "6"))
DAILY_MINUTE = int(os.environ.get("DAILY_MINUTE", "0"))
TIMEZONE = os.environ.get("TZ", "Asia/Seoul")

# 새 뉴스 조회 범위 (새 뉴스를 몇 건 가져와서 요약할지 제한)
MAX_NEWS_COUNT = int(os.environ.get("MAX_NEWS_COUNT", "5"))
