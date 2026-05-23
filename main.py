from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uuid
import aiohttp

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
        
    async def join_game(self, game_pin: int, username: str):
        self.session = aiohttp.ClientSession()
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            url = "https://kahoot.it/api/v2/login"
            payload = {
                "pin": game_pin,
                "username": username,
                "type": "player"
            }
            async with self.session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed: {resp.status}")
                return await resp.json()
        except Exception as e:
            if self.session:
                await self.session.close()
            raise e

async def connect_bot(game_pin: int, name: str, session_id: str, auto_reconnect: bool):
    reconnect_count = 0
    while True:
        client = KahootClient()
        try:
            await client.join_game(game_pin=game_pin, username=name)
            await asyncio.sleep(3600)
            break
        except Exception:
            reconnect_count += 1
            if auto_reconnect and reconnect_count < 8:
                await asyncio.sleep(2)
            else:
                break
        finally:
            if client.session:
                await client.session.close()

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
    
    for i in range(nb_bots):
        name = base_name if i == 0 else f"{base_name}{i}"
        task = asyncio.create_task(connect_bot(game_pin, name, session_id, auto_reconnect))
        tasks.append(task)
        await asyncio.sleep(0.1)
    
    active_sessions[session_id] = tasks
    
    return {
        "status": "success",
        "session_id": session_id,
        "message": f"{nb_bots} bots demarrés",
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
