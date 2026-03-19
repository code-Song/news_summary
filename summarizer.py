# -*- coding: utf-8 -*-
"""뉴스 본문 추출 및 Gemini 요약 (스트리밍)."""
from __future__ import annotations

from typing import Callable, Coroutine
import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL


async def summarize_news_stream(
    text: str,
    title: str,
    publisher: str,
    on_chunk: Callable[[str], Coroutine],
    max_chars: int = 10000,
) -> str:
    """
    뉴스 본문을 스트리밍으로 요약합니다.
    청크(토큰)가 생성될 때마다 on_chunk(chunk_text) 콜백을 호출합니다.
    최종 완성된 전체 요약문을 반환합니다.
    """
    if not GEMINI_API_KEY:
        msg = "(Gemini API 키가 없어 요약을 건너뜁니다. .env 파일에 GEMINI_API_KEY를 설정해주세요.)"
        await on_chunk(msg)
        return msg

    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...중략...]"

    if not text.strip():
        msg = "(기사 본문을 가져오지 못하여 요약할 수 없습니다.)"
        await on_chunk(msg)
        return msg

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    prompt = f"""당신은 뉴스 기사를 읽고 3~5문장으로 핵심만 간결하게 요약하는 도우미입니다. 한국어로 답변하세요.

매체: {publisher}
제목: {title}

뉴스 본문:
{text}"""

    full_text = ""
    loop = asyncio.get_running_loop()

    # Gemini stream은 동기 generator → executor로 비동기 처리
    def _call_stream():
        return model.generate_content(
            prompt,
            stream=True,
            generation_config=genai.types.GenerationConfig(max_output_tokens=500),
        )

    response = await loop.run_in_executor(None, _call_stream)

    for chunk in response:
        part = chunk.text or ""
        if part:
            full_text += part
            await on_chunk(part)

    return full_text.strip() if full_text else "(요약 생성 실패)"
