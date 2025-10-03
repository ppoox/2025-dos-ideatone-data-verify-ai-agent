#!/usr/bin/env python
"""CLI utility to talk to the data verification LangChain agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

# Ensure the repository root is on sys.path when the script is run directly.
# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

from ai_agent.agent import run_agent
from ai_agent.settings import load_settings


def _load_history(path: Path) -> List[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("History JSON은 리스트 형태여야 합니다.")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a prompt against the data verification agent")
    parser.add_argument("--prompt", required=True, help="사용자 프롬프트")
    parser.add_argument(
        "--history",
        type=Path,
        help="이전 대화 기록(.json). [{'role': 'user', 'content': '...'}] 형식",
    )
    args = parser.parse_args()

    try:
        settings = load_settings()
    except ValueError as exc:  # Missing API key, etc.
        print(f"환경 변수 오류: {exc}", file=sys.stderr)
        return 1

    history = None
    if args.history:
        try:
            history = _load_history(args.history)
        except Exception as exc:  # noqa: BLE001 - CLI 사용성 목적
            print(f"대화 기록을 읽지 못했습니다: {exc}", file=sys.stderr)
            return 1

    try:
        reply = run_agent(args.prompt, history=history, settings=settings)
    except Exception as exc:  # noqa: BLE001
        print(f"에이전트 실행 실패: {exc}", file=sys.stderr)
        return 1

    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
