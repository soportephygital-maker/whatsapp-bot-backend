package com.phygital.bot

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
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
import androidx.core.content.FileProvider
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : Activity() {
    private val baseUrl = "https://whatsapp-bot-backend-v2.onrender.com"
    private val sessionPrefsName = "phygital_session"
    private val bridgePrefsName = "phygital_local_bridge"
    private val whatsappPackage = "com.whatsapp"
    private val whatsappBusinessPackage = "com.whatsapp.w4b"
    private var token: String? = null
    private var role: String? = null
    private var username: String? = null
    private var tokenInjected = false
    private var dashboardMode = false
    private var updatePromptVisible = false
    private var pendingUpdateFile: File? = null
    private var pendingBridgeConfiguration = false

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
        val updateButton = Button(this).apply { text = "Buscar actualización" }
        val logoutButton = Button(this).apply { text = "Salir" }
        actionsPanel.addView(bridgeButton)
        actionsPanel.addView(dashboardButton)
        actionsPanel.addView(updateButton)
        actionsPanel.addView(logoutButton)

        webView = WebView(this).apply {
            visibility = View.GONE
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.builtInZoomControls = false
            settings.displayZoomControls = false
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
        bridgeButton.setOnClickListener { ensureContactsPermissionAndConfigureBridge() }
        dashboardButton.setOnClickListener { openDashboard() }
        updateButton.setOnClickListener { checkForUpdate(true) }
        logoutButton.setOnClickListener { logout() }

        restoreSavedSession()
        checkForUpdate(false)
    }

    override fun onResume() {
        super.onResume()
        val file = pendingUpdateFile
        if (file != null && Build.VERSION.SDK_INT >= 26 && packageManager.canRequestPackageInstalls()) {
            pendingUpdateFile = null
            installApk(file)
            return
        }
        if (token != null && !dashboardMode) refreshBridgeStatus()
        checkForUpdate(false)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (dashboardMode) {
            if (webView.canGoBack()) webView.goBack() else closeDashboard()
        } else {
            super.onBackPressed()
        }
    }

    private fun openDashboard() {
        dashboardMode = true
        tokenInjected = false
        status.visibility = View.GONE
        actionsPanel.visibility = View.GONE
        webView.visibility = View.VISIBLE
        webView.loadUrl("$baseUrl/dashboard")
    }

    private fun closeDashboard() {
        dashboardMode = false
        webView.loadUrl("about:blank")
        webView.visibility = View.GONE
        status.visibility = View.VISIBLE
        actionsPanel.visibility = View.VISIBLE
        refreshBridgeStatus()
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
                checkForUpdate(false)
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
        status.visibility = View.VISIBLE
        actionsPanel.visibility = View.VISIBLE
        refreshBridgeStatus()
    }

    private fun checkForUpdate(showIfCurrent: Boolean) {
        Thread {
            try {
                val json = JSONObject(request("GET", "/api/mobile/update", null, null))
                val published = json.optBoolean("published", false)
                val latestCode = json.optInt("version_code", 0)
                val latestName = json.optString("version_name", "")
                val apkUrl = json.optString("apk_url", "")
                val message = json.optString("message", "Hay una actualización disponible para Phygital Bot.")
                if (published && latestCode > BuildConfig.VERSION_CODE && apkUrl.isNotBlank()) {
                    runOnUiThread { showUpdatePrompt(latestName, message, apkUrl) }
                } else if (showIfCurrent) {
                    runOnUiThread { status.text = "La app está actualizada (${BuildConfig.VERSION_NAME})." }
                }
            } catch (e: Exception) {
                if (showIfCurrent) runOnUiThread { status.text = "No se pudo consultar actualizaciones: ${e.message}" }
            }
        }.start()
    }

    private fun showUpdatePrompt(versionName: String, message: String, apkUrl: String) {
        if (updatePromptVisible || isFinishing) return
        updatePromptVisible = true
        AlertDialog.Builder(this)
            .setTitle("Actualización disponible${if (versionName.isNotBlank()) " · $versionName" else ""}")
            .setMessage(message)
            .setNegativeButton("Después") { _, _ -> updatePromptVisible = false }
            .setPositiveButton("Instalar actualización") { _, _ ->
                updatePromptVisible = false
                downloadAndInstallUpdate(apkUrl)
            }
            .setOnCancelListener { updatePromptVisible = false }
            .show()
    }

    private fun downloadAndInstallUpdate(apkUrl: String) {
        status.text = "Descargando actualización..."
        Thread {
            try {
                val dir = File(cacheDir, "updates").apply { mkdirs() }
                val apk = File(dir, "phygital-bot-update.apk")
                val connection = (URL(apkUrl).openConnection() as HttpURLConnection).apply {
                    connectTimeout = 20000
                    readTimeout = 60000
                    instanceFollowRedirects = true
                    setRequestProperty("User-Agent", "Phygital-Bot-Android")
                }
                connection.inputStream.use { input -> apk.outputStream().use { output -> input.copyTo(output) } }
                connection.disconnect()
                runOnUiThread {
                    status.text = "Actualización descargada. Confirma la instalación en Android."
                    requestInstallOrOpen(apk)
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "No se pudo descargar la actualización: ${e.message}" }
            }
        }.start()
    }

    private fun requestInstallOrOpen(apk: File) {
        if (Build.VERSION.SDK_INT >= 26 && !packageManager.canRequestPackageInstalls()) {
            pendingUpdateFile = apk
            AlertDialog.Builder(this)
                .setTitle("Permitir actualizaciones")
                .setMessage("Android necesita autorizar a Phygital Bot para instalar sus propias actualizaciones. Activa 'Permitir de esta fuente' y regresa a la app.")
                .setPositiveButton("Abrir configuración") { _, _ ->
                    startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
                }
                .setNegativeButton("Cancelar", null)
                .show()
            return
        }
        installApk(apk)
    }

    private fun installApk(apk: File) {
        val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", apk)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        startActivity(intent)
    }

    private fun ensureContactsPermissionAndConfigureBridge() {
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) {
            configureBridge()
            return
        }
        pendingBridgeConfiguration = true
        AlertDialog.Builder(this)
            .setTitle("Filtrar contactos guardados")
            .setMessage("Para que el bot ignore a todas las personas que ya tienes agregadas, Android debe permitir a Phygital Bot leer la agenda. Sin este permiso el puente permanecerá bloqueado por seguridad.")
            .setPositiveButton("Permitir") { _, _ -> requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), 3001) }
            .setNegativeButton("Cancelar") { _, _ -> pendingBridgeConfiguration = false }
            .show()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 3001) {
            val allowed = grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
            if (allowed && pendingBridgeConfiguration) configureBridge()
            else status.text = "El puente no se activará hasta permitir acceso a Contactos; así evitamos responder a personas ya guardadas."
            pendingBridgeConfiguration = false
        }
    }

    private fun configureBridge() {
        val auth = token ?: return
        status.text = "Cargando tiendas..."
        Thread {
            try {
                val stores = JSONArray(request("GET", "/api/local-bridge/stores", null, auth))
                if (stores.length() == 0) {
                    runOnUiThread { status.text = "No hay tiendas configuradas. Abre Dashboard > Empresas y agrega una tienda." }
                    return@Thread
                }
                runOnUiThread { chooseWhatsAppApplication(stores) }
            } catch (e: Exception) {
                runOnUiThread { status.text = "No se pudieron cargar las tiendas: ${e.message}" }
            }
        }.start()
    }

    private fun chooseWhatsAppApplication(stores: JSONArray) {
        val options = arrayOf("WhatsApp", "WhatsApp Business")
        AlertDialog.Builder(this)
            .setTitle("¿Qué aplicación quieres configurar?")
            .setItems(options) { _, which ->
                val packageName = if (which == 0) whatsappPackage else whatsappBusinessPackage
                val label = options[which]
                chooseStoreForApplication(stores, packageName, label)
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun chooseStoreForApplication(stores: JSONArray, packageName: String, appLabel: String) {
        val labels = Array(stores.length()) { i ->
            val row = stores.getJSONObject(i)
            "${row.optString("company_name")} · ${row.optString("name")}"
        }
        AlertDialog.Builder(this)
            .setTitle("Tienda para $appLabel")
            .setSingleChoiceItems(labels, -1) { dialog, which ->
                val row = stores.getJSONObject(which)
                val suffix = packageSuffix(packageName)
                getSharedPreferences(bridgePrefsName, MODE_PRIVATE).edit()
                    .putInt("store_id_$suffix", row.getInt("id"))
                    .putString("store_name_$suffix", labels[which])
                    .putBoolean("enabled_$suffix", true)
                    .apply()
                dialog.dismiss()
                refreshBridgeStatus()
                requestNotificationListenerAccess()
                AlertDialog.Builder(this)
                    .setTitle("Configuración guardada")
                    .setMessage("$appLabel quedó asignado a ${labels[which]}. Puedes volver a Configurar WhatsApp local para asignar otra tienda a la otra aplicación.")
                    .setPositiveButton("Aceptar", null)
                    .show()
            }
            .setNeutralButton("Desactivar $appLabel") { _, _ ->
                val suffix = packageSuffix(packageName)
                getSharedPreferences(bridgePrefsName, MODE_PRIVATE).edit()
                    .putBoolean("enabled_$suffix", false)
                    .remove("store_id_$suffix")
                    .remove("store_name_$suffix")
                    .apply()
                refreshBridgeStatus()
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun packageSuffix(packageName: String): String = packageName.replace('.', '_')

    private fun requestNotificationListenerAccess() {
        if (hasNotificationListenerAccess()) {
            refreshBridgeStatus()
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Permitir lectura y respuesta")
            .setMessage("Android abrirá Acceso a notificaciones. Activa Phygital Bot. El puente ignorará chats grupales y contactos guardados, y procesará solo la aplicación que hayas asignado a una tienda.")
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
        val listener = hasNotificationListenerAccess()
        val waEnabled = prefs.getBoolean("enabled_${packageSuffix(whatsappPackage)}", false)
        val wbEnabled = prefs.getBoolean("enabled_${packageSuffix(whatsappBusinessPackage)}", false)
        val waStore = prefs.getString("store_name_${packageSuffix(whatsappPackage)}", null)
        val wbStore = prefs.getString("store_name_${packageSuffix(whatsappBusinessPackage)}", null)
        val configured = mutableListOf<String>()
        if (waEnabled && !waStore.isNullOrBlank()) configured.add("WhatsApp → $waStore")
        if (wbEnabled && !wbStore.isNullOrBlank()) configured.add("Business → $wbStore")
        status.text = when {
            configured.isNotEmpty() && listener -> "Puente activo · ${configured.joinToString(" | ")} · versión ${BuildConfig.VERSION_NAME}."
            configured.isNotEmpty() -> "${configured.joinToString(" | ")}. Falta conceder Acceso a notificaciones."
            else -> "Sesión activa. Configura WhatsApp y/o WhatsApp Business por tienda. Grupos y contactos guardados serán ignorados."
        }
        bridgeButton.text = if (configured.isNotEmpty()) "Cambiar tiendas / aplicaciones" else "Configurar WhatsApp local"
    }

    private fun logout() {
        dashboardMode = false
        token = null
        role = null
        username = null
        getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit().clear().apply()
        tokenInjected = false
        webView.loadUrl("about:blank")
        webView.visibility = View.GONE
        actionsPanel.visibility = View.GONE
        status.visibility = View.VISIBLE
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
