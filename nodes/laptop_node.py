import asyncio
import json
import subprocess
import psutil
import websockets
import time

SERVER_WS_URL = "ws://127.0.0.1:8080/ws/node"


def get_top_cpu_processes(limit=5):
    """Mengambil proses terberat dengan sampling interval Windows."""
    # Sampling pertama untuk inisialisasi timer psutil
    procs = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            p.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    time.sleep(0.3)  # Jeda sampling

    # Sampling kedua untuk mendapatkan angka beban riil
    for p in psutil.process_iter(['pid', 'name']):
        try:
            cpu = p.cpu_percent()
            procs.append({'pid': p.info['pid'], 'name': p.info['name'], 'cpu_percent': cpu})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    procs.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
    top = procs[:limit]
    lines = [f"PID {p['pid']:>5} | {p['name'][:18]:<18} | CPU: {p['cpu_percent']}%" for p in top]
    return "\n".join(lines)

def run_ping_test(host="8.8.8.8"):
    """Menjalankan uji ping cepat ke jaringan luar."""
    try:
        res = subprocess.run(["ping", "-n", "2", host], capture_output=True, text=True, timeout=5)
        for line in res.stdout.splitlines():
            if "Average" in line or "Rata-rata" in line or "Reply from" in line:
                return line.strip()
        return "Ping selesai tanpa statistik latensi."
    except Exception as e:
        return f"Ping gagal: {str(e)}"

async def report_telemetry(ws):
    """Mengirim telemetri berkala ke server."""
    while True:
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            battery = psutil.sensors_battery()
            battery_pct = f"{battery.percent}%" if battery else "AC_POWER"

            telemetry_data = {
                "type": "telemetry",
                "node_id": "LAPTOP_01",
                "payload": f"CPU: {cpu_usage}% | RAM: {ram.percent}% | PWR: {battery_pct}"
            }
            await ws.send(json.dumps(telemetry_data))
            await asyncio.sleep(4)
        except Exception:
            break

async def listen_commands(ws):
    """Mendengarkan instruksi aksi dari ARVI Core."""
    while True:
        try:
            raw_msg = await ws.recv()
            data = json.loads(raw_msg)
            action = data.get("action")

            if action == "INSPECT_CPU":
                print("[*] Menjalankan inspeksi proses CPU...")
                proc_list = get_top_cpu_processes()
                await ws.send(json.dumps({
                    "type": "action_result",
                    "action": "INSPECT_CPU",
                    "output": f"[TOP PROCESSES]\n{proc_list}"
                }))

            elif action == "PING_NETWORK":
                print("[*] Menjalankan uji ping jaringan...")
                ping_res = run_ping_test()
                await ws.send(json.dumps({
                    "type": "action_result",
                    "action": "PING_NETWORK",
                    "output": f"[NET PING] {ping_res}"
                }))

        except Exception as e:
            print(f"[!] Listener node terputus: {e}")
            break

async def run_node():
    print("[*] Menghubungkan Edge Node LAPTOP_01 ke ARVI Core...")
    while True:
        try:
            async with websockets.connect(SERVER_WS_URL) as ws:
                print("[+] Terhubung ke ARVI Core WebSocket!")
                await asyncio.gather(
                    report_telemetry(ws),
                    listen_commands(ws)
                )
        except Exception as err:
            print(f"[-] Menunggu server aktif ({err}). Coba lagi dalam 3 detik...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(run_node())