from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=['dashboard-ui'])
UI_VERSION = '2026.08.17-3'

HTML = f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#101318">
  <link rel="manifest" href="/manifest.webmanifest">
  <title>Phygital Bot</title>
  <style>
    body{{font-family:system-ui;background:#0b0e12;color:#eef2f7;margin:0}}
    .w{{max-width:1180px;margin:auto;padding:16px}}
    .c{{background:#151a21;border:1px solid #26303b;border-radius:14px;padding:16px;margin:12px 0}}
    .g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
    .two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
    input,button,select,textarea{{box-sizing:border-box;width:100%;padding:11px;margin:5px 0;border-radius:9px;border:1px solid #354052;background:#0f141a;color:#eef2f7}}
    button{{cursor:pointer;background:#202936}}
    .nav{{display:flex;gap:8px;flex-wrap:wrap}}
    .nav button{{width:auto}}
    .h{{display:none}}
    .row{{padding:10px 0;border-bottom:1px solid #26303b}}
    .b{{display:inline-block;padding:3px 8px;background:#26303b;border-radius:999px;font-size:12px}}
    .muted{{color:#9ba8b6;font-size:13px}}
    textarea{{min-height:240px;font-family:monospace}}
    .danger{{background:#402020}}
    .error{{color:#ff9d9d;white-space:pre-wrap}}
    .ok{{color:#75d69c}}
  </style>
</head>
<body>
<div class="w">
  <section id="login" class="c">
    <h1>Phygital Bot</h1>
    <div class="muted">UI {UI_VERSION}</div>
    <input id="u" autocomplete="username" placeholder="Usuario">
    <input id="p" autocomplete="current-password" type="password" placeholder="Contraseña">
    <button id="loginBtn" type="button">Entrar</button>
    <div id="loginError" class="error"></div>
  </section>

  <section id="app" class="h">
    <h1>Dashboard</h1>
    <div class="muted">UI {UI_VERSION}</div>
    <div id="globalMsg" class="error"></div>
    <div id="stats" class="g"></div>
    <div class="c nav">
      <button id="navHelp" type="button">Solicitudes</button>
      <button id="navConv" type="button">Conversaciones</button>
      <button id="navContacts" type="button">Contactos</button>
      <button id="navCompanies" type="button">Empresas</button>
      <button id="navUsers" class="h" type="button">Usuarios</button>
      <button id="logoutBtn" type="button">Salir</button>
    </div>
    <div id="content" class="c"></div>
  </section>
</div>
<script src="/dashboard.js?v={UI_VERSION}"></script>
</body>
</html>'''

JS = r'''
(() => {
  const TOKEN_KEY = 'phygital_token';
  const ROLE_KEY = 'phygital_role';
  const $ = (id) => document.getElementById(id);
  const authHeaders = () => ({Authorization: 'Bearer ' + (localStorage.getItem(TOKEN_KEY) || '')});
  const isAdmin = () => localStorage.getItem(ROLE_KEY) === 'admin';
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const setGlobal = (text='') => { const el = $('globalMsg'); if (el) el.textContent = text; };
  const setLoginError = (text='') => { const el = $('loginError'); if (el) el.textContent = text; };

  window.addEventListener('error', (event) => {
    setLoginError('Error de interfaz: ' + (event.message || 'desconocido'));
    setGlobal('Error de interfaz: ' + (event.message || 'desconocido'));
  });

  window.addEventListener('unhandledrejection', (event) => {
    const msg = event.reason && event.reason.message ? event.reason.message : String(event.reason || 'Error inesperado');
    setLoginError('Error: ' + msg);
    setGlobal('Error: ' + msg);
  });

  async function api(path, options={}) {
    options.headers = {...(options.headers || {}), ...authHeaders()};
    const response = await fetch(path, options);
    if (response.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(ROLE_KEY);
      showLogin('Sesión expirada. Inicia sesión otra vez.');
      throw new Error('Sesión expirada');
    }
    if (!response.ok) {
      let detail = await response.text();
      try {
        const parsed = JSON.parse(detail);
        detail = parsed.detail || detail;
      } catch (_) {}
      throw new Error(detail || ('HTTP ' + response.status));
    }
    const contentType = response.headers.get('content-type') || '';
    return contentType.includes('application/json') ? response.json() : response.text();
  }

  function showLogin(message='') {
    $('app').classList.add('h');
    $('login').classList.remove('h');
    setLoginError(message);
  }

  async function login() {
    setLoginError('Conectando...');
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: $('u').value.trim(), password: $('p').value})
      });
      if (!response.ok) {
        let message = 'Credenciales incorrectas';
        try { const data = await response.json(); message = data.detail || message; } catch (_) {}
        setLoginError(message);
        return;
      }
      const data = await response.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(ROLE_KEY, data.rol);
      setLoginError('');
      await showDashboard();
    } catch (error) {
      setLoginError('No se pudo iniciar sesión: ' + error.message);
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
    location.reload();
  }

  async function showDashboard() {
    $('login').classList.add('h');
    $('app').classList.remove('h');
    $('navUsers').classList.toggle('h', !isAdmin());
    setGlobal('');
    try {
      const stats = await api('/api/stats');
      $('stats').innerHTML = Object.entries(stats).map(([key, value]) => `<div class="c"><b>${esc(value)}</b><div>${esc(key)}</div></div>`).join('');
      await showHelp();
    } catch (error) {
      setGlobal(error.message);
    }
  }

  async function showHelp() {
    setGlobal('');
    try {
      const rows = await api('/api/help-requests');
      $('content').innerHTML = '<h2>Solicitudes de ayuda</h2>' + rows.map((r) => `<div class="row"><b>${esc(r.company_name || 'Sin empresa')}</b> · ${esc(r.wa_user_id)}<div>${esc(r.body)}</div><span class="b">${r.known_contact ? 'contacto' : 'no agregado'}</span> <span class="b">${esc(r.status)}</span></div>`).join('');
    } catch (error) { setGlobal(error.message); }
  }

  async function showConversations(companyId=null) {
    setGlobal('');
    try {
      const suffix = companyId ? ('?company_id=' + encodeURIComponent(companyId)) : '';
      const rows = await api('/api/conversaciones' + suffix);
      $('content').innerHTML = '<h2>Conversaciones</h2>' + rows.map((r) => `<div class="row"><b>${esc(r.company_name || '')}</b> · ${esc(r.wa_user_id)} <span class="b">${r.known_contact ? 'contacto' : 'no agregado'}</span><div>${esc(r.state)} · ${esc(r.status)}</div></div>`).join('');
    } catch (error) { setGlobal(error.message); }
  }

  async function showContacts() {
    setGlobal('');
    try {
      const rows = await api('/api/contacts');
      $('content').innerHTML = '<h2>Contactos autorizados</h2><p class="muted">Solo aparecen los contactos que seleccionaste desde la app Android.</p>' + rows.map((r) => `<div class="row"><b>${esc(r.name || 'Sin nombre')}</b><div>${esc(r.phone)}</div></div>`).join('');
    } catch (error) { setGlobal(error.message); }
  }

  async function showUsers() {
    setGlobal('');
    try {
      const rows = await api('/api/auth/usuarios');
      $('content').innerHTML = `
        <h2>Usuarios</h2>
        <p class="muted">Solo el administrador principal puede gestionar usuarios. Los usuarios extra no pueden convertirse en administradores.</p>
        <div class="two">
          <div>
            <h3>Crear usuario</h3>
            <input id="nu" placeholder="Usuario">
            <input id="np" type="password" placeholder="Contraseña (mín. 8)">
            <select id="nr"><option value="operador">Operador</option><option value="lector">Lector</option></select>
            <button id="createUserBtn" type="button">Crear usuario</button>
          </div>
          <div>
            <h3>Usuarios existentes</h3>
            <div id="usersList"></div>
          </div>
        </div>`;
      $('usersList').innerHTML = rows.map((u) => `<div class="row" data-user-id="${u.id}"><b>${esc(u.username)}</b> <span class="b">${esc(u.role)}</span> ${u.is_primary_admin ? '<span class="b">administrador principal</span>' : ''}<div>${u.is_active ? 'Activo' : 'Desactivado'}</div>${u.is_primary_admin ? '' : `<button class="toggle-user" data-active="${u.is_active ? '0' : '1'}" type="button">${u.is_active ? 'Desactivar' : 'Activar'}</button><button class="reset-user" type="button">Cambiar contraseña</button>`}</div>`).join('');
      $('createUserBtn').addEventListener('click', async () => {
        try {
          await api('/api/auth/crear-usuario', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:$('nu').value.trim(), password:$('np').value, role:$('nr').value})});
          await showUsers();
        } catch (error) { setGlobal(error.message); }
      });
      document.querySelectorAll('.toggle-user').forEach((button) => button.addEventListener('click', async () => {
        const row = button.closest('[data-user-id]');
        try {
          await api('/api/auth/usuarios/' + row.dataset.userId, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({is_active:button.dataset.active === '1'})});
          await showUsers();
        } catch (error) { setGlobal(error.message); }
      }));
      document.querySelectorAll('.reset-user').forEach((button) => button.addEventListener('click', async () => {
        const row = button.closest('[data-user-id]');
        const password = prompt('Nueva contraseña (mínimo 8 caracteres)');
        if (!password) return;
        try {
          await api('/api/auth/usuarios/' + row.dataset.userId, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password})});
          alert('Contraseña actualizada');
        } catch (error) { setGlobal(error.message); }
      }));
    } catch (error) { setGlobal(error.message); }
  }

  async function showCompanies() {
    setGlobal('');
    try {
      const rows = await api('/api/empresas/listar');
      const createBlock = isAdmin() ? `<div><h3>Nueva empresa</h3><input id="ck" placeholder="Clave, ej. cliente_norte"><input id="cn" placeholder="Nombre"><button id="createCompanyBtn" type="button">Crear empresa</button></div>` : '';
      $('content').innerHTML = `<h2>Empresas</h2><div class="two">${createBlock}<div><h3>Administrar</h3><div id="companyList"></div></div></div>`;
      $('companyList').innerHTML = rows.map((c) => `<button class="company-open" data-key="${esc(c.empresa_id)}" type="button">${esc(c.nombre)}${c.activa ? '' : ' (inactiva)'}</button>`).join('');
      const createBtn = $('createCompanyBtn');
      if (createBtn) createBtn.addEventListener('click', async () => {
        try {
          await api('/api/empresas/crear', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({company_key:$('ck').value.trim(), name:$('cn').value.trim(), stores:[], whatsapp_numbers:[], phone_number_ids:[]})});
          await showCompanies();
        } catch (error) { setGlobal(error.message); }
      });
      document.querySelectorAll('.company-open').forEach((button) => button.addEventListener('click', () => showCompany(button.dataset.key)));
    } catch (error) { setGlobal(error.message); }
  }

  async function showCompany(key) {
    setGlobal('');
    try {
      const [companies, support, files, tree] = await Promise.all([
        api('/api/empresas/listar'),
        api('/api/empresas/' + encodeURIComponent(key) + '/soporte'),
        api('/api/empresas/' + encodeURIComponent(key) + '/archivos'),
        api('/api/empresas/' + encodeURIComponent(key) + '/arbol')
      ]);
      const company = companies.find((c) => c.empresa_id === key);
      if (!company) throw new Error('Empresa no encontrada');
      const adminControls = isAdmin() ? `
        <div class="c">
          <h3>Configuración</h3>
          <input id="ename" value="${esc(company.nombre)}">
          <button id="renameCompanyBtn" type="button">Guardar nombre</button>
          <button id="toggleCompanyBtn" class="danger" type="button">${company.activa ? 'Desactivar' : 'Activar'}</button>
          <p class="muted">Clave: ${esc(key)}</p>
        </div>
        <div class="c">
          <h3>Soporte y escalamiento</h3>
          <input id="sname" placeholder="Nombre">
          <input id="sphone" placeholder="Teléfono">
          <select id="srole"><option value="primary">Primario</option><option value="secondary">Secundario</option></select>
          <input id="smins" type="number" value="15" min="1">
          <button id="addSupportBtn" type="button">Agregar apoyo</button>
          <div id="supportList"></div>
        </div>` : '';
      $('content').innerHTML = `
        <button id="backCompaniesBtn" type="button">← Empresas</button>
        <h2>${esc(company.nombre)}</h2>
        <div class="two">${adminControls}</div>
        <div class="two">
          <div class="c">
            <h3>Árbol de decisiones</h3>
            <p class="muted">Editor JSON inicial.</p>
            <textarea id="treeEditor" ${isAdmin() ? '' : 'readonly'}>${esc(JSON.stringify(tree, null, 2))}</textarea>
            ${isAdmin() ? '<button id="saveTreeBtn" type="button">Guardar árbol</button>' : ''}
          </div>
          <div class="c">
            <h3>Archivos de la empresa</h3>
            ${isAdmin() ? '<input id="fdesc" placeholder="Descripción"><input id="fup" type="file"><button id="uploadFileBtn" type="button">Subir archivo</button>' : ''}
            <div id="filesList"></div>
          </div>
        </div>
        <div class="c"><h3>Chats por empresa</h3><button id="companyChatsBtn" type="button">Ver conversaciones de ${esc(company.nombre)}</button></div>`;

      if ($('supportList')) $('supportList').innerHTML = support.map((s) => `<div class="row" data-support-id="${s.id}"><b>${esc(s.name)}</b> ${esc(s.phone)} <span class="b">${esc(s.role)}</span><div>Escala tras ${esc(s.escalation_after_minutes)} min</div><button class="delete-support danger" type="button">Quitar</button></div>`).join('');
      $('filesList').innerHTML = files.map((f) => `<div class="row" data-file-id="${f.id}" data-file-name="${esc(f.filename)}"><b>${esc(f.filename)}</b><div>${Math.round((f.size_bytes || 0)/1024)} KB</div><button class="download-file" type="button">Descargar</button>${isAdmin() ? '<button class="delete-file danger" type="button">Eliminar</button>' : ''}</div>`).join('');

      $('backCompaniesBtn').addEventListener('click', showCompanies);
      $('companyChatsBtn').addEventListener('click', () => showConversations(company.id));

      if (isAdmin()) {
        $('renameCompanyBtn').addEventListener('click', async () => {
          try { await api('/api/empresas/' + encodeURIComponent(key), {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:$('ename').value})}); await showCompany(key); } catch (error) { setGlobal(error.message); }
        });
        $('toggleCompanyBtn').addEventListener('click', async () => {
          try { await api('/api/empresas/' + encodeURIComponent(key), {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({is_active:!company.activa})}); await showCompany(key); } catch (error) { setGlobal(error.message); }
        });
        $('addSupportBtn').addEventListener('click', async () => {
          try { await api('/api/empresas/' + encodeURIComponent(key) + '/soporte', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:$('sname').value, phone:$('sphone').value, role:$('srole').value, priority:1, escalation_after_minutes:Number($('smins').value || 15)})}); await showCompany(key); } catch (error) { setGlobal(error.message); }
        });
        $('saveTreeBtn').addEventListener('click', async () => {
          try { const structure = JSON.parse($('treeEditor').value); await api('/api/empresas/' + encodeURIComponent(key) + '/arbol', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({structure})}); alert('Árbol guardado'); } catch (error) { setGlobal('Árbol inválido o error: ' + error.message); }
        });
        $('uploadFileBtn').addEventListener('click', async () => {
          const file = $('fup').files[0];
          if (!file) { setGlobal('Selecciona un archivo'); return; }
          const data = new FormData();
          data.append('file', file);
          data.append('description', $('fdesc').value);
          try { await api('/api/empresas/' + encodeURIComponent(key) + '/archivos', {method:'POST', body:data}); await showCompany(key); } catch (error) { setGlobal(error.message); }
        });
        document.querySelectorAll('.delete-support').forEach((button) => button.addEventListener('click', async () => {
          const id = button.closest('[data-support-id]').dataset.supportId;
          try { await api('/api/empresas/' + encodeURIComponent(key) + '/soporte/' + id, {method:'DELETE'}); await showCompany(key); } catch (error) { setGlobal(error.message); }
        }));
        document.querySelectorAll('.delete-file').forEach((button) => button.addEventListener('click', async () => {
          const id = button.closest('[data-file-id]').dataset.fileId;
          try { await api('/api/empresas/' + encodeURIComponent(key) + '/archivos/' + id, {method:'DELETE'}); await showCompany(key); } catch (error) { setGlobal(error.message); }
        }));
      }

      document.querySelectorAll('.download-file').forEach((button) => button.addEventListener('click', async () => {
        const row = button.closest('[data-file-id]');
        try {
          const response = await fetch('/api/empresas/' + encodeURIComponent(key) + '/archivos/' + row.dataset.fileId + '/descargar', {headers:authHeaders()});
          if (!response.ok) throw new Error('No se pudo descargar');
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement('a');
          anchor.href = url;
          anchor.download = row.dataset.fileName || 'archivo';
          document.body.appendChild(anchor);
          anchor.click();
          anchor.remove();
          URL.revokeObjectURL(url);
        } catch (error) { setGlobal(error.message); }
      }));
    } catch (error) { setGlobal(error.message); }
  }

  document.addEventListener('DOMContentLoaded', () => {
    $('loginBtn').addEventListener('click', login);
    $('p').addEventListener('keydown', (event) => { if (event.key === 'Enter') login(); });
    $('navHelp').addEventListener('click', showHelp);
    $('navConv').addEventListener('click', () => showConversations());
    $('navContacts').addEventListener('click', showContacts);
    $('navCompanies').addEventListener('click', showCompanies);
    $('navUsers').addEventListener('click', showUsers);
    $('logoutBtn').addEventListener('click', logout);

    if (localStorage.getItem(TOKEN_KEY)) showDashboard();
  });
})();
'''


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard():
    return HTML


@router.get('/dashboard.js')
def dashboard_js():
    return Response(JS, media_type='application/javascript', headers={'Cache-Control': 'no-store'})


@router.get('/manifest.webmanifest')
def manifest():
    return {
        'name': 'Phygital Bot Dashboard',
        'short_name': 'Phygital Bot',
        'start_url': '/dashboard',
        'display': 'standalone',
        'background_color': '#0b0e12',
        'theme_color': '#101318',
    }


@router.get('/sw.js')
def sw():
    return Response("self.addEventListener('fetch',()=>{})", media_type='application/javascript', headers={'Cache-Control': 'no-store'})
