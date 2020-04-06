#! /bin/bash

set -e
readonly ecr=$1

docker tag covid19/dashboard "${ecr}"
docker push "${ecr}"
