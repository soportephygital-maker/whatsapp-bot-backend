from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

app = FastAPI(title="WhatsApp Bot Dashboard")

# Permitir conexiones desde la App y la Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estructuras de datos
class RegistroLog(BaseModel):
    remitente: str
    palabra_clave: str
    respuesta: str

# Almacenamiento en memoria (se puede conectar a BD después)
logs_respuestas = []

@app.get("/")
def home():
    return {"status": "ok", "mensaje": "Servidor del Bot de WhatsApp Activo"}

# Endpoint que llamará la App Android al responder
@app.post("/api/log")
def registrar_respuesta(log: RegistroLog):
    registro = {
        "remitente": log.remitente,
        "palabra_clave": log.palabra_clave,
        "respuesta": log.respuesta,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    logs_respuestas.append(registro)
    return {"status": "registrado", "total": len(logs_respuestas)}

# Endpoint para ver las estadísticas en el Dashboard
@app.get("/api/stats")
def obtener_estadisticas():
    return {
        "total_respuestas": len(logs_respuestas),
        "ultimos_logs": logs_respuestas[-10:] # Últimos 10 registros
    }