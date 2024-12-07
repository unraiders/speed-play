FROM python:3.11-alpine

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apk add --no-cache gcc musl-dev linux-headers

# Copiar los archivos necesarios
COPY requirements.txt .
COPY speed-play.py .
COPY .env-example .env

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Configurar el timezone
ENV TZ=Europe/Madrid

# Ejecutar el script
CMD ["python", "speed-play.py"]
