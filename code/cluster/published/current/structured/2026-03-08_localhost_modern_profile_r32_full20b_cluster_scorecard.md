# Cluster Scorecard: `2026-03-08_localhost_modern_profile_r32_full20b`

Generated: `2026-03-08T08:40:18.285280+00:00`
Workload KPI label: `localhost`

## Canonical Completeness

| Field | Value |
|---|---|
| Overall score | `0.0` |
| Pass/fail | `fail` |
| Coverage score | `n/a%` |
| Advanced coverage score | `n/a%` |
| Coverage maturity | `n/a` |
| MLPerf overall status | `n/a` |
| MLPerf inference track ready | `False` |
| MLPerf training track ready | `False` |
| Gate: coverage >= min | `False` |
| Gate: advanced >= min | `False` |
| Gate: MLPerf alignment minimum | `False` |
| Gate: canonical complete | `False` |

## Unified KPIs

| Domain | KPI | Value |
|---|---|---:|
| Compute | GEMM max TFLOPS | `1274.1` |
| Memory | nvbandwidth HBM GB/s | `0.0` |
| Memory | STREAM-like triad GB/s | `6189.1` |
| Communication | NCCL single-node peak busbw GB/s | `0.0` |
| Communication | NCCL multi-node peak busbw GB/s | `0.0` |
| Communication | Multi/single busbw ratio | `0.00` |
| Communication | NCCL all-to-all single-node peak busbw GB/s | `0.0` |
| Communication | NCCL all-to-all multi-node peak busbw GB/s | `0.0` |
| Communication | NCCL all-to-all multi/single busbw ratio | `0.00` |
| Communication | NCCL algo winner | `n/a (single-rank)` |
| Communication | NCCL algo spread % | `n/a` |
| Communication | NCCL auto gap % | `n/a` |
| Communication | Allreduce stability CV % | `n/a` |
| Communication | Allreduce stability p99/p50 | `n/a` |
| Communication | Allreduce jitter assessment | `n/a (world_size<=1)` |
| Communication | Allreduce latency comp (small/large duration ratio) | `363.18` |
| Communication | Allreduce latency comp one-large duration ms | `0.0292` |
| Communication | Allreduce latency comp many-small duration ms | `10.6048` |
| Communication | all_gather_object vs tensor speedup | `5.41x` |
| Communication | all_gather_object vs all_reduce speedup | `9.75x` |
| Communication | Control-plane fastest method | `all_reduce_tensor` |
| Communication | Control-plane fastest latency ms | `0.0278` |
| Host transfer | nvbandwidth H2D GB/s | `55.6` |
| Workload | vLLM throughput gain ratio | `13.37` |
| Workload | vLLM p99 TTFT ratio | `10.67` |
| Workload | vLLM max SLO goodput tok/s | `3997.25` |
| Workload | vLLM goodput efficiency ratio | `0.29` |
| Workload | vLLM knee concurrency | `256` |
| Workload | vLLM request-rate max tok/s | `4611.02` |
| Workload | vLLM request-rate at max tok/s | `16.00` |
| Efficiency | vLLM tok/J @ max tok/s | `35.240` |
| Efficiency | vLLM request-rate tok/J @ max tok/s | `17.438` |
| Efficiency | Cost USD / 1M tok (concurrency) | `n/a` |
| Efficiency | Cost USD / 1M tok (request-rate) | `n/a` |
| Workload Stability | vLLM conc tok/s CV p95 % | `2.02` |
| Workload Stability | vLLM conc p99 TTFT CV p95 % | `14.87` |
| Workload Stability | vLLM rate tok/s CV p95 % | `2.60` |
| Storage Stability | fio seq-read BW CV % | `1.35` |
| Storage Stability | fio seq-write BW CV % | `0.52` |

## Bottleneck Classification

| Classifier | Value |
|---|---|
| Dominant bottleneck | `host-bound` |
| Confidence | `high` |

| Evidence |
|---|
| vLLM sweep repeat variance is elevated (conc tok/s CV p95=2.0180104196098956%, conc p99 TTFT CV p95=14.868322307810066%, rate tok/s CV p95=2.5987480227545223%). |

| Recommended next actions |
|---|
| Stabilize host scheduling path (CPU pinning, background load isolation, queue controls). |
| Re-run workload sweeps with the same repeat count and verify CV is below 10% before promoting conclusions. |

## Per-Node Metrics

| Label | GEMM max TFLOPS | nvbandwidth HBM GB/s | STREAM triad GB/s | vLLM tok/s gain | vLLM p99 TTFT ratio | vLLM max SLO goodput tok/s | vLLM knee concurrency | vLLM conc tok/s CV p95 % | fio seq read MB/s | fio seq read CV % | fio seq write MB/s | fio seq write CV % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `localhost` | `1274.1` | `0.0` | `6189.1` | `13.37` | `10.67` | `3997.25` | `256` | `2.02` | `1560.9` | `1.35` | `686.8` | `0.52` |
