A [Dash](https://plot.ly/dash/) dashboard summarizing confirmed Larimer County COVID-19 cases.

### Requirements
- [Docker](https://www.docker.com/)

### Running locally
Create `.env` file with relevant settings (if want to override defaults)
```
CACHE_DIR=/tmp/cache
DEBUG=true
HOST=0.0.0.0
PORT=5000
```

```
docker-compose up
```

### Deploy
* Test build
    ```
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build
    ```

* Deploy to ECS
    ```
    aws ecr get-login-password \
            --region us-west-2 | docker login \
            --username AWS \
            --password-stdin $ECR

    ./build.sh $ECR
    ./deploy.sh $CLUSTER $SERVICE
    ```

