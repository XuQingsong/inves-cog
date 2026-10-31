BEGIN;

-- 1. ensure stable + other-slug catalog rows exist first (FK order)
INSERT INTO flows.series_catalog (series_id, name_zh, unit, frequency, source)
SELECT DISTINCT v.series_id, '每日看跌看涨比', 'ratio', 'daily', 'Cboe' FROM (VALUES
  ('cboe_pc_total'),('cboe_pc_index'),('cboe_pc_equity'),('cboe_pc_etp'),
  ('cboe_pc_spx'),('cboe_pc_vix'),('cboe_pc_oex')) v(series_id)
ON CONFLICT (series_id) DO NOTHING;

-- catalog rows for every other-slug already present in observations
INSERT INTO flows.series_catalog (series_id, name_zh, unit, frequency, source)
SELECT DISTINCT
  'cboe_pc_other_' || lower(regexp_replace(regexp_replace(o.series_id, '^cboe_pc_', ''), '[^a-z0-9]+', '_', 'g')),
  '每日看跌看涨比', 'ratio', 'daily', 'Cboe'
FROM flows.observations o
WHERE o.series_id LIKE 'cboe_pc_%'
  AND o.series_id NOT IN ('cboe_pc_total','cboe_pc_index','cboe_pc_equity',
                          'cboe_pc_etp','cboe_pc_spx','cboe_pc_vix','cboe_pc_oex')
  AND o.series_id NOT LIKE 'cboe_pc_other_%'
ON CONFLICT (series_id) DO NOTHING;

-- 2. rewrite observations to stable ids (mapped 7 + other slugs)
UPDATE flows.observations SET series_id = 'cboe_pc_total'  WHERE series_id IN ('cboe_pc_total_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_index'  WHERE series_id IN ('cboe_pc_index_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_equity' WHERE series_id IN ('cboe_pc_equity_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_etp'    WHERE series_id IN ('cboe_pc_exchange_traded_products_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_spx'    WHERE series_id IN ('cboe_pc_spx__spxw_put_call_ratio','cboe_pc_spx_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_vix'    WHERE series_id IN ('cboe_pc_cboe_volatility_index_vix_put_call_ratio','cboe_pc_vix_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_oex'    WHERE series_id IN ('cboe_pc_oex_put_call_ratio');
UPDATE flows.observations o SET series_id =
  'cboe_pc_other_' || lower(regexp_replace(regexp_replace(o.series_id, '^cboe_pc_', ''), '[^a-z0-9]+', '_', 'g'))
WHERE o.series_id LIKE 'cboe_pc_%'
  AND o.series_id NOT IN ('cboe_pc_total','cboe_pc_index','cboe_pc_equity',
                          'cboe_pc_etp','cboe_pc_spx','cboe_pc_vix','cboe_pc_oex')
  AND o.series_id NOT LIKE 'cboe_pc_other_%';

-- zh names
UPDATE flows.series_catalog SET name_zh = '全市场看跌看涨比' WHERE series_id='cboe_pc_total';
UPDATE flows.series_catalog SET name_zh = '指数看跌看涨比'   WHERE series_id='cboe_pc_index';
UPDATE flows.series_catalog SET name_zh = '股票看跌看涨比'   WHERE series_id='cboe_pc_equity';
UPDATE flows.series_catalog SET name_zh = 'ETP 看跌看涨比'   WHERE series_id='cboe_pc_etp';
UPDATE flows.series_catalog SET name_zh = 'SPX 看跌看涨比'   WHERE series_id='cboe_pc_spx';
UPDATE flows.series_catalog SET name_zh = 'VIX 看跌看涨比'   WHERE series_id='cboe_pc_vix';
UPDATE flows.series_catalog SET name_zh = 'OEX 看跌看涨比'   WHERE series_id='cboe_pc_oex';

-- 3. drop only unreferenced old catalog ids
DELETE FROM flows.series_catalog c
WHERE c.series_id LIKE 'cboe_pc_%'
  AND c.series_id NOT IN ('cboe_pc_total','cboe_pc_index','cboe_pc_equity',
                          'cboe_pc_etp','cboe_pc_spx','cboe_pc_vix','cboe_pc_oex')
  AND c.series_id NOT LIKE 'cboe_pc_other_%'
  AND NOT EXISTS (SELECT 1 FROM flows.observations o WHERE o.series_id = c.series_id);

COMMIT;
