-- -- A. 동일 msisdn의 기간 중복(활성 구독 중복) 점검
-- SELECT s1.subscription_id AS sub_a, s2.subscription_id AS sub_b, s1.msisdn,
--        s1.valid_from AS a_from, COALESCE(s1.valid_to, '9999-12-31') AS a_to,
--        s2.valid_from AS b_from, COALESCE(s2.valid_to, '9999-12-31') AS b_to
-- FROM subscription s1
-- JOIN subscription s2 ON s1.msisdn = s2.msisdn AND s1.subscription_id < s2.subscription_id
-- WHERE daterange(s1.valid_from, COALESCE(s1.valid_to,'9999-12-31'))
--       && daterange(s2.valid_from, COALESCE(s2.valid_to,'9999-12-31'));

-- -- B. 구독 유효기간 밖의 사용 이벤트(잘못 매핑된 CDR)
-- SELECT u.usage_id, u.subscription_id, u.started_at, s.valid_from, s.valid_to
-- FROM usage_event u
-- JOIN subscription s USING(subscription_id)
-- WHERE u.started_at::date < s.valid_from
--    OR (s.valid_to IS NOT NULL AND u.started_at::date > s.valid_to);

-- -- C. 인보이스 합계 검증: (세전 소계) = sum(비세금 항목), (세금) = sum(TAX 항목)
-- SELECT i.invoice_id, i.invoice_number,
--        i.subtotal,
--        (SELECT COALESCE(SUM(amount),0) FROM invoice_item ii
--          WHERE ii.invoice_id=i.invoice_id AND ii.item_type <> 'TAX') AS calc_subtotal,
--        i.tax_total,
--        (SELECT COALESCE(SUM(amount),0) FROM invoice_item ii
--          WHERE ii.invoice_id=i.invoice_id AND ii.item_type = 'TAX') AS calc_tax
-- FROM invoice i;

-- -- D. 사용 이벤트 미과금(요율 누락 등)
-- SELECT usage_id, subscription_id, service_type, started_at, quantity, unit
-- FROM usage_event
-- WHERE rated_amount IS NULL;

-- -- 동일 MSISDN 기간 중복 탐지(기간중복 점검)
-- SELECT s1.subscription_id AS sub_a, s2.subscription_id AS sub_b, s1.msisdn,
--        s1.valid_from AS a_from, COALESCE(s1.valid_to, '9999-12-31') AS a_to,
--        s2.valid_from AS b_from, COALESCE(s2.valid_to, '9999-12-31') AS b_to
-- FROM subscription s1
-- JOIN subscription s2 ON s1.msisdn = s2.msisdn AND s1.subscription_id < s2.subscription_id
-- WHERE daterange(s1.valid_from, COALESCE(s1.valid_to,'9999-12-31'))
--    && daterange(s2.valid_from, COALESCE(s2.valid_to,'9999-12-31'));

-- -- 구독 유효기간 밖 사용 이벤트 탐지(유효기간 외 사용)
-- SELECT u.usage_id, u.subscription_id, u.started_at::date AS usage_date,
--        s.valid_from, s.valid_to
-- FROM usage_event u
-- JOIN subscription s USING(subscription_id)
-- WHERE u.started_at::date < s.valid_from
--    OR (s.valid_to IS NOT NULL AND u.started_at::date > s.valid_to);

-- -- 할인 라인 부호 오류 탐지(할인 라인은 음수여야 한다는 규칙)
-- SELECT invoice_id, invoice_item_id, description, amount
-- FROM invoice_item
-- WHERE item_type='DISCOUNT' AND amount > 0;