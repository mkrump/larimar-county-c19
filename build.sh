#! /bin/bash

set -e
readonly ecr=$1

docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker tag covid19/dashboard "${ecr}"
docker push "${ecr}"
