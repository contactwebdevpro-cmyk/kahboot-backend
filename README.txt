POUR RENDER:

1. Va sur render.com
2. Dashboard → New Web Service
3. Connecte ce repo GitHub
4. Settings:
   - Environment: Python 3
   - Build Command: pip install -r requirements.txt
   - Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
5. Create Web Service
6. Attends le déploiement (environ 2-3 minutes)
7. Copie l'URL générée
8. Mets à jour dans Vercel/index.html ligne 259

L'URL sera: https://kahoot-xxx.onrender.com
