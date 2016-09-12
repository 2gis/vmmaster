cmd: gunicorn backend.app:app --bind=0.0.0.0:9000 --workers=1 --worker-class aiohttp.worker.GunicornWebWorker
web: gunicorn frontend.app:app --bind=0.0.0.0:$PORT --workers=1 --worker-class aiohttp.worker.GunicornWebWorker
worker: gunicorn worker.app:app --bind=0.0.0.0:8000 --workers=1 --worker-class aiohttp.worker.GunicornWebWorker
