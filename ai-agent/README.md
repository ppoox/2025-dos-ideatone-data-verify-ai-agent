# AI Agent

LangChain 기반 데이터 검증 AI 에이전트를 위한 모듈입니다. OpenAI Chat Completions API를 호출하여 사용자 프롬프트와 이전 대화 맥락을 전달합니다.

## 주요 구성 요소
- `ai_agent.agent`: LangChain 체인을 생성하고 실행하는 핵심 로직
- `ai_agent.settings`: 환경 변수 기반 설정 로딩
- `ai_agent.server`: 간단한 FastAPI 엔드포인트 예시 (옵션)
- `ai_agent.tools`: Supabase/PostgreSQL 조회용 LangChain 도구 모음
- `scripts/run_agent.py`: CLI에서 프롬프트를 테스트할 수 있는 스크립트

## Supabase/PostgreSQL 연동
- `.env`에 `SUPABASE_DB_URL`을 설정하면 에이전트가 Supabase PostgreSQL DB를 조회하는 `query_supabase_sql` 툴을 자동으로 로드합니다.
- 기본 최대 조회 행 수는 `SUPABASE_DEFAULT_LIMIT`(기본 100)으로, 쿼리에 `LIMIT`가 없을 경우 적용됩니다.
- 툴 호출 시에는 반드시 `SELECT` 쿼리를 사용하고, 필요한 경우 psycopg 스타일의 명명된 파라미터를 전달하세요.
- 스키마 요약을 프롬프트에 포함시키고 싶다면 `SUPABASE_SCHEMA_SUMMARY`에 직접 입력하거나 `SUPABASE_SCHEMA_SUMMARY_PATH`에 요약 파일 경로를 지정하세요.
- 데이터 검증 체크리스트는 `DATA_VALIDATION_GUIDELINES` 또는 `DATA_VALIDATION_GUIDELINES_PATH`를 통해 주입할 수 있습니다.
- 스키마 파일이 없다면 `SUPABASE_SCHEMA_AUTOLOAD=true`로 설정해 Supabase 메타데이터에서 테이블·컬럼 정보를 자동 추출할 수 있습니다. `SUPABASE_SCHEMA_MAX_TABLES`, `SUPABASE_SCHEMA_MAX_COLUMNS`, `SUPABASE_SCHEMA_NAME`, `SUPABASE_SCHEMA_INCLUDE_VIEWS`로 범위를 조정하세요.

## 빠른 시작
1. 필요한 패키지를 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```
2. `.env.example`을 복사해 실제 키를 채웁니다.
   ```bash
   cp .env.example .env
   ```
   Supabase를 사용할 경우 다음처럼 환경 변수를 추가합니다.
   ```env
   SUPABASE_DB_URL=postgresql://postgres:password@db.xxxxxx.supabase.co:5432/postgres
   SUPABASE_DEFAULT_LIMIT=200  # 옵션
   SUPABASE_SCHEMA_SUMMARY_PATH=./docs/schema.md  # 옵션
   DATA_VALIDATION_GUIDELINES_PATH=./docs/validation.md  # 옵션
   AGENT_RETURN_INTERMEDIATE_STEPS=true  # 옵션: 서버/CLI 응답에 중간 툴 로그 포함
   SUPABASE_SCHEMA_AUTOLOAD=true  # 옵션: 스키마 자동 로딩 활성화
   SUPABASE_SCHEMA_NAME=public
   SUPABASE_SCHEMA_MAX_TABLES=20
   SUPABASE_SCHEMA_MAX_COLUMNS=15
   SUPABASE_SCHEMA_INCLUDE_VIEWS=false
   ```
3. CLI에서 프롬프트를 실행해 봅니다.
   ```bash
   python run_agent.py --prompt "검증할 규칙을 설명해줘"
   # 또는 python scripts/run_agent.py --prompt "검증할 규칙을 설명해줘"
   # 중간 툴 호출 로그 확인
   python scripts/run_agent.py --prompt "지난주 B 이벤트 이상치 수량 확인" --show-steps
   ```
   `AGENT_RETURN_INTERMEDIATE_STEPS=true`로 서버를 실행하면 `/api/agent/chat` 응답에도 `intermediate_steps` 필드가 포함되어 생성된 SQL과 관찰 결과를 추적할 수 있습니다.

FastAPI 예시 서버를 실행하려면 다음을 참고하세요.
```bash
uvicorn ai_agent.server:app --reload --host 0.0.0.0 --port 8000
# 로그 레벨을 직접 지정하려면
uvicorn ai_agent.server:app --reload --host 0.0.0.0 --port 8000 --log-level info
```

서버는 `ai_agent.server` 로거에 프롬프트와 중간 툴 호출 정보를 기록합니다. uvicorn 표준 출력에서 실시간으로 확인하거나, `AGENT_LOG_FILE=logs/agent.log`처럼 환경 변수를 지정해 파일에도 남길 수 있습니다. 로그 레벨은 `AGENT_LOG_LEVEL`(기본 `INFO`)로 제어할 수 있습니다.

> **주의**: 실제 서비스에서는 OpenAI 키를 안전하게 보관하고, 프롬프트/응답 로그를 개인정보 규칙에 맞춰 처리하세요.
