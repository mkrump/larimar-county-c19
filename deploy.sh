#! /bin/bash

set -e
readonly  service=$1

aws ecs update-service --force-new-deployment --service "${service}"
