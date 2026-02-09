# Cluster Case Study Field Notes (Synchronized)

Last updated: 2026-02-09.

## Table of Contents
1. [Scope](#scope)
2. [Synchronization Status](#synchronization-status)
3. [Required Issue Ledger](#required-issue-ledger)
4. [Evidence Matrix](#evidence-matrix)
5. [Coherence Notes](#coherence-notes)
6. [Repro Entry Point](#repro-entry-point)

This file is the validated evidence ledger aligned to the canonical run in `field-report.md`.

## Scope
| Item | Value |
| --- | --- |
| In-scope nodes | `node1`, `node2` (4x GB200 per node, 8 GPUs total) |
| Excluded nodes | none |
| Canonical run | `2026-02-09_fresh_full_suite_e2e_fixed` |
| Canonical manifest | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| Canonical suite steps | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json) |

## Synchronization Status
| Surface | Canonical run aligned | Notes |
| --- | --- | --- |
| `field-report.md` | yes | Fully repointed to `2026-02-09_fresh_full_suite_e2e_fixed` |
| `field-report-notes.md` | yes | Rebuilt to the same canonical run and issue set |
| Evidence links | yes | All local links in both markdown files resolve |

## Required Issue Ledger
| Required issue | Status in canonical package | Evidence |
| --- | --- | --- |
| Missing node2 fio artifact in canonical package (`node2_fio.json` absent). | Present gap | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| No multinode vLLM artifact in canonical package. | Present gap | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| No nvbandwidth bundle in canonical package. | Present gap | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| Health suite had GDR requested, but effective GDR was false due non-CUDA IB local checks. | Present gap | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json) |
| Tail latency knee is severe at high concurrency (throughput up, TTFT/p99 TTFT much worse). | Confirmed risk | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv)<br/>[docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png) |

## Evidence Matrix
| Claim | Data Evidence | Visualization Evidence | Status |
| --- | --- | --- | --- |
| Full suite completed cleanly (`40/40` successful). | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json) | [docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_cluster_story_dashboard.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_cluster_story_dashboard.png) | Backed |
| Multi-node NCCL path is healthy (`all_reduce` peak `840.10 GB/s`). | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json) | [docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_bw_vs_msg.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_bw_vs_msg.png)<br/>[docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_scaling_efficiency.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_scaling_efficiency.png) | Backed |
| vLLM serving shows a severe tail-latency knee (`c=512`: `52764.98 tok/s`, mean TTFT `5226.64 ms`, p99 TTFT `11247.96 ms`). | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv) | [docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_total_tok_s_vs_concurrency.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_total_tok_s_vs_concurrency.png)<br/>[docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png) | Backed |
| NVLink topology artifacts show full `NV18` mesh (`6/6` pairs) on both nodes. | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.json) | [docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.png)<br/>[docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.png) | Backed |
| FP4 checks passed with host parity (`max pairwise median gap 2.06%`, threshold `5.0%`; attestation `pass`). | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_smoke_skew_guard.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_smoke_skew_guard.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_attestation_consistency.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_attestation_consistency.json) | [docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_cluster_perf_grouped_gemm_tflops.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_cluster_perf_grouped_gemm_tflops.png)<br/>[docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_cluster_perf_grouped_gemm_tflops.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_cluster_perf_grouped_gemm_tflops.png) | Backed |
| Runtime/CVE collection executed in the suite and health package; CVE-2025-23266 and CVE-2025-23267 are `pass` on both nodes. | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1_container_runtime.txt](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1_container_runtime.txt)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node2_container_runtime.txt](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node2_container_runtime.txt)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json) | n/a | Backed |

## Coherence Notes
`field-report.md` and `field-report-notes.md` now use the same canonical run ID (`2026-02-09_fresh_full_suite_e2e_fixed`) and the same required issue set.
Historical artifacts are referenced only where they support normal-vs-weird interpretation.

## Repro Entry Point
Use the same invocation listed in [field-report.md](field-report.md#repro-steps).
