from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uuid
import aiohttp
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_sessions = {}

class KahootClient:
    def __init__(self):
        self.session = None
        self.token = None
        
    async def get_game_info(self, game_pin: int):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://kahoot.it/reserve/session/{game_pin}/?challenge=true"
                async with session.post(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data
        except Exception as e:
            print(f"Get game info error: {e}")
        return None

    async def join_game(self, game_pin: int, username: str):
        self.session = aiohttp.ClientSession()
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json"
            }
            
            url = f"https://kahoot.it/api/v2/login"
            payload = {
                "pin": str(game_pin),
                "username": username,
                "type": "player"
            }
            
            async with self.session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data.get('playerId') or data.get('token')
                    print(f"✅ Bot '{username}' connecté - Token: {self.token}")
                    return True
                else:
                    text = await resp.text()
                    print(f"❌ {username} - Status {resp.status}: {text[:100]}")
                    return False
        except asyncio.TimeoutError:
            print(f"⏱️ Timeout pour {username}")
            return False
        except Exception as e:
            print(f"❌ Erreur {username}: {str(e)[:100]}")
            return False
        finally:
            if self.session:
                await self.session.close()

async def connect_bot(game_pin: int, name: str, session_id: str, auto_reconnect: bool):
    reconnect_count = 0
    max_retries = 8 if auto_reconnect else 1
    
    while reconnect_count < max_retries:
        client = KahootClient()
        try:
            success = await client.join_game(game_pin=game_pin, username=name)
            if success:
                await asyncio.sleep(3600)
                break
            else:
                reconnect_count += 1
                if reconnect_count < max_retries:
                    await asyncio.sleep(2)
        except Exception as e:
            print(f"Bot error: {e}")
            reconnect_count += 1
            if reconnect_count < max_retries:
                await asyncio.sleep(2)

@app.post("/api/start")
async def start_bots(
    game_pin: int = Form(...),
    base_name: str = Form(...),
    nb_bots: int = Form(...),
    auto_reconnect: bool = Form(False)
):
    if nb_bots < 1 or nb_bots > 800:
        return {"error": "Entre 1 et 800 bots"}
    
    session_id = str(uuid.uuid4())[:8]
    tasks = []
    
    print(f"\n🎮 Démarrage session {session_id}")
    print(f"Code Kahoot: {game_pin}")
    print(f"Nom: {base_name}")
    print(f"Bots: {nb_bots}")
    print(f"Reconnexion: {auto_reconnect}\n")
    
    for i in range(nb_bots):
        name = base_name if i == 0 else f"{base_name}{i}"
        task = asyncio.create_task(connect_bot(game_pin, name, session_id, auto_reconnect))
        tasks.append(task)
        await asyncio.sleep(0.05)
    
    active_sessions[session_id] = tasks
    
    return {
        "status": "success",
        "session_id": session_id,
        "message": f"{nb_bots} bots en cours de connexion...",
        "count": nb_bots
    }

@app.get("/api/stop/{session_id}")
async def stop_session(session_id: str):
    if session_id in active_sessions:
        for task in active_sessions[session_id]:
            if not task.done():
                task.cancel()
        del active_sessions[session_id]
        return {"status": "stopped"}
    return {"status": "not_found"}

@app.get("/api/sessions")
async def get_sessions():
    return {"active": len(active_sessions), "ids": list(active_sessions.keys())}

@app.get("/health")
async def health():
    return {"status": "ok"}

