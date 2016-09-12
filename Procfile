web: gunicorn backend.app:app --bind=0.0.0.0:$PORT --workers=1 --worker-class aiohttp.worker.GunicornWebWorker
frontend: gunicorn frontend.app:app --bind=0.0.0.0:5000 --workers=1 --worker-class aiohttp.worker.GunicornWebWorker
cmd: gunicorn worker.app:app --bind=0.0.0.0:8000 --workers=1 --worker-class aiohttp.worker.GunicornWebWorker
