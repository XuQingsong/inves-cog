BEGIN;

-- rename daily-JSON slug ids to the stable ids (matching the archive CSV names)
UPDATE flows.observations SET series_id = 'cboe_pc_total'
 WHERE series_id IN ('cboe_pc_total_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_index'
 WHERE series_id IN ('cboe_pc_index_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_equity'
 WHERE series_id IN ('cboe_pc_equity_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_spx'
 WHERE series_id IN ('cboe_pc_spx__spxw_put_call_ratio', 'cboe_pc_spx_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_vix'
 WHERE series_id IN ('cboe_pc_cboe_volatility_index_vix_put_call_ratio', 'cboe_pc_vix_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_oex'
 WHERE series_id IN ('cboe_pc_oex_put_call_ratio');
UPDATE flows.observations SET series_id = 'cboe_pc_etp'
 WHERE series_id IN ('cboe_pc_exchange_traded_products_put_call_ratio');
UPDATE flows.series_catalog SET series_id = o.series_id
  FROM (SELECT DISTINCT series_id FROM flows.observations) o
 WHERE series_catalog.series_id LIKE 'cboe_pc_%_put_call_ratio'
   AND o.series_id IN ('cboe_pc_total','cboe_pc_index','cboe_pc_equity','cboe_pc_spx','cboe_pc_vix','cboe_pc_oex','cboe_pc_etp');
DELETE FROM flows.series_catalog WHERE series_id LIKE 'cboe_pc_%_put_call_ratio';
INSERT INTO flows.series_catalog (series_id, name_zh, unit, frequency, source)
VALUES ('cboe_pc_total','全市场看跌看涨比','ratio','daily','Cboe'),
       ('cboe_pc_index','指数看跌看涨比','ratio','daily','Cboe'),
       ('cboe_pc_equity','股票看跌看涨比','ratio','daily','Cboe'),
       ('cboe_pc_etp','ETP 看跌看涨比','ratio','daily','Cboe'),
       ('cboe_pc_spx','SPX 看跌看涨比','ratio','daily','Cboe'),
       ('cboe_pc_vix','VIX 看跌看涨比','ratio','daily','Cboe'),
       ('cboe_pc_oex','OEX 看跌看涨比','ratio','daily','Cboe')
ON CONFLICT (series_id) DO UPDATE SET name_zh=EXCLUDED.name_zh;

COMMIT;
