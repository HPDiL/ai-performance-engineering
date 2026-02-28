#!/usr/bin/env python3
import argparse
import copy
import datetime as dt
import json
import os
import re
import select
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

NUM_RE = re.compile(r"([-+]?\d*\.?\d+)")
OOM_LINE_RE = re.compile(
    r"Tried to allocate (?P<tried_val>[\d.]+)\s*(?P<tried_unit>[KMG]iB).*?"
    r"total capacity of (?P<total_val>[\d.]+)\s*(?P<total_unit>[KMG]iB).*?"
    r"of which (?P<free_val>[\d.]+)\s*(?P<free_unit>[KMG]iB) is free.*?"
    r"process has (?P<proc_val>[\d.]+)\s*(?P<proc_unit>[KMG]iB) memory in use.*?"
    r"allocated memory (?P<alloc_val>[\d.]+)\s*(?P<alloc_unit>[KMG]iB).*?"
    r"and (?P<reserved_val>[\d.]+)\s*(?P<reserved_unit>[KMG]iB) is reserved",
    re.IGNORECASE,
)
UNIT_TO_MIB = {"kib": 1.0 / 1024.0, "mib": 1.0, "gib": 1024.0}


def _ts() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _wait_for_server(base_url: str, timeout_sec: int, poll_interval_sec: int, proc: Optional[subprocess.Popen] = None) -> None:
    import urllib.request

    deadline = time.time() + timeout_sec
    health = f"{base_url}/health"
    while time.time() < deadline:
        if proc and proc.poll() is not None:
            raise RuntimeError(f"Server process exited before becoming healthy (returncode={proc.returncode})")
        try:
            with urllib.request.urlopen(health, timeout=2) as r:  # nosec B310
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(poll_interval_sec)
    raise TimeoutError(f"Timed out waiting for {health}")


def _to_mib(value: str, unit: str) -> Optional[float]:
    mult = UNIT_TO_MIB.get(unit.lower())
    if mult is None:
        return None
    try:
        return float(value) * mult
    except Exception:
        return None


def _resolve_path(value: str, base_dir: Path, force: bool = False) -> str:
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    path = Path(expanded)
    if path.is_absolute():
        return str(path)

    candidate = (base_dir / path).resolve()
    if force or expanded.startswith("./") or expanded.startswith("../") or candidate.exists():
        return str(candidate)

    # Keep non-path identifiers (for example, HF IDs) unchanged.
    return expanded


def _load_vllm_cmd(global_cfg: dict, override: str, base_dir: Path):
    raw = override or global_cfg.get("vllm_cmd", "vllm")
    if isinstance(raw, str):
        cmd = shlex.split(raw)
    else:
        cmd = [str(x) for x in raw]

    if not cmd:
        raise ValueError("vllm_cmd resolved to an empty command")
    cmd = [os.path.expandvars(x) for x in cmd]
    if "/" in cmd[0] or cmd[0].startswith(".") or cmd[0].startswith("~"):
        expanded = Path(os.path.expanduser(cmd[0]))
        if expanded.is_absolute():
            cmd[0] = str(expanded)
        elif expanded.exists():
            cmd[0] = str(expanded.resolve())
        else:
            cmd[0] = _resolve_path(cmd[0], base_dir, force=True)
    return cmd


def _start_server(run_cfg: dict, tokenizer: str, vllm_cmd: list[str]):
    serve = run_cfg.get("serve", {})
    cmd = list(vllm_cmd) + ["serve", run_cfg["model"]]

    if serve.get("tp"):
        cmd += ["-tp", str(serve["tp"])]
    if serve.get("dp"):
        cmd += ["-dp", str(serve["dp"])]
    if serve.get("enable_expert_parallel"):
        cmd += ["--enable-expert-parallel"]

    spec = serve.get("speculative", {})
    if spec:
        if spec.get("method"):
            cmd += ["--speculative-config.method", str(spec["method"])]
        if spec.get("num_speculative_tokens") is not None:
            cmd += ["--speculative-config.num_speculative_tokens", str(spec["num_speculative_tokens"])]

    cmd += ["--tokenizer", tokenizer]
    cmd += [str(x) for x in serve.get("extra_args", [])]

    env = os.environ.copy()
    env.update({k: str(v) for k, v in run_cfg.get("env", {}).items()})

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    return proc, cmd


def _run_bench(
    base_url: str,
    tokenizer: str,
    run_cfg: dict,
    scenario: dict,
    concurrency: int,
    global_cfg: dict,
    vllm_cmd: list[str],
):
    cmd = list(vllm_cmd) + [
        "bench",
        "serve",
        "--model",
        run_cfg["model"],
        "--seed",
        str(global_cfg.get("seed", 42)),
        "--dataset-name",
        "random",
        "--base-url",
        base_url,
        "--tokenizer",
        tokenizer,
        "--num-prompts",
        str(global_cfg.get("num_prompts", 1000)),
        "--max-concurrency",
        str(concurrency),
        "--random-input-len",
        str(scenario["isl"]),
        "--random-output-len",
        str(scenario["osl"]),
    ]
    if global_cfg.get("ignore_eos", True):
        cmd.append("--ignore-eos")

    timeout_sec = int(global_cfg.get("bench_timeout_sec", 3600))
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    return cmd, out.returncode, (out.stdout or "") + "\n" + (out.stderr or "")


def _num_from_line(line: str) -> Optional[float]:
    nums = NUM_RE.findall(line)
    if not nums:
        return None
    try:
        return float(nums[-1])
    except Exception:
        return None


def _extract_metrics(raw: str) -> dict:
    metrics = {
        "prefill_lines": [],
        "decode_lines": [],
        "ttft_lines": [],
        "tpot_lines": [],
    }
    for line in raw.splitlines():
        lower = line.lower()
        if "throughput" in lower and "tok" in lower:
            if "output" in lower or "decode" in lower:
                metrics["decode_lines"].append(line.strip())
            else:
                metrics["prefill_lines"].append(line.strip())
        if "ttft" in lower:
            metrics["ttft_lines"].append(line.strip())
        if "tpot" in lower:
            metrics["tpot_lines"].append(line.strip())

    metrics["prefill_toks_per_s"] = _num_from_line(metrics["prefill_lines"][-1]) if metrics["prefill_lines"] else None
    metrics["decode_toks_per_s"] = _num_from_line(metrics["decode_lines"][-1]) if metrics["decode_lines"] else None
    return metrics


def _terminate(proc: subprocess.Popen):
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def _load_concurrency(global_cfg: dict, profile: str):
    profiles = global_cfg.get("concurrency_profiles", {})
    if profile and profile in profiles:
        return profiles[profile]
    return global_cfg.get("max_concurrency_values", [8, 16, 32, 64, 128, 256])


def _capture_server_log_head(proc: subprocess.Popen, max_lines: int = 100, max_wait_sec: float = 3.0):
    if not proc.stdout:
        return []

    lines = []
    deadline = time.time() + max_wait_sec
    while len(lines) < max_lines and time.time() < deadline:
        if proc.poll() is not None:
            remaining = proc.stdout.read() or ""
            lines.extend([ln.rstrip() for ln in remaining.splitlines()])
            break
        try:
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
        except Exception:
            break
        if not ready:
            continue
        line = proc.stdout.readline()
        if not line:
            break
        lines.append(line.rstrip())

    return lines[:max_lines]


def _detect_local_gpu_count() -> Optional[int]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    lines = [ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip()]
    return len(lines)


def _required_world_size(run_cfg: dict) -> int:
    serve = run_cfg.get("serve", {})
    tp = int(serve.get("tp", 1) or 1)
    dp = int(serve.get("dp", 1) or 1)
    return tp * dp


def _parallel_tuple(run_cfg: dict):
    serve = run_cfg.get("serve", {})
    tp = int(serve.get("tp", 1) or 1)
    dp = int(serve.get("dp", 1) or 1)
    return tp, dp, tp * dp


def _adapt_run_to_gpus(run_cfg: dict, gpu_count: int):
    tp, dp, world = _parallel_tuple(run_cfg)
    if world <= gpu_count:
        return run_cfg, None

    adapted = copy.deepcopy(run_cfg)
    serve = adapted.setdefault("serve", {})
    new_tp = min(tp, gpu_count)
    new_dp = max(1, min(dp, gpu_count // max(1, new_tp)))
    if new_tp * new_dp == 0:
        new_tp, new_dp = 1, 1
    while new_tp * new_dp > gpu_count and new_tp > 1:
        new_tp -= 1
    while new_tp * new_dp > gpu_count and new_dp > 1:
        new_dp -= 1
    if new_tp * new_dp > gpu_count:
        new_tp, new_dp = 1, 1

    serve["tp"] = int(new_tp)
    if int(new_dp) > 1:
        serve["dp"] = int(new_dp)
    else:
        serve.pop("dp", None)
    if serve.get("enable_expert_parallel") and int(new_dp) < 2:
        serve["enable_expert_parallel"] = False

    old_name = run_cfg["name"]
    new_name = f"{old_name}_auto_tp{new_tp}_dp{new_dp}"
    adapted["name"] = new_name
    adapted["_parallel_adjustment"] = {
        "original_name": old_name,
        "original_tp": tp,
        "original_dp": dp,
        "original_world_size": world,
        "adjusted_tp": int(new_tp),
        "adjusted_dp": int(new_dp),
        "adjusted_world_size": int(new_tp) * int(new_dp),
        "available_gpus": gpu_count,
    }
    return adapted, adapted["_parallel_adjustment"]


def _append_extra_arg(extra_args: list[str], flag: str, value: str):
    if flag in extra_args:
        return
    extra_args.extend([flag, value])


def _build_oom_retry_run(run_cfg: dict):
    retried = copy.deepcopy(run_cfg)
    serve = retried.setdefault("serve", {})
    extra_args = [str(x) for x in serve.get("extra_args", [])]
    # Conservative single-node fallback to make oversized models launch more reliably.
    _append_extra_arg(extra_args, "--cpu-offload-gb", "12")
    _append_extra_arg(extra_args, "--gpu-memory-utilization", "0.90")
    _append_extra_arg(extra_args, "--max-model-len", "4096")
    serve["extra_args"] = extra_args
    retried["_oom_retry_applied"] = True
    retried["name"] = f"{run_cfg['name']}_oomretry"
    return retried


def _is_cuda_oom(server_log: list[str]) -> bool:
    for ln in server_log:
        lower = ln.lower()
        if "cuda out of memory" in lower or "outofmemoryerror" in lower:
            return True
    return False


def _extract_oom_diagnostics(server_log: list[str]) -> Optional[dict]:
    for ln in server_log:
        m = OOM_LINE_RE.search(ln)
        if not m:
            continue
        tried_mib = _to_mib(m.group("tried_val"), m.group("tried_unit"))
        total_mib = _to_mib(m.group("total_val"), m.group("total_unit"))
        free_mib = _to_mib(m.group("free_val"), m.group("free_unit"))
        proc_mib = _to_mib(m.group("proc_val"), m.group("proc_unit"))
        alloc_mib = _to_mib(m.group("alloc_val"), m.group("alloc_unit"))
        reserved_mib = _to_mib(m.group("reserved_val"), m.group("reserved_unit"))
        return {
            "tried_alloc_mib": tried_mib,
            "total_capacity_mib": total_mib,
            "free_mib": free_mib,
            "process_in_use_mib": proc_mib,
            "pytorch_allocated_mib": alloc_mib,
            "pytorch_reserved_unallocated_mib": reserved_mib,
            "raw_line": ln,
        }
    return None


def _gpu_mem_snapshot() -> Optional[list[dict]]:
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    rows = []
    for ln in (out.stdout or "").splitlines():
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) != 6:
            continue
        try:
            rows.append(
                {
                    "gpu_index": int(parts[0]),
                    "gpu_name": parts[1],
                    "total_mib": float(parts[2]),
                    "used_mib": float(parts[3]),
                    "free_mib": float(parts[4]),
                    "util_percent": float(parts[5]),
                }
            )
        except Exception:
            continue
    return rows or None


def _emit_loud_oom_warning(run_cfg: dict, oom_diag: Optional[dict], gpu_snapshot: Optional[list[dict]]):
    print("\n!!! CUDA OOM STARTUP FAILURE !!!", file=sys.stderr)
    print(f"run={run_cfg.get('name')} model={run_cfg.get('model')}", file=sys.stderr)
    tp, dp, world = _parallel_tuple(run_cfg)
    print(f"parallelism: tp={tp} dp={dp} world_size={world}", file=sys.stderr)
    if run_cfg.get("_parallel_adjustment"):
        print(f"parallel_adjustment={run_cfg['_parallel_adjustment']}", file=sys.stderr)
    if oom_diag:
        tried = oom_diag.get("tried_alloc_mib")
        free = oom_diag.get("free_mib")
        total = oom_diag.get("total_capacity_mib")
        used = oom_diag.get("process_in_use_mib")
        tried_s = f"{tried:.2f}" if tried is not None else "n/a"
        free_s = f"{free:.2f}" if free is not None else "n/a"
        total_s = f"{total:.2f}" if total is not None else "n/a"
        used_s = f"{used:.2f}" if used is not None else "n/a"
        print(
            "parsed_oom: "
            f"tried_alloc_mib={tried_s} free_mib={free_s} total_mib={total_s} process_in_use_mib={used_s}",
            file=sys.stderr,
        )
        reason = []
        if free is not None and tried is not None and tried > free:
            reason.append("requested allocation exceeded currently free GPU memory")
        if used is not None and total is not None and used / total > 0.95:
            reason.append("model/runtime consumed >95% of total GPU memory before startup completed")
        if reason:
            print("likely_reason: " + "; ".join(reason), file=sys.stderr)
    if gpu_snapshot:
        for row in gpu_snapshot:
            print(
                "gpu_snapshot: "
                f"idx={row['gpu_index']} name={row['gpu_name']} total_mib={row['total_mib']} "
                f"used_mib={row['used_mib']} free_mib={row['free_mib']} util={row['util_percent']}%",
                file=sys.stderr,
            )
    print("!!! END CUDA OOM !!!\n", file=sys.stderr)


def _should_fail_fast(mode: str, is_startup: bool, is_oom: bool) -> bool:
    if mode == "none":
        return False
    if mode == "any":
        return is_startup
    if mode == "startup":
        return is_startup
    if mode == "oom":
        return is_startup and is_oom
    return False


def _write_startup_failure_artifact(
    results_dir: Path,
    run_cfg: dict,
    base_url: str,
    serve_cmd: list[str],
    error: str,
    server_log: list[str],
    oom_diagnostics: Optional[dict] = None,
    gpu_snapshot: Optional[list[dict]] = None,
):
    tp, dp, world = _parallel_tuple(run_cfg)
    stamp = _ts()
    stem = f"{stamp}_{run_cfg['name']}_startup_failure"
    raw_path = results_dir / f"{stem}.raw.txt"
    json_path = results_dir / f"{stem}.json"
    raw_path.write_text("\n".join(server_log) + ("\n" if server_log else ""))
    payload = {
        "timestamp": stamp,
        "run_name": run_cfg["name"],
        "model": run_cfg["model"],
        "scenario": "__startup__",
        "isl": None,
        "osl": None,
        "max_concurrency": None,
        "base_url": base_url,
        "vllm_cmd": serve_cmd[:1],
        "tp": tp,
        "dp": dp,
        "world_size": world,
        "returncode": 1,
        "serve_cmd": serve_cmd,
        "bench_cmd": None,
        "startup_error": error,
        "startup_error_kind": "cuda_oom" if oom_diagnostics else "server_startup_failure",
        "parallel_adjustment": run_cfg.get("_parallel_adjustment"),
        "oom_retry_applied": bool(run_cfg.get("_oom_retry_applied")),
        "oom_diagnostics": oom_diagnostics,
        "gpu_snapshot": gpu_snapshot,
        "server_log_head": server_log,
        "metrics": _extract_metrics("\n".join(server_log)),
        "raw_file": str(raw_path),
    }
    json_path.write_text(json.dumps(payload, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--profile", default="")
    parser.add_argument("--run-filter", default="", help="Substring filter for run names")
    parser.add_argument("--scenario-filter", default="", help="Substring filter for scenario names")
    parser.add_argument("--results-dir", default="", help="Override results directory")
    parser.add_argument("--tokenizer", default="", help="Override tokenizer path/id")
    parser.add_argument("--base-url", default="", help="Override vLLM serve base URL")
    parser.add_argument("--vllm-cmd", default="", help="Override vLLM command prefix")
    parser.add_argument(
        "--parallel-policy",
        default="auto",
        choices=["auto", "strict"],
        help="auto: adapt TP/DP to available GPUs; strict: skip infeasible runs",
    )
    parser.add_argument(
        "--fail-fast",
        default="oom",
        choices=["none", "startup", "oom", "any"],
        help="none: continue; startup: stop on first startup failure; oom: stop on unrecoverable CUDA OOM; any: stop on any startup failure",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    cfg = yaml.safe_load(config_path.read_text())
    global_cfg = cfg["global"]
    tokenizer = args.tokenizer or cfg["paths"]["tokenizer"]
    tokenizer = _resolve_path(tokenizer, config_path.parent)
    base_url = args.base_url or global_cfg.get("base_url", "http://127.0.0.1:8000")
    vllm_cmd = _load_vllm_cmd(global_cfg, args.vllm_cmd, config_path.parent)
    scenarios = cfg["scenarios"]
    conc_vals = [int(x) for x in _load_concurrency(global_cfg, args.profile)]
    gpu_count = _detect_local_gpu_count()
    if gpu_count is None:
        print("GPU preflight: nvidia-smi unavailable; skipping world-size pre-check.")
    else:
        print(f"GPU preflight: detected {gpu_count} local GPU(s).")

    results_dir_value = args.results_dir or global_cfg.get("results_dir", "results")
    results_dir = Path(_resolve_path(results_dir_value, config_path.parent, force=True))
    results_dir.mkdir(parents=True, exist_ok=True)
    started_runs = 0
    skipped_runs = 0
    adapted_runs = 0
    startup_failures = 0
    oom_startup_failures = 0
    bench_total = 0
    bench_success = 0
    bench_failed = 0

    for run_cfg in cfg["runs"]:
        if args.run_filter and args.run_filter not in run_cfg["name"]:
            continue
        effective_run = run_cfg
        required_world = _required_world_size(run_cfg)
        if gpu_count is not None and required_world > gpu_count:
            if args.parallel_policy == "strict":
                print(
                    f"Skipping run '{run_cfg['name']}' preflight: world_size={required_world} > available_gpus={gpu_count}.",
                    file=sys.stderr,
                )
                skipped_runs += 1
                continue
            effective_run, adj = _adapt_run_to_gpus(run_cfg, gpu_count)
            if adj:
                adapted_runs += 1
                print(
                    f"Adapting run '{run_cfg['name']}' -> '{effective_run['name']}' "
                    f"(tp {adj['original_tp']}->{adj['adjusted_tp']}, dp {adj['original_dp']}->{adj['adjusted_dp']})"
                )

        candidate_run = effective_run
        run_completed = False
        while not run_completed:
            print(f"\n=== Starting run: {candidate_run['name']} ({candidate_run['model']}) ===")
            started_runs += 1
            proc, serve_cmd = _start_server(candidate_run, tokenizer, vllm_cmd=vllm_cmd)
            server_log = []
            retry_with_oom = False
            startup_ok = False
            try:
                try:
                    _wait_for_server(
                        base_url,
                        timeout_sec=int(global_cfg.get("startup_timeout_sec", 900)),
                        poll_interval_sec=int(global_cfg.get("poll_interval_sec", 2)),
                        proc=proc,
                    )
                except Exception as e:
                    server_log = _capture_server_log_head(proc, max_lines=200, max_wait_sec=2.0)
                    print(f"ERROR: server failed to become healthy for run '{candidate_run['name']}': {e}", file=sys.stderr)
                    for ln in server_log[:20]:
                        print(f"[server] {ln}", file=sys.stderr)
                    oom_diag = _extract_oom_diagnostics(server_log) if _is_cuda_oom(server_log) else None
                    if oom_diag:
                        _emit_loud_oom_warning(candidate_run, oom_diag, _gpu_mem_snapshot())

                    if (
                        args.parallel_policy == "auto"
                        and not candidate_run.get("_oom_retry_applied")
                        and oom_diag
                    ):
                        retry_with_oom = True
                    else:
                        gpu_snapshot = _gpu_mem_snapshot()
                        _write_startup_failure_artifact(
                            results_dir=results_dir,
                            run_cfg=candidate_run,
                            base_url=base_url,
                            serve_cmd=serve_cmd,
                            error=str(e),
                            server_log=server_log,
                            oom_diagnostics=oom_diag,
                            gpu_snapshot=gpu_snapshot,
                        )
                        startup_failures += 1
                        if oom_diag:
                            oom_startup_failures += 1
                        if _should_fail_fast(args.fail_fast, is_startup=True, is_oom=bool(oom_diag)):
                            raise RuntimeError(
                                f"Fail-fast ({args.fail_fast}) triggered by startup failure in run '{candidate_run['name']}'."
                            )
                else:
                    startup_ok = True
                    print("Server healthy.")
                    server_log = _capture_server_log_head(proc)

                if startup_ok:
                    for scenario_name in candidate_run.get("scenarios", []):
                        if args.scenario_filter and args.scenario_filter not in scenario_name:
                            continue
                        if scenario_name not in scenarios:
                            print(f"WARNING: scenario '{scenario_name}' not found in config; skipping.", file=sys.stderr)
                            continue
                        sc = scenarios[scenario_name]
                        for c in conc_vals:
                            bench_total += 1
                            print(f"Running {candidate_run['name']} | {scenario_name} | concurrency={c}")
                            try:
                                bench_cmd, rc, raw = _run_bench(
                                    base_url=base_url,
                                    tokenizer=tokenizer,
                                    run_cfg=candidate_run,
                                    scenario=sc,
                                    concurrency=c,
                                    global_cfg=global_cfg,
                                    vllm_cmd=vllm_cmd,
                                )
                            except subprocess.TimeoutExpired as e:
                                bench_cmd = e.cmd
                                rc = 124
                                raw = f"TIMEOUT after {e.timeout}s\n" + ((e.stdout or "") + "\n" + (e.stderr or ""))
                            if rc == 0:
                                bench_success += 1
                            else:
                                bench_failed += 1

                            stamp = _ts()
                            stem = f"{stamp}_{candidate_run['name']}_{scenario_name}_c{c}"
                            raw_path = results_dir / f"{stem}.raw.txt"
                            json_path = results_dir / f"{stem}.json"
                            raw_path.write_text(raw)
                            tp, dp, world = _parallel_tuple(candidate_run)

                            payload = {
                                "timestamp": stamp,
                                "run_name": candidate_run["name"],
                                "model": candidate_run["model"],
                                "original_run_name": run_cfg["name"],
                                "scenario": scenario_name,
                                "isl": sc["isl"],
                                "osl": sc["osl"],
                                "max_concurrency": c,
                                "base_url": base_url,
                                "vllm_cmd": vllm_cmd,
                                "tp": tp,
                                "dp": dp,
                                "world_size": world,
                                "returncode": rc,
                                "serve_cmd": serve_cmd,
                                "bench_cmd": bench_cmd,
                                "parallel_adjustment": candidate_run.get("_parallel_adjustment"),
                                "oom_retry_applied": bool(candidate_run.get("_oom_retry_applied")),
                                "server_log_head": server_log,
                                "metrics": _extract_metrics(raw),
                                "raw_file": str(raw_path),
                            }
                            json_path.write_text(json.dumps(payload, indent=2))
                    run_completed = True

            finally:
                _terminate(proc)
                print(f"Stopped run: {candidate_run['name']}")

            if retry_with_oom:
                next_run = _build_oom_retry_run(candidate_run)
                print(
                    f"Retrying '{candidate_run['name']}' as '{next_run['name']}' with OOM fallback "
                    f"(cpu_offload/max_model_len/gpu_memory_utilization)."
                )
                candidate_run = next_run
                continue
            break

    print("\nDone. Results saved under", results_dir)
    print(
        "Summary: "
        f"started_runs={started_runs}, adapted_runs={adapted_runs}, skipped_runs={skipped_runs}, "
        f"startup_failures={startup_failures}, startup_oom_failures={oom_startup_failures}, "
        f"bench_total={bench_total}, bench_success={bench_success}, bench_failed={bench_failed}"
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("Interrupted.")
        sys.exit(130)
