from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uuid
import aiohttp
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    def __init__(self, game_pin: int, username: str):
        self.game_pin = game_pin
        self.username = username
        self.ws = None
        self.session = None
        
    async def get_challenge(self):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://kahoot.it/reserve/session/{self.game_pin}/?challenge=true"
                async with session.post(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Challenge reçu: {data}")
                        return data.get('challenge')
        except Exception as e:
            logger.error(f"Erreur challenge: {e}")
        return None

    async def join_game(self):
        try:
            challenge = await self.get_challenge()
            if not challenge:
                logger.warning(f"{self.username}: Pas de challenge")
                return False

            self.session = aiohttp.ClientSession()
            headers = {
                "User-Agent": "Mozilla/5.0",
            }
            
            url = "https://kahoot.it/api/v2/login"
            payload = {
                "pin": str(self.game_pin),
                "username": self.username,
                "type": "player",
                "challenge": challenge
            }
            
            async with self.session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                text = await resp.text()
                if resp.status == 200:
                    try:
                        data = json.loads(text)
                        logger.info(f"✅ {self.username} connecté! Token: {data.get('playerId', 'N/A')}")
                        return True
                    except:
                        logger.error(f"JSON parse error: {text[:100]}")
                        return False
                else:
                    logger.warning(f"❌ {self.username} - Status {resp.status}: {text[:150]}")
                    return False
                    
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Timeout: {self.username}")
            return False
        except Exception as e:
            logger.error(f"❌ Exception {self.username}: {str(e)}")
            return False

    async def close(self):
        if self.session:
            await self.session.close()

async def connect_bot(game_pin: int, name: str, session_id: str, auto_reconnect: bool):
    reconnect_count = 0
    max_retries = 8 if auto_reconnect else 1
    
    while reconnect_count < max_retries:
        client = KahootClient(game_pin, name)
        try:
            success = await client.join_game()
            if success:
                logger.info(f"🎯 {name} reste connecté 1h...")
                await asyncio.sleep(3600)
                break
            else:
                reconnect_count += 1
                if reconnect_count < max_retries:
                    logger.info(f"🔄 {name} retry {reconnect_count}...")
                    await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Bot crash: {e}")
            reconnect_count += 1
            if reconnect_count < max_retries:
                await asyncio.sleep(2)
        finally:
            await client.close()

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
    
    logger.info(f"\n{'='*50}")
    logger.info(f"🎮 NOUVELLE SESSION: {session_id}")
    logger.info(f"Code Kahoot: {game_pin}")
    logger.info(f"Nom: {base_name}")
    logger.info(f"Bots: {nb_bots}")
    logger.info(f"{'='*50}\n")
    
    for i in range(nb_bots):
        name = base_name if i == 0 else f"{base_name}{i}"
        task = asyncio.create_task(connect_bot(game_pin, name, session_id, auto_reconnect))
        tasks.append(task)
        await asyncio.sleep(0.05)
    
    active_sessions[session_id] = {
        'tasks': tasks,
        'count': nb_bots,
        'game_pin': game_pin
    }
    
    logger.info(f"⚡ {nb_bots} bots lancés!\n")
    
    return {
        "status": "success",
        "session_id": session_id,
        "message": f"{nb_bots} bots en cours de connexion...",
        "count": nb_bots
    }

@app.get("/api/stop/{session_id}")
async def stop_session(session_id: str):
    if session_id in active_sessions:
        session_data = active_sessions[session_id]
        for task in session_data['tasks']:
            if not task.done():
                task.cancel()
        del active_sessions[session_id]
        logger.info(f"❌ Session {session_id} arrêtée")
        return {"status": "stopped"}
    return {"status": "not_found"}

@app.get("/api/sessions")
async def get_sessions():
    return {"active": len(active_sessions), "ids": list(active_sessions.keys())}

@app.get("/health")
async def health():
    return {"status": "ok"}


