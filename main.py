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
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chat Bot de Phygital - Dashboard</title>
        <style>
            * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            body { background-color: #121212; color: #e0e0e0; margin: 0; padding: 0; }
            
            /* LOGIN SCREEN */
            #loginSection { display: flex; justify-content: center; align-items: center; height: 100vh; }
            .login-card { background: #1e1e1e; padding: 40px; border-radius: 12px; width: 340px; text-align: center; box-shadow: 0 8px 24px rgba(0,0,0,0.6); }
            .login-card h2 { color: #fff; margin-bottom: 20px; }
            input, select { width: 100%; padding: 12px; margin: 8px 0; border-radius: 6px; border: 1px solid #333; background: #2b2b2b; color: #fff; }
            button { width: 100%; padding: 12px; background: #6200ee; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 10px; transition: 0.2s; }
            button:hover { background: #3700b3; }

            /* DASHBOARD MAIN */
            #dashboardSection { display: none; padding: 30px; max-width: 1200px; margin: 0 auto; }
            header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 25px; }
            .user-badge { background: #2b2b2b; padding: 6px 14px; border-radius: 20px; font-size: 14px; color: #00e676; border: 1px solid #00e676; }

            /* GRID & CARDS */
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .card { background: #1e1e1e; border-radius: 10px; padding: 20px; border: 1px solid #2c2c2c; }
            .card h3 { color: #bb86fc; margin-top: 0; border-bottom: 1px solid #2a2a2a; padding-bottom: 10px; }

            /* STATS METRICS */
            .stat-box { font-size: 36px; font-weight: bold; color: #00e676; text-align: center; margin: 20px 0; }

            /* TABLES & LISTS */
            ul { list-style: none; padding: 0; }
            li { background: #2a2a2a; padding: 10px; margin-bottom: 8px; border-radius: 6px; font-size: 14px; display: flex; justify-content: space-between; align-items: center; }
            .btn-danger { background: #cf6679; padding: 4px 8px; font-size: 12px; width: auto; margin: 0; }
            .btn-danger:hover { background: #b00020; }
        </style>
    </head>
    <body>

        <!-- PANTALLA DE LOGIN -->
        <div id="loginSection">
            <div class="login-card">
                <h2>Chat Bot Phygital</h2>
                <input type="text" id="userInput" placeholder="Usuario">
                <input type="password" id="passInput" placeholder="Contraseña">
                <button onclick="login()">Iniciar Sesión</button>
                <p id="errorMsg" style="color: #cf6679; display: none; margin-top: 10px; font-size: 14px;">Credenciales incorrectas</p>
            </div>
        </div>

        <!-- PANEL DE CONTROL ADMIN / OPERADOR -->
        <div id="dashboardSection">
            <header>
                <h2>Panel de Control - Chat Bot Phygital</h2>
                <span class="user-badge" id="userInfo">Usuario</span>
            </header>

            <div class="grid">
                <!-- METRICAS DE ACTIVIDAD -->
                <div class="card">
                    <h3>📊 Estadísticas Rápidas</h3>
                    <p>Total de respuestas enviadas:</p>
                    <div class="stat-box" id="statTotal">0</div>
                    <button onclick="cargarEstadisticas()">🔄 Actualizar Métricas</button>
                </div>

                <!-- GESTIÓN DE USUARIOS (OCULTO SI NO ES ADMIN) -->
                <div class="card" id="adminUserCard" style="display: none;">
                    <h3>👤 Crear Nuevo Usuario</h3>
                    <input type="text" id="newUsername" placeholder="Nombre de usuario">
                    <input type="password" id="newPassword" placeholder="Contraseña">
                    <input type="text" id="newTiendas" placeholder="Tiendas asignadas (ej: tienda1, tienda2)">
                    <button onclick="crearUsuario()">Crear Usuario</button>
                </div>

                <!-- SUBIDA DE CATALOGOS Y ARCHIVOS -->
                <div class="card">
                    <h3>📁 Subir Archivos (Catálogos/PDFs)</h3>
                    <input type="file" id="fileInput">
                    <button onclick="subirArchivo()">Subir Archivo a Render</button>
                    <p id="fileResult" style="font-size: 12px; word-break: break-all; color: #80d8ff; margin-top: 10px;"></p>
                </div>

                <!-- LIMPIEZA DE HISTORIAL E IA -->
                <div class="card" id="adminIaCard" style="display: none;">
                    <h3>🧠 Aprendizaje e Historial de IA</h3>
                    <p style="font-size: 13px; color: #aaa;">Borra el registro de fallas recurrentes de un número de cliente:</p>
                    <input type="text" id="cleanNum" placeholder="Número del cliente (ej: +521...)">
                    <button class="btn-danger" style="width: 100%; margin-top: 10px;" onclick="limpiarHistorial()">Borrar Historial de Fallas</button>
                </div>
            </div>
        </div>

        <script>
            let currentUser = null;

            async function login() {
                const u = document.getElementById('userInput').value;
                const p = document.getElementById('passInput').value;
                
                try {
                    const resp = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: u, password: p})
                    });
                    
                    if(resp.ok) {
                        currentUser = await resp.json();
                        document.getElementById('loginSection').style.display = 'none';
                        document.getElementById('dashboardSection').style.display = 'block';
                        document.getElementById('userInfo').innerText = `${currentUser.username} (${currentUser.rol})`;

                        // Mostrar herramientas de Admin de forma discreta
                        if (currentUser.rol === 'admin') {
                            document.getElementById('adminUserCard').style.display = 'block';
                            document.getElementById('adminIaCard').style.display = 'block';
                        }
                        
                        cargarEstadisticas();
                    } else {
                        document.getElementById('errorMsg').style.display = 'block';
                    }
                } catch(e) {
                    alert('Error de conexión con el servidor');
                }
            }

            async function cargarEstadisticas() {
                const resp = await fetch('/api/stats');
                if(resp.ok) {
                    const data = await resp.json();
                    document.getElementById('statTotal').innerText = data.total_respuestas || 0;
                }
            }

            async function crearUsuario() {
                const u = document.getElementById('newUsername').value;
                const p = document.getElementById('newPassword').value;
                const t = document.getElementById('newTiendas').value.split(',');

                const resp = await fetch(`/api/auth/crear-usuario?admin_user=${currentUser.username}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        username: u,
                        password: p,
                        tiendas: t,
                        permisos: ["ver_tiendas"]
                    })
                });

                const data = await resp.json();
                if(resp.ok) {
                    alert(data.mensaje);
                    document.getElementById('newUsername').value = '';
                    document.getElementById('newPassword').value = '';
                    document.getElementById('newTiendas').value = '';
                } else {
                    alert(data.detail || 'Error al crear usuario');
                }
            }

            async function subirArchivo() {
                const fileField = document.getElementById('fileInput');
                if(!fileField.files[0]) return alert('Selecciona un archivo');

                const formData = new FormData();
                formData.append('file', fileField.files[0]);

                const resp = await fetch('/api/archivos/subir', {
                    method: 'POST',
                    body: formData
                });

                const data = await resp.json();
                if(resp.ok) {
                    const fullUrl = window.location.origin + data.url;
                    document.getElementById('fileResult').innerHTML = `<b>Enlace generado:</b><br><a href="${fullUrl}" target="_blank" style="color:#80d8ff;">${fullUrl}</a>`;
                } else {
                    alert('Error al subir archivo');
                }
            }

            async function limpiarHistorial() {
                const num = document.getElementById('cleanNum').value;
                if(!num) return alert('Escribe el número');

                const resp = await fetch(`/api/ia/limpiar-historial/${num}?usuario=${currentUser.username}`, {
                    method: 'DELETE'
                });

                const data = await resp.json();
                if(resp.ok) {
                    alert(data.mensaje);
                    document.getElementById('cleanNum').value = '';
                } else {
                    alert(data.detail || 'Error al borrar');
                }
            }
        </script>
    </body>
    </html>
    """
