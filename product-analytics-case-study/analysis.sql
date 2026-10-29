-- Synthetic data only, independent of any employer or client.
-- One session per generated user. Assignment is fixed before outcomes.
SELECT variant, COUNT(*) AS sessions, SUM(converted) AS conversions,
       ROUND(100.0 * AVG(converted), 2) AS conversion_rate_pct,
       ROUND(AVG(latency_ms), 1) AS mean_latency_ms,
       ROUND(100.0 * AVG(no_results), 2) AS no_results_pct
FROM sessions GROUP BY variant ORDER BY variant;

SELECT device, variant, COUNT(*) AS sessions,
       ROUND(100.0 * AVG(converted), 2) AS conversion_rate_pct,
       ROUND(AVG(latency_ms), 1) AS mean_latency_ms
FROM sessions GROUP BY device, variant ORDER BY device, variant;

SELECT variant,
       ROUND(100.0 * AVG(result_clicked), 2) AS result_click_rate_pct,
       ROUND(100.0 * SUM(converted) / NULLIF(SUM(result_clicked), 0), 2)
         AS click_to_conversion_pct
FROM sessions GROUP BY variant ORDER BY variant;
