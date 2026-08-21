package com.phygital.bot

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
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
    private val notificationPrefsName = "phygital_notifications"
    private val notificationChannelId = "phygital_support_alerts"
    private val whatsappPackage = "com.whatsapp"
    private val whatsappBusinessPackage = "com.whatsapp.w4b"

    private var token: String? = null
    private var role: String? = null
    private var username: String? = null
    private var tokenInjected = false
    private var dashboardMode = false
    private var updatePromptVisible = false
    private var pendingUpdateFile: File? = null
    private var pendingAppMenu = false
    @Volatile private var notificationPolling = false

    private lateinit var status: TextView
    private lateinit var loginPanel: LinearLayout
    private lateinit var actionsPanel: LinearLayout
    private lateinit var webView: WebView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createNotificationChannel()
        requestNotificationPermissionIfNeeded()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }
        loginPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val usernameInput = EditText(this).apply { hint = "Usuario" }
        val passwordInput = EditText(this).apply { hint = "Contraseña"; inputType = 0x00000081 }
        val loginButton = Button(this).apply { text = "Entrar" }
        loginPanel.addView(usernameInput)
        loginPanel.addView(passwordInput)
        loginPanel.addView(loginButton)

        status = TextView(this).apply {
            text = "Inicia sesión para continuar."
            setPadding(0, 12, 0, 12)
        }
        actionsPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
        }

        val storesButton = Button(this).apply { text = "1. Seleccionar tiendas" }
        val appsButton = Button(this).apply { text = "2. Aplicaciones WhatsApp" }
        val dashboardButton = Button(this).apply { text = "3. Dashboard" }
        val updateButton = Button(this).apply { text = "4. Buscar actualización" }
        val permissionsButton = Button(this).apply { text = "5. Permisos del puente" }
        val treeButton = Button(this).apply { text = "6. Árbol de decisiones" }
        val logoutButton = Button(this).apply { text = "Salir" }
        actionsPanel.addView(storesButton)
        actionsPanel.addView(appsButton)
        actionsPanel.addView(dashboardButton)
        actionsPanel.addView(updateButton)
        actionsPanel.addView(permissionsButton)
        actionsPanel.addView(treeButton)
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

        loginButton.setOnClickListener {
            val user = usernameInput.text.toString().trim()
            val password = passwordInput.text.toString()
            if (user.isBlank() || password.isBlank()) status.text = "Escribe usuario y contraseña."
            else login(user, password)
        }
        storesButton.setOnClickListener { selectStores() }
        appsButton.setOnClickListener { ensureContactsPermissionAndOpenApps() }
        dashboardButton.setOnClickListener { openDashboard("") }
        updateButton.setOnClickListener { checkForUpdate(true) }
        permissionsButton.setOnClickListener { requestNotificationListenerAccess() }
        treeButton.setOnClickListener { openDashboard("#arbol") }
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
        } else super.onBackPressed()
    }

    private fun openDashboard(hash: String) {
        dashboardMode = true
        tokenInjected = false
        status.visibility = View.GONE
        actionsPanel.visibility = View.GONE
        webView.visibility = View.VISIBLE
        webView.loadUrl("$baseUrl/dashboard$hash")
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
                startNotificationPolling()
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
                startNotificationPolling()
            } catch (e: Exception) {
                if ((e.message ?: "").contains("HTTP 401")) runOnUiThread { logout() }
                else startNotificationPolling()
            }
        }.start()
    }

    private fun showAuthenticatedUi() {
        loginPanel.visibility = View.GONE
        status.visibility = View.VISIBLE
        actionsPanel.visibility = View.VISIBLE
        refreshBridgeStatus()
    }

    private fun selectStores() {
        val auth = token ?: return
        status.text = "Cargando tiendas..."
        Thread {
            try {
                val stores = JSONArray(request("GET", "/api/local-bridge/stores", null, auth))
                if (stores.length() == 0) {
                    runOnUiThread { status.text = "No hay tiendas configuradas. Agrégalas desde Dashboard > Empresas." }
                    return@Thread
                }
                val labels = Array(stores.length()) { i ->
                    val row = stores.getJSONObject(i)
                    "${row.optString("company_name")} · ${row.optString("name")}"
                }
                val ids = Array(stores.length()) { i -> stores.getJSONObject(i).getInt("id").toString() }
                val prefs = getSharedPreferences(bridgePrefsName, MODE_PRIVATE)
                val selected = prefs.getStringSet("selected_store_ids", emptySet()) ?: emptySet()
                val checked = BooleanArray(stores.length()) { i -> selected.contains(ids[i]) }
                runOnUiThread {
                    AlertDialog.Builder(this)
                        .setTitle("Selecciona una o más tiendas")
                        .setMultiChoiceItems(labels, checked) { _, which, isChecked -> checked[which] = isChecked }
                        .setPositiveButton("Guardar") { _, _ ->
                            val selectedIds = mutableSetOf<String>()
                            val selectedLabels = mutableListOf<String>()
                            checked.forEachIndexed { index, yes ->
                                if (yes) {
                                    selectedIds.add(ids[index])
                                    selectedLabels.add(labels[index])
                                }
                            }
                            getSharedPreferences(bridgePrefsName, MODE_PRIVATE).edit()
                                .putStringSet("selected_store_ids", selectedIds)
                                .putString("selected_store_labels", selectedLabels.joinToString(" | "))
                                .apply()
                            refreshBridgeStatus()
                        }
                        .setNegativeButton("Cancelar", null)
                        .show()
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "No se pudieron cargar las tiendas: ${e.message}" }
            }
        }.start()
    }

    private fun ensureContactsPermissionAndOpenApps() {
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) {
            chooseApplications()
            return
        }
        pendingAppMenu = true
        AlertDialog.Builder(this)
            .setTitle("Filtrar contactos guardados")
            .setMessage("Para ignorar personas ya agregadas, Phygital Bot necesita acceso a Contactos. Sin ese permiso no activará el puente.")
            .setPositiveButton("Permitir") { _, _ -> requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), 3001) }
            .setNegativeButton("Cancelar") { _, _ -> pendingAppMenu = false }
            .show()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 3001) {
            val allowed = grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
            if (allowed && pendingAppMenu) chooseApplications()
            else status.text = "El puente permanece bloqueado hasta permitir Contactos."
            pendingAppMenu = false
        }
    }

    private fun chooseApplications() {
        val prefs = getSharedPreferences(bridgePrefsName, MODE_PRIVATE)
        val labels = arrayOf("WhatsApp", "WhatsApp Business")
        val packages = arrayOf(whatsappPackage, whatsappBusinessPackage)
        val checked = BooleanArray(2) { i -> prefs.getBoolean("app_enabled_${packageSuffix(packages[i])}", false) }
        AlertDialog.Builder(this)
            .setTitle("Aplicaciones que atenderá el bot")
            .setMultiChoiceItems(labels, checked) { _, which, isChecked -> checked[which] = isChecked }
            .setPositiveButton("Guardar") { _, _ ->
                val editor = prefs.edit()
                packages.forEachIndexed { index, pkg -> editor.putBoolean("app_enabled_${packageSuffix(pkg)}", checked[index]) }
                editor.apply()
                refreshBridgeStatus()
                if (checked.any { it }) requestNotificationListenerAccess()
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
            .setMessage("Activa Phygital Bot en Acceso a notificaciones. Se ignorarán grupos y contactos guardados.")
            .setPositiveButton("Abrir configuración") { _, _ -> startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }
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
        val stores = prefs.getStringSet("selected_store_ids", emptySet()) ?: emptySet()
        val wa = prefs.getBoolean("app_enabled_${packageSuffix(whatsappPackage)}", false)
        val wb = prefs.getBoolean("app_enabled_${packageSuffix(whatsappBusinessPackage)}", false)
        val apps = listOfNotNull(if (wa) "WhatsApp" else null, if (wb) "Business" else null).joinToString(" + ")
        val listener = hasNotificationListenerAccess()
        status.text = when {
            stores.isEmpty() -> "Selecciona una o más tiendas para este teléfono. Versión ${BuildConfig.VERSION_NAME}."
            !wa && !wb -> "${stores.size} tienda(s) seleccionada(s). Elige qué aplicación(es) atenderá el bot."
            !listener -> "${stores.size} tienda(s) · $apps. Falta Acceso a notificaciones."
            else -> "Puente activo · ${stores.size} tienda(s) · $apps · versión ${BuildConfig.VERSION_NAME}."
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < 26) return
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(notificationChannelId, "Alertas de soporte Phygital", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Solicitudes de ayuda y escalamiento del dashboard"
            enableVibration(true)
        }
        manager.createNotificationChannel(channel)
    }

    private fun startNotificationPolling() {
        if (notificationPolling) return
        val auth = token ?: return
        notificationPolling = true
        Thread {
            val userKey = username ?: "user"
            val prefs = getSharedPreferences(notificationPrefsName, MODE_PRIVATE)
            val prefKey = "last_notification_$userKey"
            var lastId = prefs.getInt(prefKey, -1)
            while (notificationPolling && token != null) {
                try {
                    val events = JSONArray(request("GET", "/api/notifications?after_id=${if (lastId < 0) 0 else lastId}", null, auth))
                    if (lastId < 0) {
                        val start = maxOf(0, events.length() - 5)
                        for (i in start until events.length()) {
                            val event = events.getJSONObject(i)
                            showSupportNotification(event.optInt("id", 0), event.optString("title", "Phygital Bot"), event.optString("body", "Nueva alerta"))
                            lastId = maxOf(lastId, event.optInt("id", 0))
                        }
                        if (events.length() == 0) lastId = 0
                    } else {
                        for (i in 0 until events.length()) {
                            val event = events.getJSONObject(i)
                            val id = event.optInt("id", 0)
                            showSupportNotification(id, event.optString("title", "Phygital Bot"), event.optString("body", "Nueva alerta"))
                            lastId = maxOf(lastId, id)
                        }
                    }
                    prefs.edit().putInt(prefKey, lastId).apply()
                } catch (_: Exception) {}
                try { Thread.sleep(15000) } catch (_: InterruptedException) { break }
            }
        }.start()
    }

    private fun showSupportNotification(id: Int, title: String, body: String) {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val intent = Intent(this, MainActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP }
        val pendingIntent = PendingIntent.getActivity(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder = if (Build.VERSION.SDK_INT >= 26) {
            android.app.Notification.Builder(this, notificationChannelId)
        } else {
            @Suppress("DEPRECATION") android.app.Notification.Builder(this)
        }
        val notification = builder
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(android.app.Notification.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()
        getSystemService(NotificationManager::class.java).notify(10000 + id, notification)
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
                } else if (showIfCurrent) runOnUiThread { status.text = "La app está actualizada (${BuildConfig.VERSION_NAME})." }
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
                runOnUiThread { requestInstallOrOpen(apk) }
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
                .setMessage("Activa 'Permitir de esta fuente' y regresa a Phygital Bot.")
                .setPositiveButton("Abrir configuración") { _, _ -> startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName"))) }
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

    private fun logout() {
        notificationPolling = false
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
        status.text = "Sesión cerrada."
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
