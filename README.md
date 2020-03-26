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
* Build container 
    ```
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
    ```

* Push new container to ECR
    ```
    aws ecr get-login-password \
            --region us-west-2 | docker login \
            --username AWS \
            --password-stdin covid19

    docker tag covid19/dashboard <ECR-REPO>/covid19
    docker push <ECR-REPO>/covid19
    ```

* Update the task definition on ECS to use new container
* Update the service to use new task definition


### Demo
[Larimer County COVID-19 dashboard](https://www.larimer-county-c19.com/) 

