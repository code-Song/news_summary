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

    # 이전 버전과 동일하게 검증된 구버전 라이브러리로 롤백
    import google.generativeai as genai

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

    # 이전 youtube_summary 방식과 100% 동일하게 구성
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    prompt = f"""당신은 뉴스 기사를 읽고 3~5문장으로 핵심만 간결하게 요약하는 도우미입니다. 
경고: 구글 API 안전 정책(저작권)을 우회하기 위해, 절대 기사 원문의 문장을 그대로 복사해서 붙여넣지 마십시오. 반드시 당신만의 새로운 문장표현으로 완전히 바꿔서 한국어로 요약해야 합니다.

매체: {publisher}
제목: {title}

뉴스 본문:
{text}"""

    full_text = ""
    loop = asyncio.get_running_loop()

    # 뉴스 기사는 전쟁, 범죄, 주가 폭락 등 민감한 단어가 많아 LLM이 자체 검열하고 말을 자르는 현상(Safety Block) 방지
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
            generation_config=genai.types.GenerationConfig(max_output_tokens=500),
            safety_settings=safety_settings
        )

    response = await loop.run_in_executor(None, _call_stream)

    try:
        for chunk in response:
            part = chunk.text or ""
            if part:
                full_text += part
                await on_chunk(part)
    except Exception as e:
        # 안전 필터망에 걸려 갑자기 끊기면 에러가 발생하므로, 에러 발생시 그때까지 쓴 글을 유지합니다.
        pass

    return full_text.strip() if full_text else "(요약 생성 불가: 구글 안전 필터 차단됨)"
