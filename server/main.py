import os
import json
import asyncio
import requests
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Muat variabel environment dari .env di root project
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

META_API_KEY = os.getenv("META_API_KEY", "")
META_URL = "https://api.meta.ai/v1/responses"

app = FastAPI(title="ARVI OS Core Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pool koneksi WebSocket
hud_clients: Set[WebSocket] = set()
node_clients: Set[WebSocket] = set()

def query_meta_muse(user_prompt: str, effort: str = "low") -> str:
    """Mengirim instruksi ke Meta Model API (Muse Spark 1.3)"""
    if not META_API_KEY:
        return "[CONFIG ERROR] META_API_KEY belum disetel di file .env."

    headers = {
        "Authorization": f"Bearer {META_API_KEY}",
        "Content-Type": "application/json"
    }

    structured_input = (
        "You are the central intelligence engine powering ARVI OS (A Rather Virtual Intelligence), "
        "an engineering co-pilot and system orchestrator. "
        "While your foundational AI model is Meta's Muse Spark, your operational role in this environment "
        "is the ARVI Core. Always report status concisely and tactfully in the persona of a reliable J.A.R.V.I.S.-like co-pilot.\n\n"
        f"Operational Command: {user_prompt}"
    )

    payload = {
        "model": "muse-spark-1.3",
        "reasoning": {"effort": effort},
        "input": structured_input
    }

    try:
        response = requests.post(META_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            output_items = data.get("output", []) if isinstance(data, dict) else data

            for item in output_items:
                if isinstance(item, dict) and item.get("type") == "message":
                    for content_part in item.get("content", []):
                        if content_part.get("type") == "output_text":
                            return content_part.get("text", "")
            return "Respons diterima tetapi blok teks tidak ditemukan."
        else:
            return f"[API ERROR {response.status_code}] {response.text}"
    except Exception as e:
        return f"[EXCEPTION] {str(e)}"


# WebSocket Endpoint untuk Tactical HUD
@app.websocket("/ws/hud")
async def websocket_hud_endpoint(websocket: WebSocket):
    await websocket.accept()
    hud_clients.add(websocket)
    print("[+] HUD connected to ARVI Core")

    try:
        # Kirim notifikasi sambutan ke terminal HUD
        await websocket.send_text(json.dumps({
            "type": "agent_log",
            "message": "[CORE] WebSocket handshake verified. Telemetry synchronized."
        }))

        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)

            if data.get("type") == "user_command":
                cmd = data.get("command", "")
                print(f"[*] Received command from HUD: {cmd}")

                # Log proses ke terminal HUD
                await websocket.send_text(json.dumps({
                    "type": "agent_log",
                    "message": f"[INFERENCE] Querying Muse Spark 1.3 for: '{cmd}'..."
                }))

                # Jalankan inferensi Meta API di threadpool agar WebSocket tidak terblokir
                loop = asyncio.get_event_loop()
                response_text = await loop.run_in_executor(None, query_meta_muse, cmd)

                # Broadcast balasan ARVI ke HUD
                await websocket.send_text(json.dumps({
                    "type": "arvi_response",
                    "text": response_text
                }))

                # Notifikasi node jika ada eksekusi terkait sistem lokal
                for node in node_clients:
                    await node.send_text(json.dumps({
                        "event": "command_processed",
                        "command": cmd
                    }))

    except WebSocketDisconnect:
        hud_clients.remove(websocket)
        print("[-] HUD disconnected")


# WebSocket Endpoint untuk Edge Nodes (Laptop / Mobile Node)
@app.websocket("/ws/node")
async def websocket_node_endpoint(websocket: WebSocket):
    await websocket.accept()
    node_clients.add(websocket)
    print("[+] Edge Node connected")

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            # Meneruskan log aktivitas node langsung ke HUD
            if data.get("type") == "telemetry":
                for hud in hud_clients:
                    await hud.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[NODE TELEMETRY] {data.get('payload')}"
                    }))
    except WebSocketDisconnect:
        node_clients.remove(websocket)
        print("[-] Edge Node disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)