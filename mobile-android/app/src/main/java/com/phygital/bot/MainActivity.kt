package com.phygital.bot

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : Activity() {
    private val baseUrl = "https://whatsapp-bot-backend-v2.onrender.com"
    private val sessionPrefsName = "phygital_session"
    private val bridgePrefsName = "phygital_local_bridge"
    private var token: String? = null
    private var role: String? = null
    private var username: String? = null
    private var tokenInjected = false

    private lateinit var status: TextView
    private lateinit var loginPanel: LinearLayout
    private lateinit var actionsPanel: LinearLayout
    private lateinit var webView: WebView
    private lateinit var bridgeButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermissionIfNeeded()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }
        loginPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val usernameInput = EditText(this).apply { hint = "Usuario" }
        val passwordInput = EditText(this).apply { hint = "Contraseña"; inputType = 0x00000081 }
        val login = Button(this).apply { text = "Entrar" }
        loginPanel.addView(usernameInput)
        loginPanel.addView(passwordInput)
        loginPanel.addView(login)

        status = TextView(this).apply {
            text = "Inicia sesión para continuar."
            setPadding(0, 12, 0, 12)
        }
        actionsPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
        }
        bridgeButton = Button(this).apply { text = "Configurar WhatsApp local" }
        val dashboardButton = Button(this).apply { text = "Dashboard" }
        val logoutButton = Button(this).apply { text = "Salir" }
        actionsPanel.addView(bridgeButton)
        actionsPanel.addView(dashboardButton)
        actionsPanel.addView(logoutButton)

        webView = WebView(this).apply {
            visibility = View.GONE
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    val currentToken = token ?: return
                    if (!tokenInjected && url.startsWith(baseUrl)) {
                        tokenInjected = true
                        val quotedToken = JSONObject.quote(currentToken)
                        val quotedRole = JSONObject.quote(role ?: "")
                        view.evaluateJavascript(
                            "localStorage.setItem('phygital_token',$quotedToken);localStorage.setItem('phygital_role',$quotedRole);location.reload();",
                            null
                        )
                    }
                }
            }
        }

        root.addView(loginPanel)
        root.addView(status)
        root.addView(actionsPanel)
        root.addView(webView, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)

        login.setOnClickListener {
            val user = usernameInput.text.toString().trim()
            val password = passwordInput.text.toString()
            if (user.isBlank() || password.isBlank()) status.text = "Escribe usuario y contraseña."
            else login(user, password)
        }
        bridgeButton.setOnClickListener { configureBridge() }
        dashboardButton.setOnClickListener {
            tokenInjected = false
            webView.visibility = View.VISIBLE
            webView.loadUrl("$baseUrl/dashboard")
        }
        logoutButton.setOnClickListener { logout() }

        restoreSavedSession()
    }

    override fun onResume() {
        super.onResume()
        if (token != null) refreshBridgeStatus()
    }

    private fun login(userName: String, password: String) {
        status.text = "Iniciando sesión..."
        Thread {
            try {
                val body = JSONObject().put("username", userName).put("password", password).toString()
                val json = JSONObject(request("POST", "/api/auth/login", body, null))
                token = json.getString("access_token")
                role = json.optString("rol", "")
                username = json.optString("username", userName)
                saveSession()
                runOnUiThread { showAuthenticatedUi() }
            } catch (e: Exception) {
                runOnUiThread { status.text = "No se pudo iniciar sesión: ${e.message}" }
            }
        }.start()
    }

    private fun saveSession() {
        val currentToken = token ?: return
        getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit()
            .putString("token", currentToken)
            .putString("role", role ?: "")
            .putString("username", username ?: "")
            .apply()
    }

    private fun restoreSavedSession() {
        val prefs = getSharedPreferences(sessionPrefsName, MODE_PRIVATE)
        val savedToken = prefs.getString("token", null) ?: return
        token = savedToken
        role = prefs.getString("role", null)
        username = prefs.getString("username", null)
        showAuthenticatedUi()
        Thread {
            try {
                request("GET", "/api/stats", null, savedToken)
            } catch (e: Exception) {
                if ((e.message ?: "").contains("HTTP 401")) runOnUiThread { logout() }
            }
        }.start()
    }

    private fun showAuthenticatedUi() {
        loginPanel.visibility = View.GONE
        actionsPanel.visibility = View.VISIBLE
        refreshBridgeStatus()
    }

    private fun configureBridge() {
        val auth = token ?: return
        status.text = "Cargando tiendas..."
        Thread {
            try {
                val stores = JSONArray(request("GET", "/api/local-bridge/stores", null, auth))
                if (stores.length() == 0) {
                    runOnUiThread { status.text = "No hay tiendas activas configuradas en el dashboard." }
                    return@Thread
                }
                val labels = Array(stores.length()) { i ->
                    val row = stores.getJSONObject(i)
                    "${row.optString("company_name")} · ${row.optString("name")}"
                }
                runOnUiThread {
                    AlertDialog.Builder(this)
                        .setTitle("Selecciona la tienda de este teléfono")
                        .setSingleChoiceItems(labels, -1) { dialog, which ->
                            val row = stores.getJSONObject(which)
                            getSharedPreferences(bridgePrefsName, MODE_PRIVATE).edit()
                                .putInt("store_id", row.getInt("id"))
                                .putString("store_name", labels[which])
                                .putBoolean("enabled", true)
                                .apply()
                            dialog.dismiss()
                            requestNotificationListenerAccess()
                        }
                        .setNegativeButton("Cancelar", null)
                        .show()
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "No se pudieron cargar las tiendas: ${e.message}" }
            }
        }.start()
    }

    private fun requestNotificationListenerAccess() {
        if (hasNotificationListenerAccess()) {
            refreshBridgeStatus()
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Permitir lectura y respuesta")
            .setMessage("Android abrirá Acceso a notificaciones. Activa Phygital Bot. La app solo procesa notificaciones de WhatsApp y WhatsApp Business cuando el puente está habilitado.")
            .setPositiveButton("Abrir configuración") { _, _ ->
                startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            }
            .setNegativeButton("Después", null)
            .show()
    }

    private fun hasNotificationListenerAccess(): Boolean {
        val enabled = Settings.Secure.getString(contentResolver, "enabled_notification_listeners") ?: return false
        val component = ComponentName(this, LocalWhatsAppBridgeService::class.java).flattenToString()
        return enabled.split(":").any { it.equals(component, ignoreCase = true) }
    }

    private fun refreshBridgeStatus() {
        val prefs = getSharedPreferences(bridgePrefsName, MODE_PRIVATE)
        val enabled = prefs.getBoolean("enabled", false)
        val storeName = prefs.getString("store_name", null)
        val listener = hasNotificationListenerAccess()
        status.text = when {
            enabled && listener && !storeName.isNullOrBlank() -> "Puente local activo · $storeName · versión ${BuildConfig.VERSION_NAME}."
            enabled && !listener -> "Tienda configurada. Falta conceder Acceso a notificaciones a Phygital Bot."
            else -> "Sesión activa. Configura este teléfono para recibir y responder WhatsApp sin Meta API."
        }
        bridgeButton.text = if (enabled && listener) "Cambiar tienda / permisos" else "Configurar WhatsApp local"
    }

    private fun logout() {
        token = null
        role = null
        username = null
        getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit().clear().apply()
        tokenInjected = false
        webView.loadUrl("about:blank")
        webView.visibility = View.GONE
        actionsPanel.visibility = View.GONE
        loginPanel.visibility = View.VISIBLE
        status.text = "Sesión cerrada. El puente deja de enviar mensajes al backend hasta iniciar sesión nuevamente."
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2001)
        }
    }

    private fun request(method: String, path: String, body: String?, bearer: String?): String {
        val connection = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 20000
            readTimeout = 20000
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Accept", "application/json")
            if (bearer != null) setRequestProperty("Authorization", "Bearer $bearer")
            if (body != null) {
                doOutput = true
                outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
        connection.disconnect()
        if (code !in 200..299) throw IllegalStateException("HTTP $code $text")
        return text
    }
}
