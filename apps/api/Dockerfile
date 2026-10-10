FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# psycopg[binary] needs no build deps; keep image slim
COPY requirements.txt requirements-ml.txt ./
# INSTALL_ML=false: image nhẹ, chatbot chạy BM25 không vector (index_corpus/index_listings sẽ từ chối chạy)
ARG INSTALL_ML=true
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi

# corpus pháp lý/KTX cho `python -m app.room_service.legal_knowledge.index_corpus` (~0,8 MB JSON)
COPY chatbot_corpus ./chatbot_corpus
COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
