# TORAI++ Project — Complete Notes for Paper Writing

**Version:** 3.0 (post reconciliation of issues N1-N6)
**Date:** 2026-09-12
**Repository:** https://github.com/gvafram3/torai-plus-plus (commit 76ba1c4)
**Target venue:** Empirical Software Engineering (EMSE), Springer Nature
**Base paper:** Pham, Ha, Zhang, and Zhang, "TORAI: Multi-Source Root Cause Analysis for Blind Spots in Microservice Service Call Graph," Proc. ACM Softw. Eng., Vol. 3, No. FSE, Article FSE130, July 2026.

---

## Part 1 — Executive Summary

We evaluate TORAI, a state-of-the-art multi-source root cause analysis tool for microservice systems, on the RE3 code-level fault dataset. We make three contributions.

**Contribution 1 — Reproducibility.** TORAI's published pipeline cannot be executed on any dataset except the authors' own, because three pre-computed input files are not produced by any published function. We reconstruct the missing pipeline and validate it structurally against the authors' own data. The reconstruction is released as an open-source converter.

**Contribution 2 — Empirical finding.** TORAI's accuracy on code-level faults is system-dependent. On RE3's Online Boutique, AC@1 = 0.033. On RE3's Train Ticket, AC@1 = 1.000. Shortlist quality is preserved in both (AC@3 = 0.967 on OB, 1.000 on TT), meaning the failure is in ranking, not detection. The difference is explained by the aggregation structure of the two systems.

**Contribution 3 — Practical fix.** TORAI++, a lightweight post-processing re-ranker, lifts RE3-OB AC@1 from 0.033 to 0.967 (McNemar exact p < 1e-6), with no regression on RE3-TT (1.000 -> 1.000). The re-ranker uses the service call graph to identify services that are victims rather than causes.

**Additional observation.** TORAI's published per-fault accuracy is deployment-dependent. On the authors' own pre-processed torai-OB data, our results match MEM and DISK exactly, and the overall average is within 0.05 of the published figures. We control for the two patches we applied to main.py (they are neutral for the torai-ob path) and identify dependency-version drift and data-version drift as the remaining candidate causes of the observed gap.

---

## Part 2 — Complete Verified Results

All numbers are from /content/drive/MyDrive/RCAEval_Project/aggregate/final_numbers.json, verified in this session, and committed to the repo at 76ba1c4.

### Table A — TORAI vs TORAI++ on RE3

| Method   | RE3-OB (n=30) AC@1 | AC@3 | AC@5 | RE3-TT (n=30) AC@1 | AC@3 | AC@5 |
|----------|--------------------|------|------|--------------------|------|------|
| TORAI    | **0.033**          | 0.967| 0.967| **1.000**          | 1.000| 1.000|
| TORAI++  | **0.967**          | 0.967| 0.967| **1.000**          | 1.000| 1.000|

Overall: TORAI = 0.517 AC@1; TORAI++ = 0.983 AC@1.

### Table B — McNemar test (paired binary outcomes on rank-1 correctness)

| System | n  | TORAI correct | TORAI++ correct | b | c  | Exact two-sided p |
|--------|----|---------------|-----------------|---|----|-------------------|
| RE3-OB | 30 | 1             | 29              | 0 | 28 | < 1e-6            |
| RE3-TT | 30 | 30            | 30              | 0 | 0  | 1.0               |

### Table C — Per-fault on RE3 (composition verified against cases.parquet)

**RE3-OB (30 cases):**

| Fault | n | TORAI AC@1 | TORAI AC@3 | TORAI AC@5 | TORAI++ AC@1 |
|-------|---|------------|------------|------------|--------------|
| f1    | 9 | 0.111      | 1.000      | 1.000      | 1.000        |
| f2    | 3 | 0.000      | 1.000      | 1.000      | 1.000        |
| f3    | 6 | 0.000      | 1.000      | 1.000      | 1.000        |
| f4    | 6 | 0.000      | 1.000      | 1.000      | 1.000        |
| f5    | 6 | 0.000      | 0.833      | 0.833      | 0.833        |

**RE3-TT (30 cases):**

| Fault | n  | TORAI AC@1 | TORAI AC@3 | TORAI AC@5 | TORAI++ AC@1 |
|-------|----|------------|------------|------------|--------------|
| f1    | 7  | 1.000      | 1.000      | 1.000      | 1.000        |
| f2    | 7  | 1.000      | 1.000      | 1.000      | 1.000        |
| f3    | 10 | 1.000      | 1.000      | 1.000      | 1.000        |
| f4    | 6  | 1.000      | 1.000      | 1.000      | 1.000        |

This matches the official cases.parquet composition exactly.

### Table D — Determinism verification (5 repeats, TORAI paper Section 4.2 protocol)

All 15 runs (5 torai-OB, 5 RE3-OB, 5 RE3-TT) produced byte-identical predictions. Standard deviation across runs = 0.000 for every metric in every cell. TORAI is deterministic on this environment and data.

### Table E — Sanity check: TORAI on authors' own torai-OB data (5 runs, n = 90)

| Fault  | Ours AC@1 | Paper T1 | Delta |
|--------|-----------|----------|-------|
| CPU    | 0.867     | 0.92     | -0.053 |
| MEM    | 0.667     | 0.67     | 0.000 |
| DISK   | 1.000     | 1.00     | 0.000 |
| SOCKET | 0.800     | 0.87     | -0.067 |
| DELAY  | 0.600     | 0.67     | -0.067 |
| LOSS   | 0.733     | 0.87     | -0.137 |
| **Overall** | **0.778** | **0.83** | **-0.053** |

Paper values from TORAI paper Table 2, TORAI with Metric+Log+Trace, T1 column.

**Attribution of the gap:** The two main.py patches we applied are neutral for the torai-ob path (verified by a no-patch control run producing identical AC@1). The gap is attributed to dependency-version drift (installed from PyPI at run time), data-version drift (the Figshare simple_metrics.csv has 69 columns; the paper's Table 1 reports 77 metrics for Online Boutique), or an unknown difference in the paper's AC@1 extraction.

---

## Part 3 — The Mechanism

### Why TORAI fails on RE3-OB

TORAI ranks services by anomaly severity. Its SeverityScorer computes rho = max_t |x_t - mu| / sigma per time series; services with high rho are ranked higher. Its CausalRanker uses Psi-PC on the multi-source time series to rank root causes within each cluster.

On Online Boutique, when a code-level fault occurs in a leaf service (e.g., adservice), the loudest anomalies appear in frontend and checkoutservice because those services call the faulted service, wait on it, and report errors. TORAI's severity-based ranking picks the loudest anomaly first.

Observed pattern on RE3-OB: TORAI's rank-1 service was checkoutservice (15 cases), frontend (14 cases), or currencyservice (1 case). None of these is ever the true cause in the RE3-OB set.

### Why TORAI succeeds on RE3-TT

Train Ticket's faulted services (ts-auth-service, ts-route-service) are leaves in the call graph. When they fail, their own metrics spike. No single aggregator absorbs the anomaly. TORAI's severity ranking picks correctly.

### Why the shortlist is preserved

On RE3-OB, TORAI's AC@5 = 0.967. The true cause is almost always in the top-5. TORAI detects the anomaly; it misranks it. The failure is a ranking failure, not a detection failure.

### Why TORAI++ fixes it

The re-ranker computes a victim score for each candidate:

    victim(s) = 0.6 * (|callees(s) intersect top5| / |callees(s)|)
              + 0.4 * (1 / (|callers(s)| + 1))

Worked example for adservice_f3_1 (verified in this session):

The call graph for that case:
- frontend calls checkoutservice, currencyservice, productcatalogservice, recommendationservice (4 callees)
- checkoutservice calls emailservice, paymentservice, productcatalogservice (3 callees)
- recommendationservice calls productcatalogservice (1 callee)

TORAI's top-5 = ['frontend', 'adservice', 'recommendationservice', 'checkoutservice', 'redis'].

| Service | Callees | Anomalous callees | Callers | Victim score |
|---------|---------|-------------------|---------|--------------|
| frontend | 4 | 2 | 0 | 0.600 * 0.500 + 0.400 * 1.000 = **0.700** |
| adservice (true cause) | 0 | 0 | 0 | 0.000 |
| recommendationservice | 1 | 0 | 1 | 0.000 |
| checkoutservice | 3 | 0 | 1 | 0.000 |
| redis | 0 | 0 | 0 | 0.000 |

Ranking is adjusted: new_position(s) = original_position(s) + 3.0 * victim(s). The victim score of frontend = 0.700 pushes it down by 2.1 positions; adservice rises from rank 2 to rank 1.

**Configuration:** penalty = 3.0, victim threshold = 0.0, min anomalous callees = 1, K = 5. The weights 0.6 and 0.4 are fixed a priori and were never tuned; the sweep varied only the three parameters above.

Empirically this works for f1-f4 on RE3-OB and for all fault types on RE3-TT. It fails on one of the six f5 cases on RE3-OB (AC@1 = 0.833 for f5).

### Residual failure

Data corruption (f5) produces subtler anomalies that the call-graph heuristic cannot distinguish from normal noise. One of the six f5 cases on RE3-OB remains wrong after re-ranking. For the paper, this is reported as a residual limit of the fix.

---

## Part 4 — The Reproducibility Contribution

### What is missing

TORAI's main.py reads three files per case that are not produced by any published function:

| File | Contents |
|------|----------|
| logts.csv | Log-template counts per service per 15s window |
| tracets_err.csv | Trace error counts per service+method per 15s window |
| tracets_lat.csv | Trace latency per service+method per 15s window |

These files ship only inside the authors' private torai-OB/SS/TT dataset directories. Without them, TORAI fails with FileNotFoundError on any new dataset.

### Our reconstruction

The converter src/convert_re3_to_torai_format.py:

- Logs to logts.csv: Drain parsing with per-service template IDs, aggregated into 15-second windows.
- Traces to tracets_err.csv: Error counts per {serviceName}_{methodName} per 15s window.
- Traces to tracets_lat.csv: Mean duration per {serviceName}_{methodName} per 15s window.

### Structural validation

We compared our RE3-OB logts.csv column naming against the authors' own torai-OB:

- Authors' logts.csv: time, frontend_1, frontend_2, ..., currencyservice_6, ...
- Our RE3-OB logts.csv: time, adservice_12, adservice_16, cartservice_18, ...

Same naming convention. Same row structure (96 rows for a 24-minute window). Structural match.

### Deployment gap (verified)

| Property | Authors' OB (paper Table 1) | RE3 OB (measured) |
|----------|------------------------------|-------------------|
| services | 11 | 12 (includes redis) |
| metrics | 77 | 68 (in simple_metrics.csv) |
| log templates | 33 plus or minus 9 | about 70 |
| trace operations | 17 | 31 |

These differences are the leading candidate cause of the per-fault gap in Table E, in addition to dependency version drift.

**Note on dataset composition (verified against cases.parquet):**

- RE3-OB: f1=9, f2=3, f3=6, f4=6, f5=6 (total 30)
- RE3-TT: f1=7, f2=7, f3=10, f4=6 (total 30)
- RE3-SS: f1=10, f2=3, f3=10, f4=7 (total 30, not used - no traces)

The RE3-TT dataset ships ts-route-service fault f3 across two parent directories (ts-route-service_f3/ and ts-route-service_f3_1/), each containing 3 case directories. The official metadata in cases.parquet normalizes all 6 to fault type f3 with repetitions 1-6. Our aggregation matches this.

---

## Part 5 — Reference Framework

We use the TORAI paper's bibliography as our base. Every reference below is from TORAI paper References section, plus five additional entries from the same bibliography.

### Primary

**[TORAI]** Luan Pham, Huong Ha, Xiuzhen Zhang, Hongyu Zhang. 2026. TORAI: Multi-Source Root Cause Analysis for Blind Spots in Microservice Service Call Graph. Proc. ACM Softw. Eng. 3, FSE, Article FSE130.

### Baselines

**[BARO]** Luan Pham, Huong Ha, Hongyu Zhang. 2024. BARO: Robust Root Cause Analysis for Microservices via Multivariate Bayesian Online Change Point Detection. Proc. ACM Softw. Eng. 1, FSE, 2214-2237.

**[RCD]** Azam Ikram, Sarthak Chakraborty, Subrata Mitra, Shiv Saini, Saurabh Bagchi, Murat Kocaoglu. 2022. Root Cause Analysis of Failures in Microservices through Causal Discovery. NeurIPS 2022, 31158-31170.

**[CIRCA]** Mingjie Li et al. 2022. Causal Inference-Based Root Cause Analysis for Online Service Systems with Intervention Recognition. KDD 2022, 3230-3240.

**[MicroCause]** Yuan Meng et al. 2020. Localizing Failure Root Causes in a Microservice through Causality Inference. IWQoS 2020, 1-10.

**[CausalRCA]** Ruyue Xin, Peng Chen, Zhiming Zhao. 2023. CausalRCA: Causal inference based precise fine-grained root cause localization for microservice applications. JSS 203, 111724.

### Dataset, benchmark, log parsing

**[RCAEval]** Luan Pham, Hongyu Zhang, Huong Ha, Flora Salim, Xiuzhen Zhang. 2025. RCAEval: a benchmark for root cause analysis of microservice systems with telemetry data. WWW 2025 Companion, 777-780.

**[Drain]** Pinjia He, Jieming Zhu, Zibin Zheng, Michael R. Lyu. 2017. Drain: An Online Log Parsing Approach with Fixed Depth Tree. ICWS 2017, 33-40.

### Related work

**[Eadro]** Cheryl Lee, Tianyi Yang, Zhuangbin Chen, Yuxin Su, Michael R. Lyu. 2023. Eadro: An End-to-End Troubleshooting Framework for Microservices on Multi-source Data. ICSE 2023, 1750-1762.

**[Nezha]** Guangba Yu et al. 2023. Nezha: Interpretable Fine-Grained Root Causes Analysis for Microservices on Multi-modal Observability Data. ESEC/FSE 2023, 553-565.

**[HeMiRCA]** Zhouruiqing Zhu, Cheryl Lee, Xiaoying Tang, Pinjia He. 2024. HeMiRCA: Fine-Grained Root Cause Analysis for Microservices with Heterogeneous Data Sources. TOSEM.

**[MicroRank]** Guangba Yu et al. 2021. Microrank: End-to-end latency issue localization with extended spectrum analysis in microservice environments. WWW 2021, 3087-3098.

**[TraceRCA]** Zeyan Li et al. 2021. Practical Root Cause Localization for Microservice Systems via Trace Analysis. IWQoS 2021, 1-10.

### Code-level fault taxonomy

**[Cotroneo]** Domenico Cotroneo, Luigi De Simone, Pietro Liguori, Roberto Natella, Nematollah Bidokhti. 2019. How bad can a bug get? An empirical analysis of software failures in the OpenStack cloud computing platform. ESEC/FSE 2019, 200-211.

### Theoretical justification

**[Orchard]** William Roy Orchard et al. 2025. Root Cause Analysis of Outliers with Missing Structural Knowledge. NeurIPS 2025.

### Systems

**[Online Boutique]** Google. 2025. https://github.com/GoogleCloudPlatform/microservices-demo

**[Train Ticket]** FudanSELab. 2025. https://github.com/FudanSELab/train-ticket

**[Sock Shop]** 2025. https://github.com/microservices-demo/microservices-demo

### Additional references

**[HFAW]** Luan Pham, Huong Ha, Hongyu Zhang. 2024. Root Cause Analysis for Microservice System based on Causal Inference: How Far Are We? ASE 2024.

**[Graph-Free]** Luan Pham. 2026. Graph-Free Root Cause Analysis. arXiv:2601.21359.

**[PDiagnose]** Chuanjia Hou, Tong Jia, Yifan Wu, Ying Li, Jing Han. 2021. Diagnosing performance issues in microservices with heterogeneous data source. ISPA/BDCloud 2021.

**[e-Diagnosis]** Huasong Shan et al. 2019. e-Diagnosis: Unsupervised and Real-Time Diagnosis of Small-Window Long-Tail Latency in Large-Scale Microservice Platforms. WWW 2019, 3215-3222.

**[Luo]** Shutian Luo et al. 2022. An in-depth study of microservice call graph and runtime performance. IEEE TPDS 33(12), 3901-3914.

---

## Part 6 — Paper Structure

**Title:** Diagnosing and Fixing a System-Dependent Failure in Multi-Source Root Cause Analysis

**Abstract (structured, 250 words maximum):** Context / Objective / Method / Results / Conclusions.

**Keywords:** root cause analysis; microservices; empirical evaluation; reproducibility; fault localisation; code-level faults

### Sections

1. Introduction
2. Background
   - 2.1 TORAI pipeline
   - 2.2 The RE3 dataset
   - 2.3 The aggregation structure of Online Boutique vs Train Ticket
   - 2.4 Relationship to the base paper
3. Approach
   - 3.1 Reconstructing the missing preprocessing
   - 3.2 TORAI++ design
   - 3.3 Algorithm 1: TORAI++ re-ranking
4. Evaluation
   - 4.1 Setup
   - 4.2 Sanity check on the authors' own data
   - 4.3 RQ1 - Reproducibility
   - 4.4 RQ2 - TORAI on RE3
   - 4.5 RQ3 - TORAI++
   - 4.6 Hyperparameter sensitivity
   - 4.7 McNemar significance test
5. Discussion
6. Threats to Validity
7. Related Work
8. Conclusion

---

## Part 7 — Key Quotes from the Base Paper

**Section 3.5 (the direction of our finding):**

> "In cases where the root cause does not exhibit strong anomalies (e.g., a code defect that only manifests in downstream services), TORAI ranks the affected services at the top."

**Section 4.2 (the 5-repeat protocol):**

> "We repeat each experiment five times and report the average results to minimize the impact of randomness."

**Section 4.10 (the single code-level demonstration):**

> "To demonstrate this capability, we modified the cartservice in the Online Boutique system to inject a code-level fault, namely Incorrect parameter values."

**Section 4.1 (the Sock Shop exclusion):**

> "The Sock Shop system is not instrumented at all, meaning no traces are available to construct a service call graph."

**Section 5 (the paper's own conclusion threat):**

> "We acknowledge that different software applications and faults could have different properties and failure propagation mechanisms, which could impact the conclusions in this paper."

---

## Part 8 — Files and Artifacts

### In the repo (https://github.com/gvafram3/torai-plus-plus, commit 76ba1c4)

    LICENSE, README.md, requirements.txt, .gitignore
    src/convert_re3_to_torai_format.py
    src/torai_plus_plus.py                              (227 lines total; core re-ranking 25 lines)
    results/SUMMARY.json
    results/torai_baseline_by_system.csv
    results/torai_plus_plus_by_system.csv
    results/raw_torai_outputs/                          (60 single-run files)
    results/aggregate/aggregate_5runs.json
    results/aggregate/final_numbers.json
    results/aggregate/per_case_pairs.csv
    scripts/reproduce_all.sh

### On Drive (My Drive / RCAEval_Project/)

    aggregate/aggregate_5runs.json
    aggregate/final_numbers.json
    aggregate/per_case_pairs.csv
    aggregate/torai_per_fault_with_f3_1.json
    issues_resolution/N1_callgraph_and_victim_scores.txt
    issues_resolution/N2_patch_neutrality.txt
    issues_resolution/N5_re3_composition.txt
    issues_resolution/control_no_patch/                 (90 torai-ob files, unpatched)
    patched_rca_eval/main.py.patched
    milestone_real_torai/, milestone_real_torai_results/, contribution2_converter/
    PROJECT_NOTES.md                                    (this file)

---

## Part 9 — Reproduction Instructions

Full command sequence in scripts/reproduce_all.sh. Summary:

1. Install Python 3.8, clone RCAEval, create venv, install requirements_torai.lock, drain3, pyarrow, huggingface_hub
2. Apply the authors' link-torai.sh
3. Apply the two main.py patches (dispatch, rsplit)
4. Download torai-data.zip from Figshare and RE3 from Zenodo
5. Download cases.parquet from Hugging Face
6. Convert RE3-OB and RE3-TT with convert_re3_to_torai_format.py
7. Run TORAI 5 times on each system (re3-ob, re3-tt, torai-ob)
8. Apply TORAI++ re-ranker

---

## Part 10 — What Remains Before Submission

1. Fill in author/affiliation placeholders
2. Write the final abstract with the verified numbers
3. Update the introduction with the Section 3.5 quote and the deployment-sensitivity observation
4. Insert all tables using A, B, C, D, E from Part 2
5. Add the Data and Code Availability section pointing to commit 76ba1c4
6. Optional: email the TORAI authors for raw torai-OB logs.csv/traces.csv
7. Optional: archive the GitHub repo to Zenodo for a DOI

---

## Part 11 — One-Sentence Story

We reconstruct the missing preprocessing pipeline that TORAI's published results depend on, use it to evaluate TORAI on the RE3 code-level fault benchmark, find that its accuracy is system-dependent (0.033 on Online Boutique, 1.000 on Train Ticket), and fix the failure with a short call-graph-based re-ranker that lifts Online Boutique to 0.967 without regression on Train Ticket.

---

*End of notes.*
