import asyncio
import json
import psutil
import websockets

# Sesuaikan dengan port server ARVI (misal port 8080 atau 8000)
SERVER_WS_URL = "ws://127.0.0.1:8080/ws/node"

async def report_telemetry(ws):
    """Mengirim telemetri hardware laptop ke ARVI Core secara berkala."""
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
            await asyncio.sleep(4)  # Update setiap 4 detik
        except Exception as e:
            print(f"[!] Gagal mengirim telemetri: {e}")
            break

async def listen_commands(ws):
    """Mendengarkan instruksi eksekusi dari ARVI Core."""
    while True:
        try:
            message = await ws.recv()
            data = json.loads(message)
            print(f"[*] Perintah diterima dari ARVI Core: {data}")
            
            # Di sini kita bisa menambahkan eksekusi script lokal otomatis
        except Exception as e:
            print(f"[!] Koneksi listener terputus: {e}")
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