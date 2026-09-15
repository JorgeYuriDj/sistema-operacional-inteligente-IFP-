FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && groupadd --gid 10001 survey && useradd --uid 10001 --gid survey --no-create-home survey
COPY app.py storage.py survey.py manage.py wsgi.py ./
COPY migrations ./migrations
COPY templates ./templates
COPY static ./static
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import os,urllib.request; r=urllib.request.Request('http://127.0.0.1:8080/healthz',headers={'Host':os.environ['IFP_HOST']}); assert urllib.request.urlopen(r,timeout=3).status==200"
CMD ["gunicorn","--bind","0.0.0.0:8080","--workers","2","--threads","4","--timeout","30","--worker-tmp-dir","/tmp","--limit-request-line","2048","--limit-request-fields","40","--limit-request-field_size","8190","wsgi:app"]
