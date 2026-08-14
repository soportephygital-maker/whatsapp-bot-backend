from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import shutil
import requests

app = FastAPI(title="Chat Bot de Phygital Backend - Multi-Empresa")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/files", StaticFiles(directory="uploads"), name="files")

# --- BASES DE DATOS EN MEMORIA ---
USUARIOS_DB = {
    "ZoeOrtiz": {
        "password": "25052002",
        "rol": "admin",
        "empresas_autorizadas": ["todas"],
        "permisos": ["crear_usuarios", "crear_empresas", "modificar_arbol", "eliminar_historial"]
    }
}

EMPRESAS_DB = {
    "empresa_demo": {
        "nombre": "Empresa Demo Phygital",
        "tiendas": ["Tienda Centro", "Tienda Norte"],
        "numeros_whatsapp": ["+5215500000000"],
        "arbol_decisiones": {
            "nodo_raiz": "Inicio",
            "opciones": [
                {"comando": "1", "respuesta": "Uso Tecnológico A", "siguiente": "nodo_a"},
                {"comando": "2", "respuesta": "Uso Tecnológico B", "siguiente": "nodo_b"}
            ]
        }
    }
}

HISTORIAL_FALLAS = {}
METRICAS = {"total_respuestas": 0}

# --- MODELOS DE DATOS ---
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    empresas: List[str]
    rol: Optional[str] = "operador"

class EmpresaCreate(BaseModel):
    empresa_id: str
    nombre: str
    tiendas: List[str]
    numeros_whatsapp: List[str]

class ArbolDecisionesModel(BaseModel):
    empresa_id: str
    estructura_arbol: Dict

class LogMensaje(BaseModel):
    remitente: str
    mensaje: str
    respuesta: str
    empresa_id: Optional[str] = "empresa_demo"

# --- AUTENTICACIÓN Y ROLES ---
@app.post("/api/auth/login")
def login(user: UserLogin):
    u = USUARIOS_DB.get(user.username)
    if not u or u["password"] != user.password:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {
        "token": f"token_{user.username}",
        "username": user.username,
        "rol": u["rol"],
        "empresas": u["empresas_autorizadas"],
        "permisos": u["permisos"]
    }

@app.post("/api/auth/crear-usuario")
def crear_usuario(nuevo_user: UserCreate, admin_user: str = "ZoeOrtiz"):
    if USUARIOS_DB.get(admin_user, {}).get("rol") != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    USUARIOS_DB[nuevo_user.username] = {
        "password": nuevo_user.password,
        "rol": nuevo_user.rol,
        "empresas_autorizadas": nuevo_user.empresas,
        "permisos": ["ver_tiendas", "responder_soporte"]
    }
    return {"status": "ok", "mensaje": f"Usuario {nuevo_user.username} creado exitosamente"}

# --- GESTIÓN MULTI-EMPRESA Y ÁRBOLES DE DECISIÓN ---
@app.post("/api/empresas/crear")
def crear_empresa(empresa: EmpresaCreate, admin_user: str = "ZoeOrtiz"):
    if USUARIOS_DB.get(admin_user, {}).get("rol") != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos de administrador")
    
    EMPRESAS_DB[empresa.empresa_id] = {
        "nombre": empresa.nombre,
        "tiendas": empresa.tiendas,
        "numeros_whatsapp": empresa.numeros_whatsapp,
        "arbol_decisiones": {}
    }
    return {"status": "ok", "mensaje": f"Empresa '{empresa.nombre}' creada con éxito."}

@app.get("/api/empresas/listar")
def listar_empresas(usuario: str):
    u = USUARIOS_DB.get(usuario)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if u["rol"] == "admin" or "todas" in u["empresas_autorizadas"]:
        return EMPRESAS_DB
    
    # Filtrar solo las empresas a las que tiene acceso
    return {k: v for k, v in EMPRESAS_DB.items() if k in u["empresas_autorizadas"]}

@app.post("/api/arbol/guardar")
def guardar_arbol(data: ArbolDecisionesModel, usuario: str = "ZoeOrtiz"):
    if USUARIOS_DB.get(usuario, {}).get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden editar el árbol")
    
    if data.empresa_id in EMPRESAS_DB:
        EMPRESAS_DB[data.empresa_id]["arbol_decisiones"] = data.estructura_arbol
        return {"status": "ok", "mensaje": "Árbol de decisiones actualizado correctamente"}
    raise HTTPException(status_code=404, detail="Empresa no encontrada")

@app.get("/api/arbol/obtener/{empresa_id}")
def obtener_arbol(empresa_id: str):
    if empresa_id in EMPRESAS_DB:
        return EMPRESAS_DB[empresa_id]["arbol_decisiones"]
    raise HTTPException(status_code=404, detail="Empresa no encontrada")

# --- CONEXIÓN SINCRO CON LA APP MÓVIL (ANDROID / PHYGITAL APP) ---
@app.get("/api/app/sync-tienda")
def sync_app_móvil(usuario: str):
    u = USUARIOS_DB.get(usuario)
    if not u:
        raise HTTPException(status_code=401, detail="Sesión no válida")
    
    empresas_permitidas = EMPRESAS_DB if u["rol"] == "admin" else {k: v for k, v in EMPRESAS_DB.items() if k in u["empresas_autorizadas"]}
    return {
        "usuario": usuario,
        "rol": u["rol"],
        "empresas_asignadas": empresas_permitidas
    }

@app.get("/api/stats")
def obtener_stats():
    return {"total_respuestas": METRICAS["total_respuestas"]}

# --- SUBIDA DE ARCHIVOS ---
@app.post("/api/archivos/subir")
def subir_archivo(file: UploadFile = File(...)):
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    url_publica = f"/files/{file.filename}"
    return {"filename": file.filename, "url": url_publica}

# --- DASHBOARD HTML / JS INTERACTIVO ---
@app.get("/", response_class=HTMLResponse)
def dashboard_ui():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Phygital - Dashboard Multi-Empresa</title>
        <style>
            * { box-sizing: border-box; font-family: 'Segoe UI', Roboto, sans-serif; }
            body { background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 0; }
            #loginSection { display: flex; justify-content: center; align-items: center; height: 100vh; }
            .login-card { background: #161b22; padding: 40px; border-radius: 12px; width: 340px; border: 1px solid #30363d; text-align: center; }
            input, select, textarea { width: 100%; padding: 10px; margin: 8px 0; border-radius: 6px; border: 1px solid #30363d; background: #0d1117; color: #fff; }
            button { width: 100%; padding: 10px; background: #238636; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 8px; }
            button:hover { background: #2ea043; }
            
            #dashboardSection { display: none; padding: 20px; max-width: 1200px; margin: 0 auto; }
            header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; padding-bottom: 15px; margin-bottom: 20px; }
            .badge { background: #238636; color: #fff; padding: 4px 12px; border-radius: 12px; font-size: 13px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
            .card { background: #161b22; border-radius: 8px; padding: 20px; border: 1px solid #30363d; }
            .card h3 { color: #58a6ff; margin-top: 0; border-bottom: 1px solid #21262d; padding-bottom: 8px; }
        </style>
    </head>
    <body>

        <div id="loginSection">
            <div class="login-card">
                <h2 style="color: #58a6ff;">Phygital Admin</h2>
                <input type="text" id="userInput" placeholder="Usuario">
                <input type="password" id="passInput" placeholder="Contraseña">
                <button onclick="login()">Iniciar Sesión</button>
                <p id="errorMsg" style="color: #f85149; display: none; font-size: 13px;">Credenciales incorrectas</p>
            </div>
        </div>

        <div id="dashboardSection">
            <header>
                <h2>Panel Phygital - Gestión Multi-Empresa</h2>
                <span class="badge" id="userInfo">ZoeOrtiz (admin)</span>
            </header>

            <div class="grid">
                <!-- CREAR EMPRESA -->
                <div class="card" id="cardEmpresa" style="display:none;">
                    <h3>🏢 Registrar Empresa / Tienda</h3>
                    <input type="text" id="empId" placeholder="ID Único (ej: tienda_sur)">
                    <input type="text" id="empNombre" placeholder="Nombre Comercial">
                    <input type="text" id="empTiendas" placeholder="Sucursales (separadas por coma)">
                    <input type="text" id="empNums" placeholder="Números WhatsApp (ej: +521...)">
                    <button onclick="crearEmpresa()">Guardar Empresa</button>
                </div>

                <!-- CREAR USUARIOS -->
                <div class="card" id="cardUsuario" style="display:none;">
                    <h3>👤 Crear Usuario / Operador</h3>
                    <input type="text" id="newUser" placeholder="Nombre de usuario">
                    <input type="password" id="newPass" placeholder="Contraseña">
                    <input type="text" id="newEmpresas" placeholder="ID Empresas permitidas (ej: tienda_sur, tienda_centro)">
                    <button onclick="crearUsuario()">Crear Usuario</button>
                </div>

                <!-- DISEÑO DEL ÁRBOL DE DECISIONES -->
                <div class="card" id="cardArbol" style="display:none;">
                    <h3>🌳 Configurar Árbol de Decisiones</h3>
                    <select id="selectEmpresaArbol"></select>
                    <textarea id="jsonArbol" rows="6" placeholder='{"nodo_raiz": "Inicio", "opciones": [...]}'></textarea>
                    <button onclick="guardarArbol()">Guardar Estructura de Árbol</button>
                </div>

                <!-- VINCULACIÓN APP MÓVIL -->
                <div class="card">
                    <h3>📲 Sincronización con App Phygital</h3>
                    <p style="font-size: 13px; color: #8b949e;">URL activa para configurar en la App Móvil Android:</p>
                    <input type="text" readonly value="https://whatsapp-bot-backend-r3x4.onrender.com/api/app/sync-tienda" style="color: #79c0ff;">
                    <button onclick="probarSyncApp()">Test Conexión App</button>
                </div>
            </div>
        </div>

        <script>
            let currentUser = null;

            async function login() {
                const u = document.getElementById('userInput').value;
                const p = document.getElementById('passInput').value;

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

                    if (currentUser.rol === 'admin') {
                        document.getElementById('cardEmpresa').style.display = 'block';
                        document.getElementById('cardUsuario').style.display = 'block';
                        document.getElementById('cardArbol').style.display = 'block';
                        cargarEmpresas();
                    }
                } else {
                    document.getElementById('errorMsg').style.display = 'block';
                }
            }

            async function crearEmpresa() {
                const id = document.getElementById('empId').value;
                const nom = document.getElementById('empNombre').value;
                const t = document.getElementById('empTiendas').value.split(',');
                const n = document.getElementById('empNums').value.split(',');

                const resp = await fetch(`/api/empresas/crear?admin_user=${currentUser.username}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({empresa_id: id, nombre: nom, tiendas: t, numeros_whatsapp: n})
                });
                const data = await resp.json();
                alert(data.mensaje);
                cargarEmpresas();
            }

            async function crearUsuario() {
                const u = document.getElementById('newUser').value;
                const p = document.getElementById('newPass').value;
                const e = document.getElementById('newEmpresas').value.split(',');

                const resp = await fetch(`/api/auth/crear-usuario?admin_user=${currentUser.username}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p, empresas: e, rol: 'operador'})
                });
                const data = await resp.json();
                alert(data.mensaje);
            }

            async function cargarEmpresas() {
                const resp = await fetch(`/api/empresas/listar?usuario=${currentUser.username}`);
                const empresas = await resp.json();
                const sel = document.getElementById('selectEmpresaArbol');
                sel.innerHTML = '';
                for(let id in empresas) {
                    sel.innerHTML += `<option value="${id}">${empresas[id].nombre} (${id})</option>`;
                }
            }

            async function guardarArbol() {
                const empId = document.getElementById('selectEmpresaArbol').value;
                const jsonText = document.getElementById('jsonArbol').value;
                try {
                    const parsed = JSON.parse(jsonText);
                    const resp = await fetch(`/api/arbol/guardar?usuario=${currentUser.username}`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({empresa_id: empId, estructura_arbol: parsed})
                    });
                    const data = await resp.json();
                    alert(data.mensaje);
                } catch(e) {
                    alert('JSON inválido en el árbol de decisiones');
                }
            }

            async function probarSyncApp() {
                const resp = await fetch(`/api/app/sync-tienda?usuario=${currentUser.username}`);
                const data = await resp.json();
                alert('Datos sincronizados para la app:\n' + JSON.stringify(data, null, 2));
            }
        </script>
    </body>
    </html>
    """
