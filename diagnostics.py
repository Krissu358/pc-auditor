import subprocess
import psutil
import wmi
import win32api
import pythoncom
import time


def _get_power_plan() -> str:
    try:
        output = subprocess.check_output(
            ["powercfg", "/getactivescheme"], text=True, stderr=subprocess.DEVNULL
        )
        if "(" in output and ")" in output:
            return output.split("(")[1].split(")")[0].strip()
    except Exception:
        pass
    return "Unknown"


def get_system_diagnostics(benchmark_result: dict = None) -> dict:
    pythoncom.CoInitialize()

    w = wmi.WMI()
    score = 100
    warnings = []

    # 1. Monitor
    device = win32api.EnumDisplayDevices(None, 0)
    settings = win32api.EnumDisplaySettings(device.DeviceName, -1)
    refresh_rate = settings.DisplayFrequency

    if refresh_rate <= 60:
        score -= 10
        warnings.append(
            f"Screen refresh rate is {refresh_rate} Hz. If you have a >60Hz monitor, change your display settings."
        )

    # 2. RAM
    memory_modules = w.Win32_PhysicalMemory()
    ram_speed = memory_modules[0].ConfiguredClockSpeed if memory_modules else 0
    ram = psutil.virtual_memory()
    total_gb = round(ram.total / (1024**3), 2)

    if 0 < ram_speed <= 2400:
        score -= 15
        warnings.append(
            f"RAM speed is {ram_speed} MHz. XMP / EXPO profile is likely disabled in BIOS."
        )

    # 3. CPU, GPU & Power Plan
    cpu_usage = psutil.cpu_percent(interval=0.3)
    cpu_name = w.Win32_Processor()[0].Name.strip()
    gpu_name = w.Win32_VideoController()[0].Name.strip()
    power_plan = _get_power_plan()

    if "oszczędzanie" in power_plan.lower() or "power saver" in power_plan.lower():
        score -= 15
        warnings.append(
            f"Active power plan is '{power_plan}' – Windows is limiting CPU performance."
        )

    # 4. Disk & S.M.A.R.T.
    disk = psutil.disk_usage("C:\\")
    disk_free_gb = round(disk.free / (1024**3), 1)
    if disk.percent > 88:
        score -= 15
        warnings.append(f"Low disk space on C: ({disk_free_gb} GB free).")

    smart_statuses = []
    for drive in w.Win32_DiskDrive():
        model = drive.Model.strip()
        status = drive.Status.strip() if drive.Status else "Unknown"
        smart_statuses.append(f"{model}: {status}")
        if status.lower() != "ok":
            score -= 30
            warnings.append(
                f"CRITICAL (S.M.A.R.T.): Drive '{model}' reported status '{status}'! Back up your data."
            )

    # 5. Benchmark result
    if benchmark_result:
        drop = benchmark_result["drop_percent"]
        if drop > 10:
            score -= 25
            warnings.append(
                f"CPU performance drop detected under load ({drop}%). Possible thermal throttling."
            )

    # 6. Uptime
    boot_time = psutil.boot_time()
    uptime_hours = round((time.time() - boot_time) / 3600, 1)
    if uptime_hours > 120:
        score -= 5
        warnings.append(
            f"System has been running without a full restart for {uptime_hours} hrs (Fast Startup). System reboot recommended."
        )

    # 7. Top RAM processes
    top_procs = []
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            mem_mb = proc.info["memory_info"].rss / (1024 * 1024)
            top_procs.append((proc.info["name"], round(mem_mb)))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    top_procs.sort(key=lambda x: x[1], reverse=True)
    top_ram_str = ", ".join([f"{name} ({mb} MB)" for name, mb in top_procs[:3]])

    return {
        "cpu_name": cpu_name,
        "cpu_usage": cpu_usage,
        "gpu_name": gpu_name,
        "ram_total_gb": total_gb,
        "ram_percent": ram.percent,
        "ram_speed": ram_speed,
        "refresh_rate": refresh_rate,
        "disk_free_gb": disk_free_gb,
        "power_plan": power_plan,
        "smart_summary": " | ".join(smart_statuses) if smart_statuses else "No data",
        "score": max(0, score),
        "warnings": warnings,
        "uptime_hours": uptime_hours,
        "top_processes": top_ram_str,
    }