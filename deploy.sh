#! /bin/bash

set -e
readonly cluster=$1
readonly  service=$2

aws ecs update-service --cluster "${cluster}" --service "${service}" --force-new-deployment
