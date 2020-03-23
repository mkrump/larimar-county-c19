A [Dash](https://plot.ly/dash/) dashboard summarizing rail related traffic blockages using the data collected at [fra.dot.gov/blockedcrossings](https://www.fra.dot.gov/blockedcrossings).

### Requirements
- [Docker](https://www.docker.com/)

### Running locally
Create `.env` file with relevant settings (if want to override defaults)
```
FRA_DOT_GOV_CERT_PATH=fra-dot-gov-chain.pem
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
            --password-stdin <ECR-REPO>/ecs-train

    docker tag train/dashboard <ECR-REPO>/ecs-train
    docker push <ECR-REPO>/ecs-train
    ```

* Update the task definition on ECS to use new container
* Update the service to use new task definition


### Demo
[blocked crossing dashboard](http://blocked-crossings.matthewkrump.com/) 

