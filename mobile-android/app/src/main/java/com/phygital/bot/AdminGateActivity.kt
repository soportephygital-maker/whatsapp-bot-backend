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
import android.graphics.Color
import android.graphics.drawable.ColorDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.View
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

class AdminGateActivity : Activity() {
    private val baseUrl = "https://whatsapp-bot-backend-v2.onrender.com"
    private val sessionPrefsName = "phygital_session"
    private val notificationPrefsName = "phygital_notifications"
    private val appearancePrefsName = "phygital_global_appearance"
    private val notificationChannelId = "phygital_support_alerts"

    private var token: String? = null
    private var role: String? = null
    private var username: String? = null
    private var updatePromptVisible = false
    private var pendingUpdateFile: File? = null
    @Volatile private var notificationPolling = false

    private lateinit var root: LinearLayout
    private lateinit var status: TextView
    private lateinit var loginPanel: LinearLayout
    private lateinit var rolePanel: LinearLayout
    private lateinit var dashboardButton: Button
    private lateinit var adminPanelButton: Button
    private lateinit var permissionsButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createNotificationChannel()
        requestNotificationPermissionIfNeeded()

        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }
        applyCachedAppearance()

        status = TextView(this).apply {
            text = "Inicia sesión para continuar."
            setPadding(0, 12, 0, 18)
        }
        loginPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        rolePanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; visibility = View.GONE }

        val usernameInput = EditText(this).apply { hint = "Usuario" }
        val passwordInput = EditText(this).apply { hint = "Contraseña"; inputType = 0x00000081 }
        val loginButton = Button(this).apply { text = "Entrar" }
        loginPanel.addView(usernameInput)
        loginPanel.addView(passwordInput)
        loginPanel.addView(loginButton)

        dashboardButton = Button(this).apply { text = "Dashboard" }
        adminPanelButton = Button(this).apply { text = "Panel de administración" }
        permissionsButton = Button(this).apply { text = "Revisar permisos de la app" }
        val updateButton = Button(this).apply { text = "Buscar actualización" }
        val logoutButton = Button(this).apply { text = "Salir" }

        rolePanel.addView(dashboardButton)
        rolePanel.addView(adminPanelButton)
        rolePanel.addView(permissionsButton)
        rolePanel.addView(updateButton)
        rolePanel.addView(logoutButton)

        root.addView(status)
        root.addView(loginPanel)
        root.addView(rolePanel)
        setContentView(root)

        loginButton.setOnClickListener {
            val user = usernameInput.text.toString().trim()
            val pass = passwordInput.text.toString()
            if (user.isBlank() || pass.isBlank()) status.text = "Escribe usuario y contraseña."
            else login(user, pass)
        }
        dashboardButton.setOnClickListener { startActivity(Intent(this, MainActivity::class.java).putExtra("open_dashboard", true)) }
        adminPanelButton.setOnClickListener { startActivity(Intent(this, MainActivity::class.java)) }
        permissionsButton.setOnClickListener { showPermissionCenter() }
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
        if (token != null) refreshAppearanceFromServer()
        checkForUpdate(false)
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
                runOnUiThread { showRoleUi() }
                refreshAppearanceFromServer()
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
        showRoleUi()
        refreshAppearanceFromServer()
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

    private fun showRoleUi() {
        loginPanel.visibility = View.GONE
        rolePanel.visibility = View.VISIBLE
        val elevated = role == "admin" || role == "gerente"
        adminPanelButton.visibility = if (elevated) View.VISIBLE else View.GONE
        dashboardButton.visibility = View.VISIBLE
        permissionsButton.visibility = View.VISIBLE
        status.text = "Sesión activa · versión ${BuildConfig.VERSION_NAME}."
    }

    private fun refreshAppearanceFromServer() {
        val auth = token ?: return
        Thread {
            try {
                val theme = JSONObject(request("GET", "/api/settings/appearance", null, auth))
                val prefs = getSharedPreferences(appearancePrefsName, MODE_PRIVATE).edit()
                listOf("background", "cards", "text", "accent", "input", "backgroundImage", "backgroundSize").forEach { key ->
                    prefs.putString(key, theme.optString(key, ""))
                }
                prefs.apply()
                runOnUiThread { applyCachedAppearance() }
            } catch (_: Exception) {}
        }.start()
    }

    private fun applyCachedAppearance() {
        if (!::root.isInitialized) return
        val prefs = getSharedPreferences(appearancePrefsName, MODE_PRIVATE)
        val background = prefs.getString("background", "#040814") ?: "#040814"
        val text = prefs.getString("text", "#edf6ff") ?: "#edf6ff"
        try { root.setBackgroundColor(Color.parseColor(background)) } catch (_: Exception) { root.setBackgroundColor(Color.parseColor("#040814")) }
        val textColor = try { Color.parseColor(text) } catch (_: Exception) { Color.WHITE }
        if (::status.isInitialized) status.setTextColor(textColor)
        fun tintPanel(panel: LinearLayout) {
            for (i in 0 until panel.childCount) {
                val v = panel.getChildAt(i)
                if (v is TextView) v.setTextColor(textColor)
                if (v is EditText) v.setHintTextColor(textColor and 0x99FFFFFF.toInt())
            }
        }
        if (::loginPanel.isInitialized) tintPanel(loginPanel)
        if (::rolePanel.isInitialized) tintPanel(rolePanel)
    }

    private fun showPermissionCenter() {
        val rows = mutableListOf<String>()
        val contacts = checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED
        val notifications = Build.VERSION.SDK_INT < 33 || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        val listener = hasNotificationListenerAccess()
        val installs = Build.VERSION.SDK_INT < 26 || packageManager.canRequestPackageInstalls()
        val power = getSystemService(PowerManager::class.java)
        val battery = Build.VERSION.SDK_INT < 23 || power.isIgnoringBatteryOptimizations(packageName)

        rows += "${if (contacts) "✓" else "✗"} Contactos"
        rows += "${if (notifications) "✓" else "✗"} Notificaciones de Phygital"
        rows += "${if (listener) "✓" else "✗"} Acceso a notificaciones de WhatsApp"
        rows += "${if (installs) "✓" else "✗"} Instalar actualizaciones"
        rows += "${if (battery) "✓" else "✗"} Sin restricción de batería"
        rows += "✓ Internet"
        rows += "✓ Estado de red"
        rows += "✓ WakeLock"

        val allOk = contacts && notifications && listener && installs && battery
        AlertDialog.Builder(this)
            .setTitle(if (allOk) "Todos los permisos están listos" else "Faltan permisos")
            .setMessage(rows.joinToString("\n"))
            .setPositiveButton(if (allOk) "Cerrar" else "Corregir faltantes") { _, _ -> openNextMissingPermission(contacts, notifications, listener, installs, battery) }
            .setNegativeButton("Cerrar", null)
            .show()
    }

    private fun openNextMissingPermission(contacts: Boolean, notifications: Boolean, listener: Boolean, installs: Boolean, battery: Boolean) {
        when {
            !contacts -> requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), 3001)
            !notifications && Build.VERSION.SDK_INT >= 33 -> requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2001)
            !listener -> startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            !installs && Build.VERSION.SDK_INT >= 26 -> startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
            !battery && Build.VERSION.SDK_INT >= 23 -> {
                try { startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName"))) }
                catch (_: Exception) { startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
            }
        }
    }

    private fun hasNotificationListenerAccess(): Boolean {
        val enabled = Settings.Secure.getString(contentResolver, "enabled_notification_listeners") ?: return false
        val component = ComponentName(this, LocalWhatsAppBridgeService::class.java).flattenToString()
        return enabled.split(":").any { it.equals(component, ignoreCase = true) }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < 26) return
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(notificationChannelId, "Alertas de soporte Phygital", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Notificaciones según el puesto del usuario"
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
                    for (i in 0 until events.length()) {
                        val event = events.getJSONObject(i)
                        val id = event.optInt("id", 0)
                        if (lastId >= 0 || i >= maxOf(0, events.length() - 5)) {
                            showSupportNotification(id, event.optString("title", "Phygital Bot"), event.optString("body", "Nueva alerta"))
                        }
                        lastId = maxOf(lastId, id)
                    }
                    if (events.length() == 0 && lastId < 0) lastId = 0
                    prefs.edit().putInt(prefKey, lastId).apply()
                } catch (_: Exception) {}
                try { Thread.sleep(15000) } catch (_: InterruptedException) { break }
            }
        }.start()
    }

    private fun showSupportNotification(id: Int, title: String, body: String) {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val intent = Intent(this, AdminGateActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP }
        val pendingIntent = PendingIntent.getActivity(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder = if (Build.VERSION.SDK_INT >= 26) android.app.Notification.Builder(this, notificationChannelId)
        else @Suppress("DEPRECATION") android.app.Notification.Builder(this)
        val notification = builder.setSmallIcon(android.R.drawable.ic_dialog_alert).setContentTitle(title).setContentText(body)
            .setStyle(android.app.Notification.BigTextStyle().bigText(body)).setAutoCancel(true).setContentIntent(pendingIntent).build()
        getSystemService(NotificationManager::class.java).notify(20000 + id, notification)
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
                if (published && latestCode > BuildConfig.VERSION_CODE && apkUrl.isNotBlank()) runOnUiThread { showUpdatePrompt(latestName, message, apkUrl) }
                else if (showIfCurrent) runOnUiThread { status.text = "La app está actualizada (${BuildConfig.VERSION_NAME})." }
            } catch (e: Exception) {
                if (showIfCurrent) runOnUiThread { status.text = "No se pudo consultar actualizaciones: ${e.message}" }
            }
        }.start()
    }

    private fun showUpdatePrompt(versionName: String, message: String, apkUrl: String) {
        if (updatePromptVisible || isFinishing) return
        updatePromptVisible = true
        AlertDialog.Builder(this).setTitle("Actualización disponible${if (versionName.isNotBlank()) " · $versionName" else ""}")
            .setMessage(message).setNegativeButton("Después") { _, _ -> updatePromptVisible = false }
            .setPositiveButton("Instalar actualización") { _, _ -> updatePromptVisible = false; downloadAndInstallUpdate(apkUrl) }
            .setOnCancelListener { updatePromptVisible = false }.show()
    }

    private fun downloadAndInstallUpdate(apkUrl: String) {
        status.text = "Descargando actualización..."
        Thread {
            try {
                val dir = File(cacheDir, "updates").apply { mkdirs() }
                val apk = File(dir, "phygital-bot-update.apk")
                val connection = (URL(apkUrl).openConnection() as HttpURLConnection).apply { connectTimeout = 20000; readTimeout = 60000; instanceFollowRedirects = true; setRequestProperty("User-Agent", "Phygital-Bot-Android") }
                connection.inputStream.use { input -> apk.outputStream().use { output -> input.copyTo(output) } }
                connection.disconnect()
                runOnUiThread { requestInstallOrOpen(apk) }
            } catch (e: Exception) { runOnUiThread { status.text = "No se pudo descargar la actualización: ${e.message}" } }
        }.start()
    }

    private fun requestInstallOrOpen(apk: File) {
        if (Build.VERSION.SDK_INT >= 26 && !packageManager.canRequestPackageInstalls()) {
            pendingUpdateFile = apk
            startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
            return
        }
        installApk(apk)
    }

    private fun installApk(apk: File) {
        val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", apk)
        val intent = Intent(Intent.ACTION_VIEW).apply { setDataAndType(uri, "application/vnd.android.package-archive"); addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK) }
        startActivity(intent)
    }

    private fun logout() {
        notificationPolling = false
        token = null; role = null; username = null
        getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit().clear().apply()
        rolePanel.visibility = View.GONE
        loginPanel.visibility = View.VISIBLE
        status.text = "Sesión cerrada."
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2001)
    }

    private fun request(method: String, path: String, body: String?, bearer: String?): String {
        val connection = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method; connectTimeout = 20000; readTimeout = 20000
            setRequestProperty("Content-Type", "application/json"); setRequestProperty("Accept", "application/json")
            if (bearer != null) setRequestProperty("Authorization", "Bearer $bearer")
            if (body != null) { doOutput = true; outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) } }
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
        connection.disconnect()
        if (code !in 200..299) throw IllegalStateException("HTTP $code $text")
        return text
    }
}
