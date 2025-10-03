# AI Agent

LangChain 기반 데이터 검증 AI 에이전트를 위한 모듈입니다. OpenAI Chat Completions API를 호출하여 사용자 프롬프트와 이전 대화 맥락을 전달합니다.

## 주요 구성 요소
- `ai_agent.agent`: LangChain 체인을 생성하고 실행하는 핵심 로직
- `ai_agent.settings`: 환경 변수 기반 설정 로딩
- `ai_agent.server`: 간단한 FastAPI 엔드포인트 예시 (옵션)
- `scripts/run_agent.py`: CLI에서 프롬프트를 테스트할 수 있는 스크립트

## 빠른 시작
1. 필요한 패키지를 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```
2. `.env.example`을 복사해 실제 키를 채웁니다.
   ```bash
   cp .env.example .env
   ```
3. CLI에서 프롬프트를 실행해 봅니다.
   ```bash
   python run_agent.py --prompt "검증할 규칙을 설명해줘"
   # 또는 python scripts/run_agent.py --prompt "검증할 규칙을 설명해줘"
   ```

FastAPI 예시 서버를 실행하려면 다음을 참고하세요.
```bash
uvicorn ai_agent.server:app --reload --host 0.0.0.0 --port 8000
```

> **주의**: 실제 서비스에서는 OpenAI 키를 안전하게 보관하고, 프롬프트/응답 로그를 개인정보 규칙에 맞춰 처리하세요.
