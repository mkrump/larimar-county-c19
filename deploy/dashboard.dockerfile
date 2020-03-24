FROM python:3

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY settings.py ./
COPY assets ./assets

COPY app.py ./

#https://pythonspeed.com/articles/gunicorn-in-docker/
# "--forwarded-allow-ips", "*" assumes is always run behind a trusted SSL termination load balancer
CMD [ "gunicorn", "--bind", "0.0.0.0", "--log-file", "-", "--worker-tmp-dir", "/dev/shm", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "--forwarded-allow-ips", "*", "app:server" ]