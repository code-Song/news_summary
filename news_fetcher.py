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
    description: str = ""

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
            desc = re.sub(r'<[^>]+>', '', item.get("description", ""))
            published = item.get("pubDate", "")
            
            news_list.append(NewsInfo(
                url=link,
                title=title,
                publisher="네이버 뉴스",
                published_date=published,
                description=desc
            ))
            
            if len(news_list) >= MAX_NEWS_COUNT:
                break
                
    except Exception as e:
        logger.error("네이버 API 뉴스 검색 실패: %s", e)

    return news_list


def fetch_article_text(url: str) -> str:
    """네이버 뉴스 본문을 파싱 (기사 내용만 정확하게 추출하여 외계어/메뉴 차단)"""
    # 사용자가 제안한 검증된 이전 프로젝트의 Session 헤더 완벽 차용
    UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    )
    headers = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        # 이전 코드대로 lxml 혹은 html.parser 사용
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. 네이버 뉴스 전용 본문 컨테이너
        article = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
        if article:
            # 불필요 요소 완벽 제거 (과거 프로젝트 참조 적용)
            for s in article.select("script, style, .media_end_correction, .copyright, figure"):
                s.decompose()
            for br in article.find_all("br"):
                br.replace_with("\n")
                
            return article.get_text('\n', strip=True)[:10000]
            
        # 2. 일반 백업 로직
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
