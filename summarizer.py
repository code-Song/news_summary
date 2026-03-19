# -*- coding: utf-8 -*-
"""뉴스 본문 추출 및 OpenAI 요약 (스트리밍)."""
from __future__ import annotations

from typing import Callable, Coroutine
import asyncio
from config import OPENAI_API_KEY, OPENAI_MODEL

async def summarize_news_stream(
    text: str,
    title: str,
    publisher: str,
    on_chunk: Callable[[str], Coroutine],
    max_chars: int = 15000,
) -> str:
    """뉴스 본문을 스트리밍으로 요약합니다."""
    if not OPENAI_API_KEY:
        msg = "(OpenAI API 키가 없어 요약을 건너뜁니다. .env 파일에 설정해주세요.)"
        await on_chunk(msg)
        return msg

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...중략...]"

    if not text.strip():
        msg = "(기사 본문을 가져오지 못하여 요약할 수 없습니다.)"
        await on_chunk(msg)
        return msg
    
    system_prompt = "당신은 뉴스 기사를 읽고 3~5문장으로 가장 중요한 핵심만 간결하게 요약해주는 똑똑한 도우미입니다. 완전한 자연어 문장 형태로 작성하며, 광고나 메뉴 텍스트 등은 모두 무시하고 한국어로 답변하세요."

    prompt = f"""
매체: {publisher}
제목: {title}

뉴스 본문:
{text}"""

    full_text = ""

    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            stream=True,
            max_tokens=600
        )

        async for chunk in response:
            delta = chunk.choices[0].delta.content if chunk.choices else ""
            if delta:
                full_text += delta
                await on_chunk(delta)
                
    except Exception as e:
        msg = f"\n[...OpenAI 호출 중 에러 발생: {e}]"
        full_text += msg
        await on_chunk(msg)

    return full_text.strip() if full_text else "(요약 생성 불가)"
