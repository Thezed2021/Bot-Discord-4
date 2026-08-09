# Usamos a imagem Slim do Python que é leve, segura e compila o PyNaCl rapidamente
FROM python:3.11-slim

# Impede que o Python crie arquivos .pyc e força a saída sem buffer (ótimo para logs do Render)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instala o FFmpeg (necessário para processar o áudio) e limpa o cache do apt para economizar espaço
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
        apt-get clean && \
            rm -rf /var/lib/apt/lists/*

            # Define o diretório de trabalho dentro do container
            WORKDIR /app

            # Copia os requisitos e instala
            COPY requirements.txt .
            RUN pip install --no-cache-dir -r requirements.txt

            # Copia todo o restante do código
            COPY . .

            # Comando de inicialização
            CMD ["python", "main.py"]