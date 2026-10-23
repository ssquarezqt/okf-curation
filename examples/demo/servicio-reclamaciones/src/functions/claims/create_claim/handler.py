"""POST /claims — registra una reclamación por retraso y decide si se aprueba automáticamente."""
import json
import os
import uuid

import boto3

from shared.auth import require

CLAIMS_TABLE = os.environ.get("CLAIMS_TABLE", "demo-claims")
AUTO_APPROVE_LIMIT = int(os.environ.get("AUTO_APPROVE_LIMIT", "250"))
MIN_DELAY_MINUTES = int(os.environ.get("MIN_DELAY_MINUTES", "180"))
REQUIRED = ("booking_ref", "flight_number", "delay_minutes", "amount")

table = boto3.resource("dynamodb").Table("demo-claims")


def lambda_handler(event, context):
    claims, err = require(event, {"Agentes", "Supervisores"})
    if err:
        return err
    body = json.loads(event.get("body") or "{}")
    missing = [f for f in REQUIRED if f not in body]
    if missing:
        return {"statusCode": 400, "body": json.dumps({"error": f"Faltan campos: {', '.join(missing)}"})}
    if body["delay_minutes"] < MIN_DELAY_MINUTES:
        return {"statusCode": 422, "body": json.dumps({"error": "El retraso no da derecho a compensación"})}
    # OJO: la aprobación automática solo aplica por debajo del límite; el resto va a revisión manual
    status = "APPROVED" if body["amount"] <= AUTO_APPROVE_LIMIT else "PENDING_REVIEW"
    item = {"claim_id": str(uuid.uuid4()), "status": status, "created_by": claims.get("sub"), **{k: body[k] for k in REQUIRED}}
    table.put_item(Item=item)
    return {"statusCode": 201, "body": json.dumps({"claim_id": item["claim_id"], "status": status})}
