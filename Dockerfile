FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Application port inside the container
EXPOSE 8000

# Prepare the database, then start the web server on container port 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py bootstrap && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
