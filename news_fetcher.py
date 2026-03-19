# -*- coding: utf-8 -*-
"""뉴스 RSS 파싱 및 본문 추출."""
import logging
from dataclasses import dataclass
from typing import List

import feedparser
import requests
from bs4 import BeautifulSoup
from config import NEWS_RSS_URLS, MAX_NEWS_COUNT

logger = logging.getLogger(__name__)

@dataclass
class NewsInfo:
    url: str
    title: str
    publisher: str
    published_date: str


def fetch_rss_news() -> List[NewsInfo]:
    """설정된 RSS URL에서 뉴스 목록을 가져옵니다."""
    news_list = []
    
    for rss_url in NEWS_RSS_URLS:
        logger.info("RSS 피드 가져오는 중: %s", rss_url)
        try:
            feed = feedparser.parse(rss_url)
            default_publisher = feed.feed.get("title", "뉴스")
            
            # 아이템 파싱 (최대 개수 여유있게 가져옵니다)
            for entry in feed.entries[:MAX_NEWS_COUNT * 2]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                published = entry.get("published", "")
                
                # 구글 뉴스의 경우 source 태그에 매체명이 있을 수 있음
                actual_publisher = default_publisher
                if "source" in entry and "title" in entry.source:
                    actual_publisher = entry.source.title
                
                if not link:
                    continue
                
                news_list.append(NewsInfo(
                    url=link,
                    title=title,
                    publisher=actual_publisher,
                    published_date=published
                ))
        except Exception as e:
            logger.error("RSS 피드 파싱 실패 (%s): %s", rss_url, e)

    # 링크 기준으로 중복 제거 (순서 유지)
    seen = set()
    unique_news = []
    for news in news_list:
        if news.url not in seen:
            seen.add(news.url)
            unique_news.append(news)
            
    # 앞에서부터 최대 뉴스 개수만큼 반환
    return unique_news[:MAX_NEWS_COUNT]


def fetch_article_text(url: str) -> str:
    """주어진 URL의 뉴스 본문을 파이썬 requests와 bs4를 사용해 파싱합니다."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # 뉴스 본문은 보통 p 태그들에 모여있음
        paragraphs = soup.find_all("p")
        # 공백 제외하고 어느정도 길이가 있는 문단들만 추출
        text_content = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
        
        if not text_content:
            # p 태그로 못 찾았을 경우, body의 텍스트를 대략적으로 가져옵니다 (단순화된 백업 로직)
            body = soup.find("body")
            if body:
                text_content = [body.get_text(separator='\n', strip=True)]
            else:
                text_content = [soup.get_text(separator='\n', strip=True)]
                
        full_text = "\n".join(text_content)
        # 긴 기사일 경우를 대비해 토큰 제한 고려하여 10000자로 자름
        return full_text[:10000]
        
    except Exception as e:
        logger.warning("기사 본문 가져오기 실패 (%s): %s", url, e)
        return ""
