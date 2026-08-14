from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import shutil
import requests

app = FastAPI(title="Chat Bot de Phygital Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos (Catálogos, PDFs, etc.)
os.makedirs("uploads", exist_ok=True)
app.mount("/files", StaticFiles(directory="uploads"), name="files")

# --- BASE DE DATOS EN MEMORIA / PERSISTENCIA ---
# En un entorno de producción se recomienda conectar una base SQLite/PostgreSQL
USUARIOS_DB = {
    "ZoeOrtiz": {
        "password": "25052002",
        "rol": "admin",
        "tiendas": ["todas"],
        "permisos": ["crear_usuarios", "eliminar_historial", "descargar_archivos", "modificar_arbol"]
    }
}

HISTORIAL_FALLAS = {} # { "numero": [{"fecha": "...", "mensaje": "...", "solucionado": False}] }
ESTADOS_ESCALADOS = {} # { "cliente_num": "colega_num" }

# --- MODELOS DE DATOS ---
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    tiendas: List[str]
    permisos: List[str]

class LogMensaje(BaseModel):
    remitente: str
    mensaje: str
    respuesta: str
    tienda_id: Optional[str] = "general"

class ComandoColega(BaseModel):
    colega_num: str
    cliente_num: str
    respuesta_texto: str

# --- MÓDULO DE AUTENTICACIÓN Y ROLES ---
@app.post("/api/auth/login")
def login(user: UserLogin):
    u = USUARIOS_DB.get(user.username)
    if not u or u["password"] != user.password:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"token": "token_simulado", "username": user.username, "rol": u["rol"], "permisos": u["permisos"]}

@app.post("/api/auth/crear-usuario")
def crear_usuario(nuevo_user: UserCreate, admin_user: str = "ZoeOrtiz"):
    # Validación de Rol Admin
    if USUARIOS_DB.get(admin_user, {}).get("rol") != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    USUARIOS_DB[nuevo_user.username] = {
        "password": nuevo_user.password,
        "rol": "operador",
        "tiendas": nuevo_user.tiendas,
        "permisos": nuevo_user.permisos
    }
    return {"status": "ok", "mensaje": f"Usuario {nuevo_user.username} creado exitosamente"}

# --- SUBIDA DE ARCHIVOS A RENDER ---
@app.post("/api/archivos/subir")
def subir_archivo(file: UploadFile = File(...)):
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    url_publica = f"/files/{file.filename}"
    return {"filename": file.filename, "url": url_publica}

# --- INTEGRACIÓN CON MONDAY.COM ---
MONDAY_API_KEY = "TU_API_KEY_DE_MONDAY"
BOARD_ID = "TU_BOARD_ID"

def crear_item_monday(cliente: str, problema: str):
    url = "https://api.monday.com/v2"
    headers = {"Authorization": MONDAY_API_KEY, "Content-Type": "application/json"}
    query = f'''
    mutation {{
        create_item (board_id: {BOARD_ID}, item_name: "Soporte Solicitado: {cliente}") {{
            id
        }}
    }}
    '''
    try:
        requests.post(url, json={'query': query}, headers=headers)
    except Exception as e:
        print("Error Monday:", e)

# --- APRENDIZAJE E HISTORIAL DE FALLAS CON IA ---
@app.post("/api/ia/procesar-mensaje")
def procesar_ia(log: LogMensaje):
    num = log.remitente
    if num not in HISTORIAL_FALLAS:
        HISTORIAL_FALLAS[num] = []
    
    HISTORIAL_FALLAS[num].append({"mensaje": log.mensaje, "respuesta": log.respuesta})
    
    # Detección de fallas repetidas o solicitud explícita de soporte
    fallas_previas = [item["mensaje"] for item in HISTORIAL_FALLAS[num]]
    
    if len(fallas_previas) > 2 or "soporte" in log.mensaje.lower() or "humano" in log.mensaje.lower():
        crear_item_monday(num, log.mensaje)
        return {
            "requiere_escalamiento": True,
            "sugerencia_ia": "El cliente presenta fallas recurrentes. Se ha generado un ticket en Monday.com y notificado a un asesor.",
            "historial": fallas_previas
        }

    return {"requiere_escalamiento": False, "sugerencia_ia": log.respuesta}

@app.delete("/api/ia/limpiar-historial/{numero}")
def limpiar_historial(numero: str, usuario: str):
    if USUARIOS_DB.get(usuario, {}).get("rol") != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para borrar historiales")
    if numero in HISTORIAL_FALLAS:
        del HISTORIAL_FALLAS[numero]
    return {"status": "ok", "mensaje": f"Historial borrado para {numero}"}

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def dashboard_ui():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Chat Bot de Phygital - Dashboard</title>
        <style>
            body { background-color: #121212; color: #ffffff; font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .login-card { background: #1e1e1e; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); width: 300px; text-align: center; }
            input { width: 90%; padding: 10px; margin: 10px 0; border-radius: 6px; border: 1px solid #333; background: #2b2b2b; color: white; }
            button { width: 98%; padding: 10px; background: #3700b3; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
            button:hover { background: #4f00e0; }
        </style>
    </head>
    <body>
        <div class="login-card" id="loginBox">
            <h2>Chat Bot Phygital</h2>
            <input type="text" id="userInput" placeholder="Usuario">
            <input type="password" id="passInput" placeholder="Contraseña">
            <button onclick="login()">Iniciar Sesión</button>
            <p id="errorMsg" style="color: #ff5252; display: none;">Credenciales incorrectas</p>
        </div>

        <script>
            async function login() {
                const u = document.getElementById('userInput').value;
                const p = document.getElementById('passInput').value;
                const resp = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                if(resp.ok) {
                    const data = await resp.json();
                    alert('Bienvenido ' + data.username + ' (' + data.rol + ')');
                    // Aquí cargaremos el panel completo de administración
                } else {
                    document.getElementById('errorMsg').style.display = 'block';
                }
            }
        </script>
    </body>
    </html>
    """
