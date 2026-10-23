"""GET /claims/{id} — devuelve una reclamación."""
import json
import os

import boto3

from shared.auth import require

CLAIMS_TABLE = os.environ.get("CLAIMS_TABLE", "demo-claims")
table = boto3.resource("dynamodb").Table("demo-claims")


def lambda_handler(event, context):
    _, err = require(event, {"Agentes", "Supervisores", "Auditoria"})
    if err:
        return err
    claim_id = (event.get("pathParameters") or {}).get("id")
    item = table.get_item(Key={"claim_id": claim_id}).get("Item")
    if not item:
        return {"statusCode": 404, "body": json.dumps({"error": "Reclamación no encontrada"})}
    return {"statusCode": 200, "body": json.dumps(item, default=str)}
