from __future__ import annotations

import asyncio
import os

from anthropic import AsyncAnthropic

from driftguard import driftguard

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


async def main() -> None:
    prompt = "List three ways to reduce prompt injection risk in production systems."
    result = await driftguard.wrap(
        prompt=prompt,
        model="claude-3-7-sonnet-latest",
        call=lambda: client.messages.create(
            model="claude-3-7-sonnet-latest",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        ),
        metadata={"provider": "anthropic"},
    )
    print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())

