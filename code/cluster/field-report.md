# Cluster Perf Field Report (GB200, 2 Nodes)

Last updated: 2026-02-08.

## Evaluation Scope
- In scope hosts: `node1`, `node2` (2 nodes total).
- GPUs: 4x GB200 per node (8 total).
- Excluded nodes: none.
- Baseline run for stakeholder conclusions: `2026-02-08_ssh_key_full_suite_clean_final6`.
- Historical incident evidence is retained only where it changes recommendations.

## First Contact Experience
- Multi-node launch works reliably once OOB/bootstrap interfaces are explicitly pinned.
- Cluster is HPC-flavored: strong IB/NCCL path, weaker OOB TCP path, and service health can directly gate correctness.
- Biggest usability gotchas were operational, not kernel-level: service readiness (`persistenced`/`imex`/`dcgm`) and accidental background launcher contention.

## TL;DR (Stakeholder)
- Latest clean 2-node run is healthy and reproducible: NCCL all-reduce peak bus bandwidth `839.72 GB/s` (16 GiB), NVLS not degraded.
- vLLM serving shows a clear latency knee: output throughput rises to `27.63k tok/s` at concurrency `512`, but mean TTFT grows to `~3992 ms`.
- OOB TCP is only `~7.73/7.59 Gbps` (fwd/rev), so treat it as control/bootstrap, not data plane.
- One-off `node2_gpu2` GEMM collapse was transient and self-cleared under immediate locked rerun; no reset was required.
- DCGM is now hard-required by preflight and before/after state is recorded per host; latest clean run had DCGM already active on both nodes.
- Historical run evidence is still needed for two reasons: it proves incident causality and quantifies mitigation tradeoffs (especially NVLS fallback).

## Benchmark Arc A: Networking Story
- Clean baseline (`final6`) demonstrates strong multi-node fabric behavior with stable collectives.
- Key metrics:
  - IB write bandwidth: `~387.14 Gbps` per active HCA.
  - NCCL max bus bandwidths: all-reduce `839.72 GB/s`, all-gather `655.20 GB/s`, reduce-scatter `676.08 GB/s`, alltoall `603.45 GB/s`.
  - torch distributed all-reduce sanity max: `714.91 GB/s`.
- Charts:
  - 2-node NCCL bus bandwidth: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_2nodes_nccl_bw_vs_msg.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_2nodes_nccl_bw_vs_msg.png)
  - 2-node NCCL scaling efficiency: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_2nodes_nccl_scaling_efficiency.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_2nodes_nccl_scaling_efficiency.png)

## Benchmark Arc B: Inference Story
- vLLM (`openai/gpt-oss-120b`, TP=4, ISL/OSL=1024/1024) shows throughput scaling with a clear latency knee.
- Key metrics:
  - `c=32`: output `6383.88 tok/s`, mean TTFT `227.97 ms`.
  - `c=256`: output `23843.83 tok/s`, mean TTFT `933.05 ms`.
  - `c=512`: output `27628.65 tok/s`, mean TTFT `3991.83 ms`.
- Charts:
  - tokens/sec vs concurrency: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_total_tok_s_vs_concurrency.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_total_tok_s_vs_concurrency.png)
  - TTFT vs concurrency: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_ttft_vs_concurrency.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_ttft_vs_concurrency.png)
  - TPOT vs concurrency: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_tpot_vs_concurrency.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_tpot_vs_concurrency.png)

## Major Findings (Each Backed by Data + Visualization)

### 1) WEIRD (historical, root-caused): NCCL low-band regime from stuck node1 physical GPU0 SM clock
- What happened: A historical run entered a low-band regime at `~529.64 GB/s` all-reduce peak vs normal `~840.55 GB/s`.
- Why it matters: This was a hardware-state anomaly, not workload variance.
- Data:
  - Low-band historical run: [results/structured/2026-02-07_224500_nccl_16g_baseline_ppr4_bindnone_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-07_224500_nccl_16g_baseline_ppr4_bindnone_node1node2_cluster_health_suite_summary.json)
  - High-band historical run: [results/structured/2026-02-07_140642_cluster_health_suite_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-07_140642_cluster_health_suite_node1node2_cluster_health_suite_summary.json)
- Visualization:
  - Regime overlay: [docs/figures/2026-02-07_nccl_allreduce_bimodal_overlay.png](docs/figures/2026-02-07_nccl_allreduce_bimodal_overlay.png)
- Action: Keep per-GPU clock telemetry + preflight + repeatability checks in standard validation.

### 2) WEIRD (historical incident, mitigated): service-health outage broke NCCL NVLS init and container startup
- What happened: Historical incident run failed NCCL NVLS init (`transport/nvls.cc`) and vLLM container startup (`/run/nvidia-persistenced/socket` missing).
- Why it matters: service state can invalidate both communication and serving.
- Data:
  - NCCL failure excerpt: [results/structured/2026-02-08_025442_cloud_eval_full_health_suite_extended_node1node2_nccl_all_reduce_perf.error_excerpt.txt](results/structured/2026-02-08_025442_cloud_eval_full_health_suite_extended_node1node2_nccl_all_reduce_perf.error_excerpt.txt)
  - vLLM container failure log: [results/structured/2026-02-08_025442_cloud_eval_full_node1_vllm_serve_sweep_sweep_log.txt](results/structured/2026-02-08_025442_cloud_eval_full_node1_vllm_serve_sweep_sweep_log.txt)
- Visualization:
  - NVLS on/off impact: [docs/figures/2026-02-08_nvls_on_off_allreduce_busbw.png](docs/figures/2026-02-08_nvls_on_off_allreduce_busbw.png)
  - Operator state snapshot: [docs/figures/2026-02-08_operator_state_snapshot.png](docs/figures/2026-02-08_operator_state_snapshot.png)
- Action: keep strict preflight mandatory before any benchmark and health-suite run.

### 3) NOTABLE: DCGM is now a hard gate with before/after evidence
- What happened: In historical discovery, DCGM was asymmetric across nodes; preflight now hard-requires DCGM and records before/after/start-by-preflight.
- Why it matters: prevents “silent blind” monitoring runs.
- Data:
  - Historical before/after incident check: [results/structured/2026-02-08_test_preflight_dcgm_before_after_node1node2_preflight_services.json](results/structured/2026-02-08_test_preflight_dcgm_before_after_node1node2_preflight_services.json)
  - Latest clean baseline preflight: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_preflight_services.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_preflight_services.json)
- Visualization:
  - Operator state snapshot: [docs/figures/2026-02-08_operator_state_snapshot.png](docs/figures/2026-02-08_operator_state_snapshot.png)
- Action: keep provider restart policy decision explicit; current unit policy remains `Restart=on-abort`.

### 4) NOTABLE: OOB TCP is much slower than IB and should remain bootstrap-only
- What happened: OOB TCP is `~7.73/7.59 Gbps` in clean baseline, while IB path sustains far higher collective throughput.
- Why it matters: interface/port pinning and control-plane assumptions determine launch reliability.
- Data:
  - OOB throughput: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_iperf3_oob_tcp.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_iperf3_oob_tcp.json)
  - Health summary: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_health_suite_extended_node1node2_cluster_health_suite_summary.json)
- Visualization:
  - OOB TCP chart: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_iperf3_oob_tcp.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_iperf3_oob_tcp.png)
- Action: keep explicit OOB/socket/NCCL HCA pinning in all multi-node recipes.

### 5) NOTABLE: inference latency knee is strong and actionable
- What happened: throughput improves steadily, but TTFT rises sharply at high concurrency.
- Why it matters: user-facing SLOs require explicit concurrency caps, not throughput-only tuning.
- Data:
  - Sweep CSV: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_sweep.csv](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_sweep.csv)
  - Sweep summary: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_concurrency_sweep_summary.txt](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_concurrency_sweep_summary.txt)
- Visualization:
  - TTFT chart: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_ttft_vs_concurrency.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_ttft_vs_concurrency.png)
  - Throughput chart: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_total_tok_s_vs_concurrency.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_vllm_serve_total_tok_s_vs_concurrency.png)
- Action: publish concurrency guardrails for low-latency vs max-throughput modes.

### 6) WEIRD (transient, diagnosed): one-off `node2_gpu2` GEMM collapse did not persist
- What happened: a single run dropped to `~709 TFLOPS` on `node2_gpu2`; immediate isolated rerun recovered (`~1548.7 TFLOPS`), and clean baseline remained in-family (`~1530.66 TFLOPS`).
- Why it matters: reset should be conditional, not default.
- Data:
  - Anomalous run: [results/structured/2026-02-08_ssh_key_full_suite_r2_node2_gemm_gpu_sanity.csv](results/structured/2026-02-08_ssh_key_full_suite_r2_node2_gemm_gpu_sanity.csv)
  - Immediate rerun: [results/structured/2026-02-08_node2_gpu2_diag_pre_reset_node2_gemm_gpu_sanity.csv](results/structured/2026-02-08_node2_gpu2_diag_pre_reset_node2_gemm_gpu_sanity.csv)
  - Clean baseline confirmation: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node2_gemm_gpu_sanity.csv](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node2_gemm_gpu_sanity.csv)
- Visualization:
  - Transient anomaly chart: [docs/figures/2026-02-08_node2_gpu2_transient_gemm_tflops.png](docs/figures/2026-02-08_node2_gpu2_transient_gemm_tflops.png)
- Action: rerun isolated with locked clocks first; reset only if persistent.

### 7) NOTABLE: local scratch capacity exists but is unmounted by default
- What happened: multiple NVMe devices are present, but default benchmark path (`/tmp`) reflects root filesystem behavior.
- Why it matters: storage path decisions can dominate data staging and iteration time.
- Data:
  - Node1 storage: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_storage.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_storage.json)
  - Node2 storage: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node2_storage.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node2_storage.json)
  - fio baseline: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_fio.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_fio.json)
- Visualization:
  - fio chart: [docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_fio.png](docs/figures/2026-02-08_ssh_key_full_suite_clean_final6_node1_fio.png)
  - Operator state snapshot: [docs/figures/2026-02-08_operator_state_snapshot.png](docs/figures/2026-02-08_operator_state_snapshot.png)
- Action: publish and automate a provider-approved `/scratch` policy.

### 8) NOTABLE: SHARP user-space present, but collective integration path is not operational
- What happened: forced NCCL CollNet checks failed before/after `sharp_am` start attempts.
- Why it matters: users cannot assume SHARP acceleration is available just because packages exist.
- Data:
  - SHARP check summary: [results/structured/2026-02-08_082000_ib_sharp_check_v3_ib_sharp_check.json](results/structured/2026-02-08_082000_ib_sharp_check_v3_ib_sharp_check.json)
  - CollNet failure excerpt: [results/structured/2026-02-08_082000_ib_sharp_check_v3_nccl_collnet_all_reduce_after_start_error_excerpt.txt](results/structured/2026-02-08_082000_ib_sharp_check_v3_nccl_collnet_all_reduce_after_start_error_excerpt.txt)
- Visualization:
  - Operator state snapshot: [docs/figures/2026-02-08_operator_state_snapshot.png](docs/figures/2026-02-08_operator_state_snapshot.png)
- Action: provider should document intended SHARP path (MPI HCOLL and/or NCCL net plugin) and health criteria.

### 9) WEIRD (operational reliability): orphan launchers can invalidate benchmark runs
- What happened: `/tmp` launcher scripts repeatedly started non-target runs during clean-run attempts.
- Why it matters: results can become invalid without obvious single-command failures.
- Data:
  - Launcher scripts evidence: [results/structured/2026-02-08_interference_launcher_scripts.txt](results/structured/2026-02-08_interference_launcher_scripts.txt)
  - Runtime/process snapshots: [results/structured/2026-02-08_interference_runtime_excerpts.txt](results/structured/2026-02-08_interference_runtime_excerpts.txt), [results/structured/2026-02-08_interference_process_snapshot.txt](results/structured/2026-02-08_interference_process_snapshot.txt)
- Visualization:
  - Operator state snapshot: [docs/figures/2026-02-08_operator_state_snapshot.png](docs/figures/2026-02-08_operator_state_snapshot.png)
- Action: enforce single queue runner + overlap detection as a hard policy.

## Monitoring Expectations Coverage (Clustermax-Oriented)

| Expectation | Status | Notes / Evidence |
| --- | --- | --- |
| Cluster overview (nodes/workloads/health trends) | PARTIAL | Node-level health is covered by active suite artifacts; no control-plane dashboard in scope. [final6_health] |
| Control-plane health (K8s API/etcd/scheduler) | MISSING | No K8s control plane observed in scope. [final6_node1_meta] [final6_node2_meta] |
| Slurm integration and job stats | MISSING | No Slurm control-plane evidence in scope. [final6_node1_meta] [final6_node2_meta] |
| Kubernetes metrics stack (`kube-prometheus`, `kube-state-metrics`, `node-exporter`, `cAdvisor`) | MISSING | Not observed in scope. [final6_node1_meta] [final6_node2_meta] |
| DCGM exporter/hostengine reliability | PARTIAL | Now hard-required in preflight with before/after auditing; provider restart policy remains a decision point. [preflight_historical_dcgm] [preflight_final6] |
| KV-cache metrics for HPA (`gpu_cache_usage_perc`) | MISSING | No K8s/HPA integration in scope. |
| Alerting/notification integration | UNKNOWN | Provider alerting surface not evaluated in this SSH-only scope. |
| Node power/thermal telemetry | PARTIAL | Node-level GPU telemetry is captured; no fleet dashboard in scope. [final6_node1_meta] [final6_node2_meta] |
| PCIe AER monitoring | MISSING | Not collected as a first-class metric in this runbook. |
| dmesg/log pipeline (promtail or equivalent) | PARTIAL | Incident-focused kernel evidence captured; no continuous log pipeline evaluated. [xid_tail] |
| TFLOPs/SM active/occupancy via DCGM profiling counters | MISSING | Not captured in this evaluation package. |
| Nsight Compute availability for users | UNKNOWN | Not fully validated as a managed user-facing workflow here. |
| NVLink/XGMI throughput visibility | YES | NVLink P2P measurements are included. [nvlink_curve] [nvlink_matrix] |
| PCIe host<->GPU throughput visibility | YES | `nvbandwidth` evidence captured. [nvbandwidth] |
| InfiniBand/RoCE throughput visibility | YES | IB perftest + NCCL multi-node suite evidence captured. [final6_health] |
| User/group quotas and scheduler history | MISSING | No scheduler resource governance surface in scope. |
| Active + passive health-check integration | PARTIAL | Active checks are strong; passive continuous monitoring was not in scope. [final6_health] [preflight_final6] |

## Stakeholder Recommendations (Prioritized)

1. `P0` Keep strict preflight mandatory: `nvidia-persistenced`, `nvidia-imex`, and `nvidia-dcgm` must be healthy before any benchmark/profiling run.
2. `P0` Keep DCGM as a hard requirement with before/after auditing; formalize whether `Restart=on-abort` is intentional and document expected behavior.
3. `P0` Publish a single multi-node launcher golden path (OOB/socket interface, HCA allowlist, port policy).
4. `P1` Publish serving guardrails: default concurrency envelopes for low-latency and max-throughput modes.
5. `P1` Publish provider storage policy for local NVMe scratch (`/scratch` design, durability expectations, lifecycle).
6. `P1` Clarify SHARP support stance and required software path (MPI HCOLL and/or NCCL plugin) with validation criteria.
7. `P1` Enforce single queue runner and overlap detection to prevent hidden benchmark contention.
8. `P2` Add continuous passive observability (log pipeline + alerting) to complement active suites.

## Reproducibility Package
- Clean baseline manifest: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_manifest.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_manifest.json)
- Clean preflight (DCGM before/after): [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_preflight_services.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_preflight_services.json)
- Clean health summary: [results/structured/2026-02-08_ssh_key_full_suite_clean_final6_health_suite_extended_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-08_ssh_key_full_suite_clean_final6_health_suite_extended_node1node2_cluster_health_suite_summary.json)
- Historical incident bundle (only what changed decisions):
  - Historical run (`2026-02-08_032814_cloud_eval_full_fixed`) service/context snapshot: [results/structured/2026-02-08_032814_cloud_eval_full_fixed_preflight_services.json](results/structured/2026-02-08_032814_cloud_eval_full_fixed_preflight_services.json)
  - NVLS failure excerpt: [results/structured/2026-02-08_025442_cloud_eval_full_health_suite_extended_node1node2_nccl_all_reduce_perf.error_excerpt.txt](results/structured/2026-02-08_025442_cloud_eval_full_health_suite_extended_node1node2_nccl_all_reduce_perf.error_excerpt.txt)
  - NVLS-off tradeoff run: [results/structured/2026-02-08_031531_health_suite_extended_nvls0_node1node2_cluster_health_suite_summary.json](results/structured/2026-02-08_031531_health_suite_extended_nvls0_node1node2_cluster_health_suite_summary.json)

One-command baseline repro:
```bash
cd code/cluster

scripts/run_cluster_eval_suite.sh \
  --run-id 2026-02-08_ssh_key_full_suite_clean_final6 \
  --hosts node1,node2 \
  --labels node1,node2 \
  --ssh-key ~/.ssh/ssh_key.pem \
  --oob-if enP22p3s0f3 \
  --socket-ifname enP22p3s0f3 \
  --nccl-ib-hca mlx5_0,mlx5_1,mlx5_4,mlx5_5 \
  --health-suite extended \
  --disable-fp4
```

## What Historical Runs Changed (Why They Are Kept)
- They proved causal links for operational failures that the clean run no longer shows.
- They quantified the real mitigation cost (`NVLS off` reduced all-reduce peak from `~839.39` to `~699.63 GB/s`).
- They justified hard preflight gating and explicit fallback reporting in the harness.
- They prevented over-claiming from a single “all good” run.

## Open Questions for Provider
- Is `nvidia-dcgm` `Restart=on-abort` an intentional SRE policy?
- What is the expected SHARP enablement path for user collectives on this image?
- What is the intended lifecycle and performance policy for local NVMe scratch?
- Which control-plane/scheduler observability surface should users rely on (if any) in this environment?

---

[final6_health]: results/structured/2026-02-08_ssh_key_full_suite_clean_final6_health_suite_extended_node1node2_cluster_health_suite_summary.json
[final6_node1_meta]: results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node1_meta.json
[final6_node2_meta]: results/structured/2026-02-08_ssh_key_full_suite_clean_final6_node2_meta.json
[preflight_final6]: results/structured/2026-02-08_ssh_key_full_suite_clean_final6_preflight_services.json
[preflight_historical_dcgm]: results/structured/2026-02-08_test_preflight_dcgm_before_after_node1node2_preflight_services.json
[xid_tail]: results/structured/2026-02-07_232000_node1_dmesg_nvrm_xid_tail.log
[nvlink_curve]: docs/figures/2026-02-06_node1_nvlink_p2p_bw_curve.png
[nvlink_matrix]: docs/figures/2026-02-06_node1_nvlink_p2p_bandwidth_matrix.png
[nvbandwidth]: results/structured/2026-02-08_011938_cluster_perf_node1_nvbandwidth.txt
