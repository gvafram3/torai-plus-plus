# TORAI++ : Fixing TORAI's Blindness to Aggregation

**Paper:** *When Root Cause Analysis Fails: TORAI's Blindness to Aggregation in Microservice Systems* (submitted).

## TL;DR

TORAI (FSE 2026) reports strong root-cause-analysis accuracy on resource faults.
On the **RE3 code-level fault dataset**, we find:

- On **Online Boutique** (aggregation-heavy), TORAI's AC@1 collapses to **0.03**.
- On **Train Ticket** (no aggregation pattern), TORAI's AC@1 stays at **1.00**.
- Cause: TORAI ranks by anomaly severity, so it picks the aggregator
  (`frontend`, `checkoutservice`) that is a *victim*, not the *cause*.
- We propose **TORAI++**, a post-hoc re-ranker using the call graph.
  It lifts RE3-OB from **0.03 → 0.97** with **zero regression** on RE3-TT.

## Headline numbers

| Method      | RE3-OB (n=30) | RE3-TT (n=30) | Overall (n=60) |
|-------------|---------------|---------------|----------------|
| TORAI       | 0.03          | 1.00          | 0.52           |
| **TORAI++** | **0.97**      | **1.00**      | **0.98**       |

## Repository contents
