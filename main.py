from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timezone
import os
import shutil

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

USUARIOS_DB = {
    "ZoeOrtiz": {
        "password": "25052002",
        "rol": "admin",
        "empresas_autorizadas": ["todas"],
        "permisos": ["crear_usuarios", "crear_empresas", "modificar_arbol", "eliminar_historial", "responder_soporte"]
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
CONVERSACIONES: Dict[str, Dict] = {}
COLA_APP_ADMIN: List[Dict] = []
NEXT_QUEUE_ID = 1
APARIENCIA = {
    "background_color": "#0d1117",
    "card_color": "#161b22",
    "text_color": "#c9d1d9",
    "primary_color": "#238636",
    "accent_color": "#58a6ff",
    "background_image": "",
    "logo_url": "",
    "header_text": "Panel Phygital - Gestión Multi-Empresa"
}


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def conversacion(numero: str):
    if numero not in CONVERSACIONES:
        CONVERSACIONES[numero] = {
            "numero": numero,
            "modo": "bot",
            "operador": None,
            "actualizado": ahora_iso(),
            "mensajes": []
        }
    return CONVERSACIONES[numero]


def agregar_mensaje(numero: str, origen: str, texto: str, operador: Optional[str] = None):
    c = conversacion(numero)
    c["mensajes"].append({
        "origen": origen,
        "texto": texto,
        "operador": operador,
        "fecha": ahora_iso()
    })
    c["actualizado"] = ahora_iso()
    return c


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


class IncomingMessage(BaseModel):
    numero: str
    mensaje: str
    empresa_id: Optional[str] = "empresa_demo"


class HumanReply(BaseModel):
    numero: str
    mensaje: str
    operador: str = "ZoeOrtiz"


class ConversationMode(BaseModel):
    numero: str
    operador: Optional[str] = "ZoeOrtiz"


class BridgeAck(BaseModel):
    queue_id: int
    status: str = "sent"
    detail: Optional[str] = None


class AppearanceModel(BaseModel):
    background_color: str
    card_color: str
    text_color: str
    primary_color: str
    accent_color: str
    background_image: Optional[str] = ""
    logo_url: Optional[str] = ""
    header_text: Optional[str] = "Panel Phygital - Gestión Multi-Empresa"


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


@app.get("/api/app/sync-tienda")
def sync_app_movil(usuario: str):
    u = USUARIOS_DB.get(usuario)
    if not u:
        raise HTTPException(status_code=401, detail="Sesión no válida")
    empresas_permitidas = EMPRESAS_DB if u["rol"] == "admin" else {k: v for k, v in EMPRESAS_DB.items() if k in u["empresas_autorizadas"]}
    return {
        "usuario": usuario,
        "rol": u["rol"],
        "empresas_asignadas": empresas_permitidas,
        "bridge": {
            "pending_url": "/api/app/bridge/pending",
            "ack_url": "/api/app/bridge/ack",
            "incoming_url": "/api/chat/incoming"
        }
    }


@app.post("/api/chat/incoming")
def mensaje_entrante(data: IncomingMessage):
    c = agregar_mensaje(data.numero, "cliente", data.mensaje)
    if c["modo"] == "humano":
        return {
            "status": "ok",
            "bot_debe_responder": False,
            "motivo": "conversacion_en_atencion_humana",
            "modo": "humano"
        }
    return {
        "status": "ok",
        "bot_debe_responder": True,
        "modo": "bot",
        "empresa_id": data.empresa_id
    }


@app.get("/api/conversaciones")
def listar_conversaciones():
    return sorted(CONVERSACIONES.values(), key=lambda x: x.get("actualizado", ""), reverse=True)


@app.get("/api/conversaciones/{numero}")
def obtener_conversacion(numero: str):
    return conversacion(numero)


@app.post("/api/conversaciones/tomar")
def tomar_conversacion(data: ConversationMode):
    c = conversacion(data.numero)
    c["modo"] = "humano"
    c["operador"] = data.operador
    c["actualizado"] = ahora_iso()
    return {"status": "ok", "modo": "humano", "numero": data.numero, "operador": data.operador}


@app.post("/api/conversaciones/reactivar-bot")
def reactivar_bot(data: ConversationMode):
    c = conversacion(data.numero)
    c["modo"] = "bot"
    c["operador"] = None
    c["actualizado"] = ahora_iso()
    return {"status": "ok", "modo": "bot", "numero": data.numero}


@app.post("/api/conversaciones/responder")
def responder_desde_dashboard(data: HumanReply):
    global NEXT_QUEUE_ID
    if not data.mensaje.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
    c = conversacion(data.numero)
    c["modo"] = "humano"
    c["operador"] = data.operador
    agregar_mensaje(data.numero, "humano", data.mensaje.strip(), data.operador)
    item = {
        "id": NEXT_QUEUE_ID,
        "numero": data.numero,
        "mensaje": data.mensaje.strip(),
        "operador": data.operador,
        "status": "pending",
        "creado": ahora_iso(),
        "actualizado": ahora_iso(),
        "detail": None
    }
    NEXT_QUEUE_ID += 1
    COLA_APP_ADMIN.append(item)
    return {
        "status": "queued",
        "queue_id": item["id"],
        "modo": "humano",
        "mensaje": "Respuesta enviada a la cola de la app administradora"
    }


@app.get("/api/app/bridge/pending")
def bridge_pending(usuario: str = "ZoeOrtiz"):
    if usuario not in USUARIOS_DB:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    return [x for x in COLA_APP_ADMIN if x["status"] == "pending"]


@app.post("/api/app/bridge/ack")
def bridge_ack(data: BridgeAck):
    for item in COLA_APP_ADMIN:
        if item["id"] == data.queue_id:
            item["status"] = data.status
            item["detail"] = data.detail
            item["actualizado"] = ahora_iso()
            return {"status": "ok", "queue_id": item["id"], "delivery_status": item["status"]}
    raise HTTPException(status_code=404, detail="Mensaje de cola no encontrado")


@app.get("/api/app/bridge/history")
def bridge_history():
    return list(reversed(COLA_APP_ADMIN[-200:]))


@app.get("/api/apariencia")
def obtener_apariencia():
    return APARIENCIA


@app.post("/api/apariencia")
def guardar_apariencia(data: AppearanceModel, usuario: str = "ZoeOrtiz"):
    if USUARIOS_DB.get(usuario, {}).get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden cambiar la apariencia")
    APARIENCIA.update(data.model_dump())
    return {"status": "ok", "apariencia": APARIENCIA}


@app.get("/api/stats")
def obtener_stats():
    return {
        "total_respuestas": METRICAS["total_respuestas"],
        "conversaciones": len(CONVERSACIONES),
        "en_atencion_humana": sum(1 for x in CONVERSACIONES.values() if x["modo"] == "humano"),
        "mensajes_pendientes_app": sum(1 for x in COLA_APP_ADMIN if x["status"] == "pending")
    }


@app.post("/api/archivos/subir")
def subir_archivo(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename)
    file_location = f"uploads/{safe_name}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": safe_name, "url": f"/files/{safe_name}"}


@app.get("/", response_class=HTMLResponse)
def dashboard_ui():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Phygital Admin</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--text:#c9d1d9;--primary:#238636;--accent:#58a6ff}
*{box-sizing:border-box;font-family:Segoe UI,Roboto,sans-serif}body{margin:0;background:var(--bg);color:var(--text);background-size:cover;background-attachment:fixed}.hidden{display:none!important}
#loginSection{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}.login-card,.card{background:color-mix(in srgb,var(--card) 94%,transparent);border:1px solid #30363d;border-radius:14px;padding:20px}.login-card{width:min(380px,100%)}
input,select,textarea{width:100%;padding:11px;margin:6px 0 12px;border-radius:8px;border:1px solid #30363d;background:#0d1117;color:white}button{padding:10px 14px;background:var(--primary);color:#fff;border:0;border-radius:8px;cursor:pointer;font-weight:700}button.secondary{background:#30363d}button.danger{background:#b42318}.app{max-width:1450px;margin:auto;padding:18px}.top{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:16px}.top h1{margin:0;font-size:22px;color:var(--accent)}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}.tabs button{background:#21262d}.tabs button.active{background:var(--primary)}.grid{display:grid;grid-template-columns:340px 1fr;gap:16px}.list{max-height:620px;overflow:auto}.conv{padding:12px;border-bottom:1px solid #30363d;cursor:pointer}.conv:hover,.conv.active{background:#21262d}.badge{display:inline-block;padding:3px 8px;border-radius:99px;font-size:12px;background:#30363d}.badge.humano{background:#7a271a}.badge.bot{background:#175cd3}.chat{min-height:480px;display:flex;flex-direction:column}.messages{flex:1;min-height:330px;max-height:500px;overflow:auto;padding:8px}.msg{max-width:75%;padding:9px 12px;border-radius:12px;margin:8px 0;background:#21262d}.msg.humano{margin-left:auto;background:#174a2b}.msg.cliente{margin-right:auto}.composer{border-top:1px solid #30363d;padding-top:12px}.row{display:flex;gap:8px;flex-wrap:wrap}.row>*{flex:1}.statusline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.settings{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.colorinput{height:44px;padding:3px}.muted{color:#8b949e;font-size:13px}.empty{padding:30px;text-align:center;color:#8b949e}@media(max-width:800px){.grid{grid-template-columns:1fr}.list{max-height:300px}.msg{max-width:90%}}
</style>
</head>
<body>
<section id="loginSection"><div class="login-card"><h2>Phygital Admin</h2><input id="userInput" placeholder="Usuario"><input id="passInput" type="password" placeholder="Contraseña"><button id="loginBtn" style="width:100%">Iniciar sesión</button><p id="errorMsg" class="muted"></p></div></section>
<section id="dashboardSection" class="hidden"><div class="app"><div class="top"><div><h1 id="headerTitle">Panel Phygital</h1><div id="userInfo" class="muted"></div></div><div id="logoWrap"></div></div><div class="tabs"><button class="active" data-tab="chatTab">Conversaciones</button><button data-tab="settingsTab">Apariencia</button><button data-tab="adminTab">Administración</button></div>
<div id="chatTab"><div class="grid"><div class="card"><h3>Conversaciones</h3><div id="conversationList" class="list"><div class="empty">Sin conversaciones todavía.</div></div></div><div class="card chat"><div id="chatEmpty" class="empty">Selecciona una conversación.</div><div id="chatContent" class="hidden"><div class="statusline"><strong id="chatNumber"></strong><span id="modeBadge" class="badge"></span><button id="takeBtn" class="secondary">Tomar conversación</button><button id="botBtn">Reactivar bot</button></div><div id="messages" class="messages"></div><div class="composer"><textarea id="replyText" rows="3" placeholder="Escribe una respuesta para enviar mediante la app administradora..."></textarea><div class="row"><button id="sendBtn">Enviar respuesta</button><button id="refreshBtn" class="secondary">Actualizar</button></div><div id="sendStatus" class="muted"></div></div></div></div></div></div>
<div id="settingsTab" class="hidden"><div class="card"><h3>Apariencia del dashboard</h3><div class="settings"><label>Fondo<input id="bgColor" type="color" class="colorinput"></label><label>Tarjetas<input id="cardColor" type="color" class="colorinput"></label><label>Texto<input id="textColor" type="color" class="colorinput"></label><label>Color principal<input id="primaryColor" type="color" class="colorinput"></label><label>Color de acento<input id="accentColor" type="color" class="colorinput"></label><label>Imagen de fondo (URL)<input id="backgroundImage" placeholder="https://..."></label><label>Logo (URL)<input id="logoUrl" placeholder="https://..."></label><label>Texto de encabezado<input id="headerText"></label></div><div class="row"><button id="saveAppearance">Guardar apariencia</button><button id="resetAppearance" class="secondary">Restablecer</button></div><p class="muted">También puedes usar archivos subidos en /files/ como fondo o logo.</p></div></div>
<div id="adminTab" class="hidden"><div class="settings"><div class="card"><h3>Puente App Administradora</h3><p class="muted">La app debe consultar mensajes pendientes y confirmar cada envío.</p><code>/api/app/bridge/pending</code><br><code>/api/app/bridge/ack</code><br><code>/api/chat/incoming</code></div><div class="card"><h3>Estado</h3><div id="statsBox" class="muted">Cargando...</div><button id="statsBtn" class="secondary">Actualizar estado</button></div></div></div>
</div></section>
<script>
let currentUser=null,currentNumber=null;
const $=id=>document.getElementById(id);
async function api(url,opt={}){const r=await fetch(url,opt);let d={};try{d=await r.json()}catch(e){}if(!r.ok)throw new Error(d.detail||'Error de servidor');return d}
function post(url,data){return api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})}
function esc(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
async function login(){try{currentUser=await post('/api/auth/login',{username:$('userInput').value,password:$('passInput').value});$('loginSection').classList.add('hidden');$('dashboardSection').classList.remove('hidden');$('userInfo').textContent=currentUser.username+' ('+currentUser.rol+')';await loadAppearance();await loadConversations();await loadStats()}catch(e){$('errorMsg').textContent=e.message}}
async function loadConversations(){const list=await api('/api/conversaciones');const box=$('conversationList');if(!list.length){box.innerHTML='<div class="empty">Sin conversaciones todavía.</div>';return}box.innerHTML=list.map(c=>`<div class="conv ${c.numero===currentNumber?'active':''}" data-num="${esc(c.numero)}"><strong>${esc(c.numero)}</strong><br><span class="badge ${c.modo}">${c.modo==='humano'?'Atención humana':'Bot activo'}</span><div class="muted">${c.mensajes.length} mensajes</div></div>`).join('');box.querySelectorAll('.conv').forEach(el=>el.addEventListener('click',()=>openConversation(el.dataset.num)))}
async function openConversation(num){currentNumber=num;const c=await api('/api/conversaciones/'+encodeURIComponent(num));$('chatEmpty').classList.add('hidden');$('chatContent').classList.remove('hidden');$('chatNumber').textContent=c.numero;const b=$('modeBadge');b.className='badge '+c.modo;b.textContent=c.modo==='humano'?'Atención humana':'Bot activo';$('takeBtn').classList.toggle('hidden',c.modo==='humano');$('botBtn').classList.toggle('hidden',c.modo==='bot');$('messages').innerHTML=c.mensajes.map(m=>`<div class="msg ${esc(m.origen)}"><div>${esc(m.texto)}</div><div class="muted">${esc(m.operador||m.origen)} · ${new Date(m.fecha).toLocaleString()}</div></div>`).join('');$('messages').scrollTop=$('messages').scrollHeight;await loadConversations()}
async function take(){if(!currentNumber)return;await post('/api/conversaciones/tomar',{numero:currentNumber,operador:currentUser.username});await openConversation(currentNumber)}
async function reactivate(){if(!currentNumber)return;await post('/api/conversaciones/reactivar-bot',{numero:currentNumber,operador:currentUser.username});await openConversation(currentNumber)}
async function sendReply(){if(!currentNumber)return;const t=$('replyText').value.trim();if(!t)return;try{const d=await post('/api/conversaciones/responder',{numero:currentNumber,mensaje:t,operador:currentUser.username});$('replyText').value='';$('sendStatus').textContent='En cola para la app administradora. ID '+d.queue_id;await openConversation(currentNumber);await loadStats()}catch(e){$('sendStatus').textContent=e.message}}
function applyAppearance(a){document.documentElement.style.setProperty('--bg',a.background_color);document.documentElement.style.setProperty('--card',a.card_color);document.documentElement.style.setProperty('--text',a.text_color);document.documentElement.style.setProperty('--primary',a.primary_color);document.documentElement.style.setProperty('--accent',a.accent_color);document.body.style.backgroundImage=a.background_image?`url("${a.background_image.replace(/"/g,'')}")`:'none';$('headerTitle').textContent=a.header_text||'Panel Phygital';$('logoWrap').innerHTML=a.logo_url?`<img src="${esc(a.logo_url)}" alt="Logo" style="max-height:52px;max-width:180px">`:''}
async function loadAppearance(){const a=await api('/api/apariencia');applyAppearance(a);$('bgColor').value=a.background_color;$('cardColor').value=a.card_color;$('textColor').value=a.text_color;$('primaryColor').value=a.primary_color;$('accentColor').value=a.accent_color;$('backgroundImage').value=a.background_image||'';$('logoUrl').value=a.logo_url||'';$('headerText').value=a.header_text||''}
async function saveAppearance(){const a={background_color:$('bgColor').value,card_color:$('cardColor').value,text_color:$('textColor').value,primary_color:$('primaryColor').value,accent_color:$('accentColor').value,background_image:$('backgroundImage').value.trim(),logo_url:$('logoUrl').value.trim(),header_text:$('headerText').value.trim()};const d=await post('/api/apariencia?usuario='+encodeURIComponent(currentUser.username),a);applyAppearance(d.apariencia)}
async function resetAppearance(){const a={background_color:'#0d1117',card_color:'#161b22',text_color:'#c9d1d9',primary_color:'#238636',accent_color:'#58a6ff',background_image:'',logo_url:'',header_text:'Panel Phygital - Gestión Multi-Empresa'};const d=await post('/api/apariencia?usuario='+encodeURIComponent(currentUser.username),a);applyAppearance(d.apariencia);await loadAppearance()}
async function loadStats(){const s=await api('/api/stats');$('statsBox').innerHTML=`Conversaciones: <b>${s.conversaciones}</b><br>Atención humana: <b>${s.en_atencion_humana}</b><br>Pendientes app: <b>${s.mensajes_pendientes_app}</b>`}
$('loginBtn').addEventListener('click',login);$('takeBtn').addEventListener('click',take);$('botBtn').addEventListener('click',reactivate);$('sendBtn').addEventListener('click',sendReply);$('refreshBtn').addEventListener('click',()=>currentNumber?openConversation(currentNumber):loadConversations());$('saveAppearance').addEventListener('click',saveAppearance);$('resetAppearance').addEventListener('click',resetAppearance);$('statsBtn').addEventListener('click',loadStats);document.querySelectorAll('.tabs button').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));btn.classList.add('active');['chatTab','settingsTab','adminTab'].forEach(id=>$(id).classList.add('hidden'));$(btn.dataset.tab).classList.remove('hidden')}));
setInterval(()=>{if(currentUser){loadConversations();if(currentNumber)openConversation(currentNumber);}},5000);
</script>
</body>
</html>
""")
