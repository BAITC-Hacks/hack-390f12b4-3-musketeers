FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt && useradd --create-home app
COPY backend backend
COPY frontend frontend
COPY data data
COPY serve.py run.py ./
RUN mkdir /data && chown app:app /data
USER app
ENV HOST=0.0.0.0 PORT=8080 DATABASE_PATH=/data/city.sqlite3 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/api/health',timeout=2)"
CMD ["python", "serve.py"]
