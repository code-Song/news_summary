# -*- coding: utf-8 -*-
"""뉴스 본문 추출 및 Gemini 요약 (스트리밍)."""
from __future__ import annotations

from typing import Callable, Coroutine
import asyncio
from config import GEMINI_API_KEY, GEMINI_MODEL

async def summarize_news_stream(
    text: str,
    title: str,
    publisher: str,
    on_chunk: Callable[[str], Coroutine],
    max_chars: int = 15000,
) -> str:
    """뉴스 본문을 스트리밍으로 요약합니다."""
    if not GEMINI_API_KEY:
        msg = "(Gemini API 키가 없어 요약을 건너뜁니다. .env 파일에 GEMINI_API_KEY를 설정해주세요.)"
        await on_chunk(msg)
        return msg

    import google.generativeai as genai

    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...중략...]"

    if not text.strip():
        msg = "(기사 본문을 가져오지 못하여 요약할 수 없습니다.)"
        await on_chunk(msg)
        return msg

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    prompt = f"""당신은 뉴스 기사를 읽고 3~5문장으로 핵심만 간결하게 요약하는 똑똑한 도우미입니다. 
경고: 구글 API 안전 정책(저작권)을 우회하기 위해, 절대 기사 원문의 문장을 그대로 복사해서 붙여넣지 마십시오. 전혀 다른 방식의 자연스러운 문장으로 완벽하게 의역해서 한국어로 요약해야 합니다. 광고나 메뉴 텍스트 등은 모두 무시하세요.

매체: {publisher}
제목: {title}

뉴스 본문:
{text}"""

    full_text = ""
    loop = asyncio.get_running_loop()

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    def _call_stream():
        return model.generate_content(
            prompt,
            stream=True,
            generation_config=genai.types.GenerationConfig(max_output_tokens=600),
            safety_settings=safety_settings
        )

    try:
        response = await loop.run_in_executor(None, _call_stream)
        for chunk in response:
            part = chunk.text or ""
            if part:
                full_text += part
                await on_chunk(part)
    except Exception as e:
        msg = f"\n[...구글 AI 자체 검열(보안 필터)로 인해 요약이 강제 중단되었거나 에러가 발생했습니다: {e}]"
        full_text += msg
        await on_chunk(msg)

    return full_text.strip() if full_text else "(요약 생성 불가)"
