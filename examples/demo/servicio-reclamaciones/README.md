# servicio-reclamaciones

API serverless (AWS Lambda + API Gateway) para registrar y consultar reclamaciones de pasajeros por retraso.
Cada Lambda HTTP vive en `src/functions/<área>/<nombre>/handler.py`; el código compartido, en `src/shared/`.

Despliegue: `./scripts/deploy.sh <funcion>`.
