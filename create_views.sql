-- Business Metrics Views

-- 1. daily_mape: View to track model performance per day based on actuals vs predictions
CREATE OR REPLACE VIEW daily_mape AS
SELECT
    f.forecast_date AS record_date,
    SUM(ABS(a.actual_covers - f.predicted_covers)) AS total_absolute_error,
    SUM(a.actual_covers) AS total_actual_covers,
    CASE
        WHEN SUM(a.actual_covers) > 0 THEN
            ROUND((SUM(ABS(a.actual_covers - f.predicted_covers))::NUMERIC / SUM(a.actual_covers)) * 100, 2)
        ELSE 0
    END AS wmape_percentage
FROM forecasts f
JOIN actuals a ON f.forecast_date = a.record_date AND f.hour = a.hour
GROUP BY f.forecast_date
ORDER BY f.forecast_date DESC;

-- 2. feedback_stats: View to track feedback submissions by reason
CREATE OR REPLACE VIEW feedback_stats AS
SELECT
    feedback_date,
    reason,
    COUNT(id) AS submission_count,
    SUM(ABS(actual - predicted)) as total_discrepancy
FROM feedback
GROUP BY feedback_date, reason
ORDER BY feedback_date DESC, submission_count DESC;
