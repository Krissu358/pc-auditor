import time
import math
import multiprocessing


def _single_core_work(seconds: float) -> float:
    start_time = time.time()
    ops = 0
    i = 0
    while (time.time() - start_time) < seconds:
        math.sqrt(i)
        ops += 1
        i += 1
    return ops / seconds


def _stress_worker(seconds: float):
    start_time = time.time()
    i = 0
    while (time.time() - start_time) < seconds:
        math.sqrt(i)
        i += 1


def run_thermal_stress_test(progress_callback=None) -> dict:
    # Performance measurement
    if progress_callback:
        progress_callback(0.15, "Measuring cold performance...")
    sample_start = _single_core_work(2.0)

    if progress_callback:
        progress_callback(0.35, "Stressing all CPU cores (8s)...")

    cores = multiprocessing.cpu_count()
    processes = []
    for _ in range(cores):
        p = multiprocessing.Process(target=_stress_worker, args=(8.0,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    if progress_callback:
        progress_callback(0.85, "Measuring post-load performance...")
    sample_end = _single_core_work(2.0)

    drop = ((sample_start - sample_end) / sample_start) * 100
    if progress_callback:
        progress_callback(1.0, "Stress test finished.")

    return {
        "cold_mops": round(sample_start / 1_000_000, 2),
        "hot_mops": round(sample_end / 1_000_000, 2),
        "drop_percent": round(drop, 1),
        "cores_tested": cores,
    }