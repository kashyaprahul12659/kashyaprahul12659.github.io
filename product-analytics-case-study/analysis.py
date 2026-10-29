"""Reproducible portfolio demonstration. All records are synthetic."""
from pathlib import Path
import csv
import json
import math
import random
import sqlite3
import statistics

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "product_analytics_case_study" if Path(__file__).name == "build_case_study.py" else ROOT
OUT.mkdir(exist_ok=True)
if OUT != ROOT:
    (OUT / "analysis.py").write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")

SQL = """-- Synthetic data only, independent of any employer or client.
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
"""
(OUT / "analysis.sql").write_text(SQL, encoding="utf-8")

rng = random.Random(20261029)
rows = []
for i in range(12000):
    variant = "control" if rng.random() < .5 else "treatment"
    device = "mobile" if rng.random() < .65 else "desktop"
    no_results = int(rng.random() < (.08 if variant == "control" else .055))
    latency = max(100, int(rng.gauss(480 if variant == "control" else 550, 110)))
    click = int(not no_results and rng.random() < (.40 if variant == "control" else .435))
    converted = int(click and rng.random() < (.28 if device == "mobile" else .34))
    rows.append((f"u{i:05}", variant, device, latency, no_results, click, converted))
columns = ["user_id", "variant", "device", "latency_ms", "no_results", "result_clicked", "converted"]
with (OUT / "sessions.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(columns)
    writer.writerows(rows)

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE sessions(user_id TEXT PRIMARY KEY, variant TEXT, device TEXT, latency_ms INTEGER, no_results INTEGER, result_clicked INTEGER, converted INTEGER)")
db.executemany("INSERT INTO sessions VALUES(?,?,?,?,?,?,?)", rows)
queries = [q.strip() for q in SQL.split(";") if "SELECT" in q]
results = []
for q in queries:
    cur = db.execute(q)
    results.append([dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()])

control, treatment = [[r for r in rows if r[1] == v] for v in ["control", "treatment"]]
n0, n1 = len(control), len(treatment)
c0, c1 = sum(r[-1] for r in control), sum(r[-1] for r in treatment)
p0, p1 = c0 / n0, c1 / n1
diff = p1 - p0
se = math.sqrt(p0 * (1 - p0) / n0 + p1 * (1 - p1) / n1)
ci = [diff - 1.96 * se, diff + 1.96 * se]
pooled = (c0 + c1) / (n0 + n1)
z = diff / math.sqrt(pooled * (1 - pooled) * (1 / n0 + 1 / n1))
p_value = math.erfc(abs(z) / math.sqrt(2))
srm_z = (n1 - len(rows) * .5) / math.sqrt(len(rows) * .25)
srm_p = math.erfc(abs(srm_z) / math.sqrt(2))
latency_delta = statistics.mean(r[3] for r in treatment) - statistics.mean(r[3] for r in control)
checks = {
    "synthetic_data": True,
    "records": len(rows),
    "unique_users": len({r[0] for r in rows}),
    "conversion_implies_click": all(not r[-1] or r[-2] for r in rows),
    "no_result_sessions_have_no_click": all(not r[4] or not r[5] for r in rows),
    "sql_and_python_conversion_counts_agree": all(next(x for x in results[0] if x['variant'] == v)['conversions'] == sum(r[-1] for r in rows if r[1] == v) for v in ['control', 'treatment']),
    "sample_ratio_p_value": srm_p,
}
assert checks["records"] == checks["unique_users"]
assert checks["conversion_implies_click"] and checks["no_result_sessions_have_no_click"]
assert checks["sql_and_python_conversion_counts_agree"]
summary = {"data_notice": "SYNTHETIC DEMONSTRATION; not employer/client results", "metrics": results[0], "device_metrics": results[1], "funnel_metrics": results[2], "effect_percentage_points": 100 * diff, "relative_lift_pct": 100 * diff / p0, "ci_95_percentage_points": [100 * x for x in ci], "two_sided_p_value": p_value, "latency_delta_ms": latency_delta, "checks": checks}
(OUT / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

report = f"""# Search funnel experiment: a product analytics case study

**Synthetic demonstration created with AI assistance. This is not Microsoft, Bing, customer, or employer data, and the findings are not claimed business achievements.**

![Synthetic experiment dashboard](dashboard.png)

## Decision

Evaluate a hypothetical search-results change using conversion as the primary metric and latency as a guardrail. For this example, the rollout rule is: the 95% conversion-effect interval must exclude zero and the mean-latency increase must stay below 50 ms. The rule is a stated decision criterion, not a claim of experiment preregistration.

## Data and method

- 12,000 generated users, one session per user; fixed seed 20261029.
- Approximately 50/50 random assignment, with assignment preceding generated outcomes.
- A session can convert only after a result click; sessions with no results cannot click.
- Independent SQL and Python calculations verify conversion counts.
- Unpooled normal-approximation 95% confidence interval for the difference in proportions; pooled two-sided z-test. This demonstration has sufficient counts for the approximation. One primary metric; subgroup results are exploratory.
- Sample-ratio check p-value: {srm_p:.3f}.

## Results

| Metric | Control | Treatment |
| --- | ---: | ---: |
| Sessions | {n0:,} | {n1:,} |
| Conversions | {c0:,} | {c1:,} |
| Conversion rate | {p0:.2%} | {p1:.2%} |
| Mean latency (ms) | {statistics.mean(r[3] for r in control):.1f} | {statistics.mean(r[3] for r in treatment):.1f} |

Absolute conversion effect: **{100*diff:+.2f} percentage points**, with a 95% interval of **[{100*ci[0]:+.2f}, {100*ci[1]:+.2f}] percentage points**. Relative lift: {100*diff/p0:+.1f}%. Two-sided p-value: {p_value:.4f}. Mean latency increases by **{latency_delta:.1f} ms**.

## Recommendation

**Hold the rollout under the stated guardrail.** Even if conversion improves, the latency increase exceeds the example's 50 ms threshold. Profile the added search step, optimize it, and rerun a controlled experiment. Report both the primary metric and the guardrail rather than presenting the conversion lift alone.

## Limitations

The generator intentionally creates different click rates and latencies, so these effects demonstrate analysis, not discovery about real customers. Sessions are independent by construction; real experiments need user-level assignment, repeat-user handling, exposure checks, bot exclusion, seasonality controls, and a prospective sample-size plan. No claim is made that this one simulated run generalizes to a production system.

## Reproduce

Run `python analysis.py` with Python 3.10+; it uses only the standard library and regenerates the data, SQL, results, and this report from a fixed seed. `analysis.sql` runs against the included CSV loaded into a SQLite `sessions` table. Open `analysis.ipynb` for a short notebook walkthrough.

## Files

- `analysis.py`: data generation, SQLite queries, inference, and consistency checks.
- `analysis.sql`: primary metrics, device segmentation, and funnel queries.
- `sessions.csv`: synthetic session records generated locally by `analysis.py` (not committed).
- `results.json`: complete calculated results and validation checks.
- `analysis.ipynb`: executable notebook walkthrough.

Prepared for Rahul Kashyap's portfolio, October 2026.
"""
(OUT / "README.md").write_text(report, encoding="utf-8")
notebook = {"cells": [{"cell_type": "markdown", "metadata": {}, "source": ["# Synthetic search funnel experiment\n", "AI-assisted demonstration only; no employer or customer data.\n", "The analysis reports a conversion metric, uncertainty, and a latency guardrail."]}, {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": ["from pathlib import Path\n", "import runpy, json\n", "runpy.run_path('analysis.py', run_name='__main__')\n", "results = json.loads(Path('results.json').read_text())\n", "results"]}, {"cell_type": "markdown", "metadata": {}, "source": ["## Interpretation\n", "Read the effect interval together with the latency guardrail. A positive conversion point estimate alone does not establish a rollout decision. See README.md for the decision rule and limitations."]}], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.10"}}, "nbformat": 4, "nbformat_minor": 5}
(OUT / "analysis.ipynb").write_text(json.dumps(notebook, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
