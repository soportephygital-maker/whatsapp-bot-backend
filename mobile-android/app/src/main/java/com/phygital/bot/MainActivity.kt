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
import android.view.View
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import androidx.core.content.FileProvider
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : Activity() {
    private val baseUrl = "https://whatsapp-bot-backend-142e.onrender.com"
    private val sessionPrefsName = "phygital_session"
    private val bridgePrefsName = "phygital_local_bridge"
    private val notificationPrefsName = "phygital_notifications"
    private val notificationChannelId = "phygital_support_alerts"

    private var token: String? = null
    private var role: String? = null
    private var username: String? = null
    private var tokenInjected = false
    private var updatePromptVisible = false
    private var pendingUpdateFile: File? = null
    private var canManageBridge = false
    @Volatile private var notificationPolling = false

    private lateinit var webView: WebView
    private lateinit var settingsButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createNotificationChannel()
        requestNotificationPermissionIfNeeded()

        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(12, 10, 12, 10)
        }

        val dashboardButton = Button(this).apply {
            text = "Dashboard"
            setOnClickListener { openDashboard() }
        }
        settingsButton = Button(this).apply {
            text = "Configuración"
            visibility = View.VISIBLE
            setOnClickListener { showBridgeSettings() }
        }
        val logoutButton = Button(this).apply {
            text = "Salir"
            setOnClickListener { confirmLogout() }
        }

        toolbar.addView(dashboardButton, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        toolbar.addView(settingsButton, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        toolbar.addView(logoutButton, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))

        webView = WebView(this).apply {
            visibility = View.VISIBLE
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
                            "localStorage.setItem('phygital_token',$quotedToken);localStorage.setItem('phygital_role',$quotedRole);if(window.show){show();}",
                            null
                        )
                    }
                }
            }
        }

        root.addView(toolbar)
        root.addView(webView, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)

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

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    private fun restoreSavedSession() {
        val prefs = getSharedPreferences(sessionPrefsName, MODE_PRIVATE)
        val savedToken = prefs.getString("token", null)
        if (savedToken.isNullOrBlank()) {
            openLogin()
            return
        }
        token = savedToken
        role = prefs.getString("role", null)
        username = prefs.getString("username", null)
        Thread {
            try {
                request("GET", "/api/stats", null, savedToken)
                loadNativeAccess(savedToken)
                runOnUiThread { openDashboard() }
                startNotificationPolling()
            } catch (e: Exception) {
                if ((e.message ?: "").contains("HTTP 401")) {
                    getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit().clear().apply()
                    runOnUiThread { openLogin() }
                } else {
                    try { loadNativeAccess(savedToken) } catch (_: Exception) {}
                    runOnUiThread { openDashboard() }
                    startNotificationPolling()
                }
            }
        }.start()
    }

    private fun loadNativeAccess(auth: String) {
        val access = JSONObject(request("GET", "/api/access-control/me", null, auth))
        val permissions = access.optJSONObject("permissions") ?: JSONObject()
        canManageBridge = permissions.optBoolean("manage_mobile_bridge", false)
        runOnUiThread { settingsButton.visibility = View.VISIBLE }
    }

    private fun isAdminUser(): Boolean {
        val normalized = role.orEmpty().trim().lowercase().replace('-', '_').replace(' ', '_')
        return normalized == "admin" || normalized == "super_admin" || normalized == "superadmin"
    }

    private fun openLogin() {
        startActivity(Intent(this, AdminGateActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
        finish()
    }

    private fun openDashboard() {
        tokenInjected = false
        webView.loadUrl("$baseUrl/dashboard?embedded=1")
    }

    private fun confirmLogout() {
        AlertDialog.Builder(this)
            .setTitle("Cerrar sesión")
            .setMessage("¿Quieres salir de Phygital Bot?")
            .setNegativeButton("Cancelar", null)
            .setPositiveButton("Salir") { _, _ -> logout() }
            .show()
    }

    private fun logout() {
        notificationPolling = false
        token = null
        role = null
        username = null
        getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit().clear().apply()
        webView.clearCache(true)
        webView.evaluateJavascript("localStorage.removeItem('phygital_token');localStorage.removeItem('phygital_role');", null)
        openLogin()
    }

    private fun showBridgeSettings() {
        if (!isAdminUser()) {
            showNotificationOnlySettings()
            return
        }
        val auth = token ?: return
        Thread {
            try {
                val companies = JSONArray(request("GET", "/api/empresas/listar", null, auth))
                runOnUiThread { buildBridgeSettingsDialog(companies) }
            } catch (e: Exception) {
                runOnUiThread {
                    AlertDialog.Builder(this)
                        .setTitle("Configuración")
                        .setMessage("No se pudieron cargar las empresas y tiendas.\n${e.message ?: ""}")
                        .setPositiveButton("Aceptar", null)
                        .show()
                }
            }
        }.start()
    }

    private fun showNotificationOnlySettings() {
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 20, 32, 20)
        }
        content.addView(TextView(this).apply {
            text = "Notificaciones"
            textSize = 17f
        })
        content.addView(TextView(this).apply {
            text = "Desde aquí puedes permitir que Phygital Bot reciba y muestre las notificaciones necesarias."
        })
        content.addView(Button(this).apply {
            text = "Acceso a notificaciones"
            setOnClickListener { startActivity(Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS")) }
        })

        AlertDialog.Builder(this)
            .setTitle("Configuración")
            .setView(content)
            .setPositiveButton("Cerrar", null)
            .show()
    }

    private fun buildBridgeSettingsDialog(companies: JSONArray) {
        val prefs = getSharedPreferences(bridgePrefsName, MODE_PRIVATE)
        val selected = prefs.getStringSet("selected_store_ids", emptySet())?.toMutableSet() ?: mutableSetOf()

        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 16, 32, 16)
        }

        val waSwitch = Switch(this).apply {
            text = "WhatsApp"
            isChecked = prefs.getBoolean("app_enabled_com_whatsapp", false)
        }
        val businessSwitch = Switch(this).apply {
            text = "WhatsApp Business"
            isChecked = prefs.getBoolean("app_enabled_com_whatsapp_w4b", false)
        }
        content.addView(waSwitch)
        content.addView(businessSwitch)

        content.addView(TextView(this).apply {
            text = "\nTiendas que atenderá este teléfono"
            textSize = 16f
        })

        val checks = mutableListOf<Pair<Int, CheckBox>>()
        for (i in 0 until companies.length()) {
            val company = companies.optJSONObject(i) ?: continue
            val companyName = company.optString("nombre", company.optString("name", "Empresa"))
            content.addView(TextView(this).apply {
                text = "\n$companyName"
                textSize = 15f
            })
            val stores = company.optJSONArray("tiendas") ?: JSONArray()
            for (j in 0 until stores.length()) {
                val store = stores.optJSONObject(j) ?: continue
                val storeId = store.optInt("id", 0)
                if (storeId <= 0) continue
                val storeName = store.optString("nombre", store.optString("name", "Tienda $storeId"))
                val check = CheckBox(this).apply {
                    text = storeName
                    isChecked = selected.contains(storeId.toString())
                }
                checks.add(storeId to check)
                content.addView(check)
            }
        }

        val notificationAccess = Button(this).apply {
            text = "Acceso a notificaciones"
            setOnClickListener { startActivity(Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS")) }
        }
        val appSettings = Button(this).apply {
            text = "Ajustes de la aplicación"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
            }
        }
        content.addView(notificationAccess)
        content.addView(appSettings)

        val scroll = ScrollView(this).apply { addView(content) }
        AlertDialog.Builder(this)
            .setTitle("Configuración del puente")
            .setView(scroll)
            .setNegativeButton("Cancelar", null)
            .setPositiveButton("Guardar") { _, _ ->
                val selectedIds = checks.filter { it.second.isChecked }.map { it.first.toString() }.toSet()
                prefs.edit()
                    .putBoolean("app_enabled_com_whatsapp", waSwitch.isChecked)
                    .putBoolean("app_enabled_com_whatsapp_w4b", businessSwitch.isChecked)
                    .putStringSet("selected_store_ids", selectedIds)
                    .apply()
                startBridgeKeepAlive()
            }
            .show()
    }

    private fun startBridgeKeepAlive() {
        val intent = Intent(this, BridgeKeepAliveService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent)
            else startService(intent)
        } catch (_: Exception) {}
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
                }
            } catch (_: Exception) {
                if (showIfCurrent) return@Thread
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
            } catch (_: Exception) {}
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
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        startActivity(intent)
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2001)
        }
    }

    private fun request(method: String, path: String, body: String?, bearer: String?): String =
        NetworkClient.request(method, path, body, bearer)
}
