package com.phygital.bot

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
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
    private val notificationChannelId = "phygital_support_alerts"

    private var token: String? = null
    private var role: String? = null
    private var username: String? = null
    private var updatePromptVisible = false
    private var pendingUpdateFile: File? = null
    @Volatile private var notificationPolling = false

    private lateinit var status: TextView
    private lateinit var loginPanel: LinearLayout
    private lateinit var rolePanel: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createNotificationChannel()
        requestNotificationPermissionIfNeeded()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }
        status = TextView(this).apply {
            text = "Inicia sesión para continuar."
            setPadding(0, 12, 0, 12)
        }
        loginPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        rolePanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; visibility = android.view.View.GONE }

        val usernameInput = EditText(this).apply { hint = "Usuario" }
        val passwordInput = EditText(this).apply { hint = "Contraseña"; inputType = 0x00000081 }
        val loginButton = Button(this).apply { text = "Entrar" }
        loginPanel.addView(usernameInput)
        loginPanel.addView(passwordInput)
        loginPanel.addView(loginButton)

        val dashboardButton = Button(this).apply { text = "Abrir panel de administración" }
        val updateButton = Button(this).apply { text = "Buscar actualización" }
        val logoutButton = Button(this).apply { text = "Salir" }
        rolePanel.addView(dashboardButton)
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
        dashboardButton.setOnClickListener {
            if (role == "admin") startActivity(Intent(this, MainActivity::class.java))
            else status.text = "El dashboard está disponible únicamente para el administrador."
        }
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
        loginPanel.visibility = android.view.View.GONE
        rolePanel.visibility = android.view.View.VISIBLE
        val isAdmin = role == "admin"
        rolePanel.getChildAt(0).visibility = if (isAdmin) android.view.View.VISIBLE else android.view.View.GONE
        status.text = if (isAdmin) {
            "Administrador · acceso al dashboard y alertas administrativas. Versión ${BuildConfig.VERSION_NAME}."
        } else {
            "Sesión ${role ?: "usuario"}. Esta cuenta solo recibe las notificaciones correspondientes a su puesto."
        }
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
        val intent = Intent(this, AdminGateActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP }
        val pendingIntent = PendingIntent.getActivity(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val builder = if (Build.VERSION.SDK_INT >= 26) android.app.Notification.Builder(this, notificationChannelId)
        else @Suppress("DEPRECATION") android.app.Notification.Builder(this)
        val notification = builder
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(android.app.Notification.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()
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
        token = null
        role = null
        username = null
        getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit().clear().apply()
        rolePanel.visibility = android.view.View.GONE
        loginPanel.visibility = android.view.View.VISIBLE
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
