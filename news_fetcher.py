# -*- coding: utf-8 -*-
"""뉴스 RSS 파싱 및 본문 추출."""
import logging
from dataclasses import dataclass
from typing import List

import feedparser
import requests
from bs4 import BeautifulSoup
from config import NEWS_RSS_URLS, MAX_NEWS_COUNT, NAVER_API_KEY, NAVER_SECRET_KEY

logger = logging.getLogger(__name__)

@dataclass
class NewsInfo:
    url: str
    title: str
    publisher: str
    published_date: str

import datetime
import re

def fetch_rss_news() -> List[NewsInfo]:
    """사용자가 발급한 네이버 Open API를 통해 깔끔하게 최신 네이버 뉴스(속보)를 가져옵니다."""
    news_list = []
    
    if not NAVER_API_KEY or not NAVER_SECRET_KEY:
        logger.error("NAVER_API_KEY 및 NAVER_SECRET_KEY 설정이 필요합니다.")
        return news_list

    # 네이버 뉴스 검색 API URL
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_API_KEY,
        "X-Naver-Client-Secret": NAVER_SECRET_KEY
    }
    
    # '속보' 키워드로 최신순 검색 (100개 요청어유)
    # 관심 분야가 있다면 "IT" 등으로 변경 가능
    params = {
        "query": "속보",
        "display": 50,
        "sort": "date"
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        for item in data.get("items", []):
            link = item.get("link", "")
            
            # 본문 추출이 가장 완벽한 네이버 자체 서비스 기사만 골라냅니다
            if "n.news.naver.com" not in link:
                continue
                
            # 네이버 API는 타이틀에 <b> 태그 등을 넣으므로 제거
            title = re.sub(r'<[^>]+>', '', item.get("title", ""))
            published = item.get("pubDate", "")
            
            news_list.append(NewsInfo(
                url=link,
                title=title,
                publisher="네이버 뉴스",
                published_date=published
            ))
            
            if len(news_list) >= MAX_NEWS_COUNT:
                break
                
    except Exception as e:
        logger.error("네이버 API 뉴스 검색 실패: %s", e)

    return news_list


def fetch_article_text(url: str) -> str:
    """네이버 뉴스 본문을 파싱 (기사 내용만 정확하게 추출하여 외계어/메뉴 차단)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")
        
        # 1. 네이버 뉴스 전용 본문 컨테이너 (정확도 100%)
        dic_area = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
        if dic_area:
            # 사진 설명 등 불필요한 내부 태그 제거
            for blind in dic_area.select("span.end_photo_org, div.nbd_im_w, em.img_desc, strong"):
                blind.decompose()
            return dic_area.get_text(separator='\n', strip=True)[:10000]
            
        # 2. 일반 백업 로직 (본문 p태그)
        paragraphs = soup.find_all("p")
        text_content = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        
        if not text_content:
            body = soup.find("body")
            if body:
                text_content = [body.get_text(separator='\n', strip=True)]
                
        full_text = "\n".join(text_content)
        return full_text[:10000]
        
    except Exception as e:
        logger.warning("기사 본문 가져오기 실패 (%s): %s", url, e)
        return ""
