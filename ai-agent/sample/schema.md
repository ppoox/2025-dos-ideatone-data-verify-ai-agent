### 고객(사용자)과 관련된 데이터를 저장하며 customer 스키마를 사용하고 테이블 목록은 아래와 같다.
- Tables 
  - customer
  	- 역할: 가입자(고객) 기본 정보
  	- PK: customer_id
  	- 주요 컬럼: customer_name, birth_date, email, created_at
  	- 관계: 1:N → account

### 청구와 관련된 데이터를 저장하며 billing 스키마를 사용하고 테이블 목록은 아래와 같다.
- Tables
	- account
		- 역할: 청구 계정(여러 회선을 묶는 단위)
		- PK: account_id
		- 주요 컬럼: customer_id(FK), bill_cycle_day,  status, currency_code
		- 관계: 1:N → subscription, 1:N → billing_cycle, 1:N → invoice, 1:N → payment

	- rate_plan
		- 역할: 요금제 정의(기본료/제공량/초과요율/효력기간)
		- PK: rate_plan_id
		- 주요 컬럼: monthly_fee, voice_allowance_min, data_allowance_mb, sms_allowance, overage_*, effective_from/to

	- discount
		- 역할: 할인 정책(정액/정율, 적용범위/대상, 효력기간)
		- PK: discount_id
		- 주요 컬럼: discount_type, amount_value|percent_value, apply_scope, apply_basis, effective_from/to

	- subscription
		- 역할: 회선/구독(요금제, 번호/식별자, 유효기간, 상태)
		- PK: subscription_id
		- 주요 컬럼: account_id(FK), rate_plan_id(FK), msisdn(E.164), sim_type, service_status, valid_from/to
		- 인덱스/제약: 활성 구독 단일성(uq_subscription_msisdn_active)

	- subscription_discount
		- 역할: 구독별 할인 적용 이력
		- PK: subscription_discount_id
		- 주요 컬럼: subscription_id(FK), discount_id(FK), valid_from/to

	- billing_cycle
		- 역할: 계정별 청구 기간(시작/종료/만기/상태)
		- PK: billing_cycle_id
		- 주요 컬럼: account_id(FK), cycle_start_date, cycle_end_date, due_date, status, invoice_id(Unique)
		- 관계: 1:1 → invoice(Unique FK), 1:N → usage_event

	- usage_event (파티셔닝 루트; 월별 파티션)
		- 역할: 사용량 이벤트(CDR 요약/원본)
		- PK: usage_id
		- 주요 컬럼: subscription_id(FK), billing_cycle_id(FK), service_type, started_at, quantity, unit, rated_amount
		- 파티션: RANGE (started_at) → 예: usage_event_2025_09, usage_event_2025_10

	- tax_rule
		- 역할: 세율(지역/효력기간)
		- PK: tax_rule_id
		- 주요 컬럼: region_code, tax_name, rate_percent, effective_from/to

	- invoice
		- 역할: 청구서 헤더(합계/상태)
		- PK: invoice_id
		- 주요 컬럼: account_id(FK), billing_cycle_id(Unique FK), invoice_number(Unique),
		subtotal(할인 반영, 세전), discount_total, tax_total, total_due, status

	- invoice_item
		- 역할: 청구서 상세(정액/사용/할인/세금/조정)
		- PK: invoice_item_id
		- 주요 컬럼: invoice_id(FK), subscription_id(FK, optional), item_type, service_type,
		description, quantity, unit_price, amount(음수 허용)

	- payment
		- 역할: 결제 이력
		- PK: payment_id
    	- 주요 컬럼: account_id(FK), invoice_id(FK), payment_date, method, amount, status, external_ref
- Enums
    - account_status
        - values: ACTIVE, SUSPENDED, CLOSED
    - service_status
        - values: ACTIVE, SUSPENDED, CANCELLED
    - billing_cycle_status
        - values: OPEN, CLOSED
    - invoice_status
        - values: DRAFT, ISSUED, PARTIAL, PAID, VOID
    - payment_status
        - values: PENDING, CLEARED, FAILED, REFUNDED
    - sim_type
        - values: USIM, ESIM
    - service_type
        - values: VOICE, DATA, SMS
	- usage_unit
    	- values: MIN, MB, COUNT
  	- usage_direction
    	- values: MO, MT
	- discount_type
    	- values: PERCENT, FIXED
	- apply_scope
    	- values: ACCOUNT, SUBSCRIPTION, INVOICE
	- invoice_item_type
    	- values: RECURRING, USAGE, ONE_TIME, DISCOUNT, ADJUSTMENT, TAX
  	- payment_method
      	- values: CARD, BANK_TRANSFER, CASH, POINT, OTHER