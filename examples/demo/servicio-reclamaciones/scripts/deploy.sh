#!/usr/bin/env bash
# Uso: ./scripts/deploy.sh <create_claim|get_claim>
set -euo pipefail
case "$1" in
  create_claim) aws lambda update-function-code --function-name demo-create-claim --zip-file fileb://build/create_claim.zip ;;
  get_claim) aws lambda update-function-code --function-name demo-get-claim --zip-file fileb://build/get_claim.zip ;;
esac
