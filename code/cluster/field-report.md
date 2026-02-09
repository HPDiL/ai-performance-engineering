# Cluster Perf Field Report (GB200, 2 Nodes)

Last updated: 2026-02-09.

## Table of Contents
1. [TL;DR](#tldr)
2. [Scope + Canonical Artifacts](#scope--canonical-artifacts)
3. [Cluster Story (First Contact)](#cluster-story-first-contact)
4. [Benchmark A (Networking Story)](#benchmark-a-networking-story)
5. [Benchmark B (Inference Story)](#benchmark-b-inference-story)
6. [Node Parity Snapshot (node1 vs node2)](#node-parity-snapshot-node1-vs-node2)
7. [NVLink/NVSwitch Topology Snapshot](#nvlinknvswitch-topology-snapshot)
8. [GB200 Extensions (Enabled in Canonical Run)](#gb200-extensions-enabled-in-canonical-run)
9. [Normal vs Weird Log](#normal-vs-weird-log)
10. [Gaps, Risks, and Smell Checks](#gaps-risks-and-smell-checks)
11. [Required Issues (Explicit)](#required-issues-explicit)
12. [Stakeholder Recommendations (Prioritized)](#stakeholder-recommendations-prioritized)
13. [Repro Steps](#repro-steps)
14. [Reproducibility Package](#reproducibility-package)
15. [Activity Log](#activity-log)
16. [Appendix (Coverage vs Case-Study Goals)](#appendix-coverage-vs-case-study-goals)

## TL;DR
| Topic | Summary |
| --- | --- |
| Scope | In-scope hosts: `node1`, `node2`; 4x GB200 per host (8 GPUs total); excluded nodes: none. |
| Canonical run | `2026-02-09_fresh_full_suite_e2e_fixed` |
| Suite status | `40/40` steps succeeded (`exit_code=0` for all steps). |
| NCCL headline | Health-suite all-reduce peak bus bandwidth: `840.10 GB/s` (16 GiB payload point). |
| vLLM headline | Single-node sweep peaks at `52,764.98 tok/s` at concurrency `512`, with mean TTFT `5,226.64 ms` and p99 TTFT `11,247.96 ms` (clear latency knee). |
| Train-step sanity | BF16/FSDP train-step scales from `103,587.89 tok/s` (1 node) to `207,313.23 tok/s` (2 nodes), `2.00x` throughput scale. |
| FP4 status | FP4 skew guard passed (`2.06%` max pairwise median gap, threshold `5.0%`), attestation status `pass`. |
| OOB vs fabric | OOB TCP is `7.57/7.40 Gbps` (fwd/rev), far below IB/NCCL data-path capacity. |
| Runtime/CVE | Container runtime evidence collected per host; CVE-2025-23266/23267 status `pass` on both hosts. |
| Key gaps in canonical package | No multinode vLLM canary artifact, no nvbandwidth bundle, and no `node2_fio.json` despite a parity placeholder path. |

## Scope + Canonical Artifacts
| Scope item | Value |
| --- | --- |
| Nodes in-scope | `node1`, `node2` |
| Excluded nodes | none |
| GPUs per node | 4 |
| Canonical manifest | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| Canonical suite steps | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json) |
| Discovery/meta | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta.json) |
| Preflight + runtime/CVE | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_preflight_services.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_preflight_services.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1_container_runtime.txt](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1_container_runtime.txt)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node2_container_runtime.txt](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node2_container_runtime.txt) |

## Cluster Story (First Contact)
| UTC time | Milestone |
| --- | --- |
| `18:26:55` | bootstrap completed on both nodes |
| `18:26:59` | strict preflight completed (`persistenced` + `imex` + `dcgm`) |
| `18:27:40` | first 2-node NCCL run completed |
| `18:30:27` | extended health suite completed |
| `18:43:39` | vLLM single-node sweep completed |
| `18:59:11` | dashboard + manifest refresh completed |

Time-to-first multi-node signal was ~45 seconds from preflight completion (`18:26:59` to `18:27:40`).

<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_cluster_story_dashboard.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_cluster_story_dashboard.png" alt="Cluster story dashboard" width="920"/></a></p>

Data: [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json)

## Benchmark A (Networking Story)
| Metric | Value |
| --- | --- |
| NCCL all-reduce peak (health suite) | `840.10 GB/s` |
| NCCL all-gather peak (health suite) | `655.33 GB/s` |
| NCCL reduce-scatter peak (health suite) | `676.27 GB/s` |
| NCCL alltoall peak (health suite) | `601.08 GB/s` |
| torch distributed all-reduce peak | `720.73 GB/s` |
| IB write BW per active HCA (`mlx5_0/1/4/5`) | `~387.13-387.14 Gbps` |
| OOB TCP throughput (fwd/rev) | `7.57 / 7.40 Gbps` |
| Suite-A standalone NCCL max (single node, 64 MiB top point) | `549.57 GB/s` |
| Suite-A standalone NCCL max (2 nodes, 64 MiB top point) | `416.25 GB/s` |

Interpretation: the health-suite message-size sweep (up to 16 GiB) shows strong multi-node all-reduce behavior; the lower standalone NCCL peaks are from a smaller max payload (64 MiB), so the two measurements are not directly comparable.

<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_bw_vs_msg.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_bw_vs_msg.png" alt="2-node NCCL bus bandwidth vs message size" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_scaling_efficiency.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_scaling_efficiency.png" alt="2-node NCCL scaling efficiency" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_nccl_algo_comparison.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_nccl_algo_comparison.png" alt="NCCL algorithm comparison" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_iperf3_oob_tcp.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_iperf3_oob_tcp.png" alt="OOB TCP throughput" width="920"/></a></p>

Data: [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_nccl.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_nccl.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_nccl_algo_comparison.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_nccl_algo_comparison.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_iperf3_oob_tcp.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_iperf3_oob_tcp.json)

## Benchmark B (Inference Story)
| Concurrency | Total tok/s | Output tok/s | Mean TTFT (ms) | p99 TTFT (ms) | p99 TPOT (ms) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `32` | `14042.84` | `7021.42` | `171.87` | `371.00` | `4.52` |
| `64` | `26216.85` | `13108.43` | `138.75` | `245.20` | `5.67` |
| `128` | `38519.67` | `19259.84` | `170.94` | `473.58` | `7.79` |
| `256` | `49911.06` | `24955.53` | `844.27` | `2299.99` | `11.30` |
| `512` | `52764.98` | `26382.49` | `5226.64` | `11247.96` | `19.57` |

Interpretation: throughput continues increasing up to `c=512`, but latency degrades sharply from `c=256` onward; this run clearly exposes a tail-latency knee.

<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_total_tok_s_vs_concurrency.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_total_tok_s_vs_concurrency.png" alt="vLLM total tokens/sec vs concurrency" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png" alt="vLLM TTFT vs concurrency" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_tpot_vs_concurrency.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_tpot_vs_concurrency.png" alt="vLLM TPOT vs concurrency" width="920"/></a></p>

Data: [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.jsonl](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.jsonl)

## Node Parity Snapshot (node1 vs node2)
| Metric | node1 | node2 | node2/node1 |
| --- | ---: | ---: | ---: |
| GEMM mean TFLOPS (`avg_tflops`) | `1532.61` | `1521.72` | `0.993x` |
| GEMM min TFLOPS | `1497.68` | `1475.87` | `0.985x` |
| NUMA local memcpy BW (GB/s) | `134.77` | `136.25` | `1.011x` |
| fio seq read (MB/s) | `1449.77` | `missing artifact` | `n/a` |

<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_gemm_gpu_sanity.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_gemm_gpu_sanity.png" alt="GEMM parity chart" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_numa_mem_bw.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_numa_mem_bw.png" alt="Node1 NUMA bandwidth" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_numa_mem_bw.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_numa_mem_bw.png" alt="Node2 NUMA bandwidth" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_fio.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_fio.png" alt="Node1 fio chart" width="920"/></a></p>

Data: [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_gemm_gpu_sanity.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_gemm_gpu_sanity.csv)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_gemm_gpu_sanity.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_gemm_gpu_sanity.csv)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_numa_mem_bw.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_numa_mem_bw.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_numa_mem_bw.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_numa_mem_bw.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_fio.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_fio.json)

## NVLink/NVSwitch Topology Snapshot
| Node | GPU count | NVLink pair count | Link type summary |
| --- | ---: | ---: | --- |
| node1 | `4` | `6` | full `NV18` mesh |
| node2 | `4` | `6` | full `NV18` mesh |

<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.png" alt="Node1 NVLink topology" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.png" alt="Node2 NVLink topology" width="920"/></a></p>

Data: [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.json)

## GB200 Extensions (Enabled in Canonical Run)
| Extension | Result |
| --- | --- |
| All-reduce stability (`2 GiB`, 200 iters) | mean `805.61 GB/s`, CV `2.161%`, jitter assessment `moderate_jitter` |
| All-reduce latency composition (`4 GiB`) | one-large `805.75 GB/s` vs many-small `119.09 GB/s` (`6.77x` bandwidth ratio) |
| Control-plane collective overhead | `all_reduce_tensor 0.2334 ms` vs `all_gather_tensor 0.3470 ms` vs `all_gather_object 1.6599 ms` |
| NCCL algorithm comparison | auto `840.08`, NVLS `840.00`, Ring `698.22`, Tree `546.79` (GB/s peaks) |
| C2C memcpy (pinned) | H2D `125.81 Gbps`, D2H `124.49 Gbps`; 4-byte lat H2D `1.958 us`, D2H `1.832 us` |
| Train-step BF16/FSDP | single `103,587.89 tok/s`, multi `207,313.23 tok/s` (`2.00x`) |
| FP4 skew + attestation | skew guard `pass` (`2.06%` max gap, threshold `5.0%`), attestation `pass` |
| MAMF spread | min `1528.77 TFLOPS`, max `1725.89 TFLOPS` (`11.42%` spread) |

<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_allreduce_stability.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_allreduce_stability.png" alt="All-reduce stability" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_allreduce_latency_comp.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_allreduce_latency_comp.png" alt="All-reduce latency composition" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_allgather_control_plane.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_allgather_control_plane.png" alt="Control-plane collective overhead" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_c2c_memcpy_bw.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_c2c_memcpy_bw.png" alt="C2C memcpy bandwidth" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_c2c_memcpy_lat.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_c2c_memcpy_lat.png" alt="C2C memcpy latency" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_single_node_torchrun_train_step.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_single_node_torchrun_train_step.png" alt="Single-node train-step" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_multinode_torchrun_train_step.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_multinode_torchrun_train_step.png" alt="Multi-node train-step" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_cluster_perf_grouped_gemm_tflops.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_cluster_perf_grouped_gemm_tflops.png" alt="Node1 FP4 grouped GEMM" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_cluster_perf_grouped_gemm_tflops.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node2_cluster_perf_grouped_gemm_tflops.png" alt="Node2 FP4 grouped GEMM" width="920"/></a></p>
<p><a href="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_mamf_straggler.png"><img src="docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_mamf_straggler.png" alt="MAMF spread" width="920"/></a></p>

Data: [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_allreduce_stability.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_allreduce_stability.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_allreduce_latency_comp.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_allreduce_latency_comp.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_allgather_control_plane.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_allgather_control_plane.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_c2c_memcpy.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_c2c_memcpy.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_single_node_torchrun_train_step.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_single_node_torchrun_train_step.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_multinode_torchrun_train_step.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_multinode_torchrun_train_step.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_smoke_skew_guard.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_smoke_skew_guard.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_attestation_consistency.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_attestation_consistency.json)

## Normal vs Weird Log
| Area | Normal (canonical run) | Weird / notable behavior | Evidence |
| --- | --- | --- | --- |
| Multi-node NCCL | all-reduce peak `840.10 GB/s` | historical low-band regime around `~529.64 GB/s` exists in prior incident runs | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json)<br/>[results/structured/2026-02-07_224500_nccl_16g_baseline_ppr4_bindnone_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-07_224500_nccl_16g_baseline_ppr4_bindnone_node1node2_cluster_health_suite_summary.json) |
| Service state | preflight verified `persistenced/imex/dcgm` active on both nodes | prior outage showed NVLS init and serving startup failures when service state was wrong | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_preflight_services.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_preflight_services.json)<br/>[results/structured/2026-02-08_025442_cloud_eval_full_health_suite_extended_node1node2_nccl_all_reduce_perf.error_excerpt.txt](results/structured/2026-02-08_025442_cloud_eval_full_health_suite_extended_node1node2_nccl_all_reduce_perf.error_excerpt.txt) |
| Inference knee | predictable throughput scaling then sharp TTFT knee at `c=512` | p99 TTFT at max throughput is very high (`11.25 s`) and must be policy-gated | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv) |
| FP4 host parity | skew guard and attestation both pass | median gap (`2.06%`) is still under threshold but noticeably higher than prior `~1%` values | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_smoke_skew_guard.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_smoke_skew_guard.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_attestation_consistency.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_fp4_attestation_consistency.json) |

## Gaps, Risks, and Smell Checks
| Severity | Finding | Why this matters | Evidence |
| --- | --- | --- | --- |
| High | `node2_fio.json` missing in canonical package | storage parity is incomplete for this run; parity summary includes a placeholder path only | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json) |
| High | No multinode vLLM serving artifact in canonical run | inference story is strong for single-node only; multinode serving path is not validated in this package | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| Medium | No nvbandwidth bundle in canonical run | direct host-device + D2D bandwidth evidence is missing from this package | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| Medium | Health suite requested GDR, but effective GDR is `false` | `--health-gdr` was passed but local IB tools did not use CUDA path, so GDR verification is incomplete | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json) |
| Medium | Tail latency knee is severe at high concurrency (throughput up, TTFT/p99 TTFT much worse) | `c=512` maximizes throughput but degrades user-facing latency substantially (`mean TTFT 5226.64 ms`, `p99 TTFT 11247.96 ms`) | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv)<br/>[docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png) |
| Medium | MAMF spread is `11.42%` across 8 GPUs | this is larger than desired for tight straggler confidence and should be trended across reruns | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_gpu0_mamf_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_gpu0_mamf_summary.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_gpu3_mamf_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_gpu3_mamf_summary.json) |

## Required Issues (Explicit)
| Required issue (verbatim) | Status in canonical package | Evidence |
| --- | --- | --- |
| Missing node2 fio artifact in canonical package (`node2_fio.json` absent). | Present gap | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node_parity_summary.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| No multinode vLLM artifact in canonical package. | Present gap | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| No nvbandwidth bundle in canonical package. | Present gap | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| Health suite had GDR requested, but effective GDR was false due non-CUDA IB local checks. | Present gap | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json) |
| Tail latency knee is severe at high concurrency (throughput up, TTFT/p99 TTFT much worse). | Confirmed risk | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv)<br/>[docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_ttft_vs_concurrency.png) |

## Stakeholder Recommendations (Prioritized)
| Priority | Recommendation |
| --- | --- |
| `P0` | Keep this run as canonical networking + single-node inference baseline (`2026-02-09_fresh_full_suite_e2e_fixed`). |
| `P0` | Add node2 fio collection to the canonical suite path (close storage parity gap). |
| `P0` | Add canonical multinode vLLM canary (`>=3` concurrency points) to satisfy Benchmark B multi-node confidence. |
| `P1` | Add canonical nvbandwidth bundle (node1+node2) so NVLink/C2C narrative includes direct bandwidth evidence. |
| `P1` | Fix health-suite GDR path so `--health-gdr` produces effective GPU-backed IB checks (or fail if not effective). |
| `P1` | Keep explicit serving guardrails (`c<=256` low-latency mode vs high-throughput mode at higher tail latency). |
| `P2` | Track MAMF spread trend across repeated runs and flag persistent >10% spread. |

## Repro Steps
Canonical command used for this run:

```bash
cd code/cluster

scripts/run_cluster_eval_suite.sh \
  --run-id 2026-02-09_fresh_full_suite_e2e_fixed \
  --hosts node1,node2 \
  --labels node1,node2 \
  --ssh-key ~/.ssh/ssh_key.pem \
  --oob-if enP22p3s0f3 \
  --socket-ifname enP22p3s0f3 \
  --nccl-ib-hca mlx5_0,mlx5_1,mlx5_4,mlx5_5 \
  --health-suite extended \
  --health-gdr \
  --health-gdr-gpu 0 \
  --health-gdr-mem-types 0,1 \
  --health-gdr-use-dmabuf \
  --fp4-runtime host \
  --run-c2c \
  --run-numa-mem-bw \
  --run-train-step \
  --train-step-single-node \
  --train-step-multi-node \
  --run-checkpoint-io \
  --enable-mamf \
  --mamf-mode quick \
  --mamf-concurrent \
  --enable-allreduce-stability \
  --allreduce-payload-gib 2.0 \
  --allreduce-iters 200 \
  --allreduce-warmup 20 \
  --enable-allreduce-latency-comp \
  --allreduce-latency-payload-gib 4.0 \
  --allreduce-latency-chunks 1000 \
  --allreduce-latency-iters 5 \
  --allreduce-latency-warmup 1 \
  --enable-allgather-control-plane \
  --allgather-control-iters 2000 \
  --allgather-control-warmup 200 \
  --enable-nccl-algo-comparison \
  --nccl-algos Ring,Tree,NVLS,auto
```

## Reproducibility Package
| Bundle | Artifact links |
| --- | --- |
| Canonical manifest + steps | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_suite_steps.json) |
| Discovery + topology | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta_nvlink_topology.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta_nvlink_topology.json) |
| Networking arc | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_nccl_algo_comparison.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_nccl_algo_comparison.json) |
| Inference arc | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.jsonl](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.jsonl) |
| System/compute extras | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_gemm_gpu_sanity.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_gemm_gpu_sanity.csv)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_gemm_gpu_sanity.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_gemm_gpu_sanity.csv)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_fio.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_fio.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_c2c_memcpy.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_c2c_memcpy.json) |
| Runtime/CVE evidence | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1_container_runtime.txt](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1_container_runtime.txt)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node2_container_runtime.txt](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node2_container_runtime.txt) |
| Missing from this canonical package | `node2_fio.json`, multinode vLLM serve artifacts, nvbandwidth bundle artifacts |

## Activity Log
| Date | Update |
| --- | --- |
| 2026-02-09 | Re-ran full end-to-end suite as fresh system flow under `RUN_ID=2026-02-09_fresh_full_suite_e2e_fixed`; suite completed `40/40` steps successfully. |
| 2026-02-09 | Regenerated stakeholder report against canonical fixed artifacts and removed stale references to prior canonical run IDs. |
| 2026-02-09 | Added explicit risk/gap flags for missing `node2_fio.json`, missing multinode vLLM artifacts, missing nvbandwidth bundle, and non-effective GDR path in health suite. |

## Appendix (Coverage vs Case-Study Goals)
| Goal | Status in canonical package | Evidence |
| --- | --- | --- |
| Discovery metadata bundle | Covered | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_meta.json)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node2_meta.json) |
| Benchmark A: NCCL networking story | Covered | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1node2_cluster_health_suite_summary.json)<br/>[docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_bw_vs_msg.png](docs/figures/2026-02-09_fresh_full_suite_e2e_fixed_2nodes_nccl_bw_vs_msg.png) |
| Benchmark B: vLLM online serving knee | Covered (single-node) | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_node1_vllm_serve_sweep.csv) |
| Complete eval suite reuse value | Mostly covered | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_manifest.json) |
| Runtime/CVE evidence defaults | Covered | [results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1_container_runtime.txt](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node1_container_runtime.txt)<br/>[results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node2_container_runtime.txt](results/structured/2026-02-09_fresh_full_suite_e2e_fixed_health_suite_extended_node2_container_runtime.txt) |
| Storage parity (both nodes) | Gap | `node2_fio.json` missing in canonical package |
| Multinode vLLM canary in canonical package | Gap | no canonical `*_vllm_multinode_*` artifact |
| nvbandwidth bundle in canonical package | Gap | no canonical `*_nvbandwidth*` artifact |
