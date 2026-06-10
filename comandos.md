1. Borrar todos los datos de Redis (FLUSH):


docker exec PopToken-redis redis-cli FLUSHALL


2. Sembrar el génesis de nuevo:


python -m scripts.seed_genesis


3. Levantar la API FastAPI:


python -m uvicorn app.main:app --reload --port 8888


ejemplos de post /tx para probar con fastAPI

{
  "type": "emision",
  "from": "Hoyts_0xA1b2",
  "to": "Alice",
  "tokens": 10,
  "motivo": "compra_entrada",
  "pelicula": "Dune",
  "timestamp": "2026-06-10T20:15:00Z"
}

{
  "type": "transferencia",
  "from": "Alice",
  "to": "Bob",
  "tokens": 4,
  "timestamp": "2026-06-10T21:00:00Z"
}
