from __future__ import annotations

import asyncio
import os

from openai import AsyncOpenAI

import driftguard

client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


@driftguard.monitor(model="gpt-4o-mini")
async def call_llm(prompt: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


async def main() -> None:
    print(await call_llm("Summarize why runtime safety monitoring matters for LLM apps."))


if __name__ == "__main__":
    asyncio.run(main())
