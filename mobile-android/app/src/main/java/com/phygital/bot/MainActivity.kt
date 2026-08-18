package com.phygital.bot

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.ContactsContract
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
    private val notificationChannelId = "phygital_support_alerts"
    private var token: String? = null
    private var role: String? = null
    private var username: String? = null
    @Volatile private var notificationPolling = false
    private lateinit var status: TextView
    private lateinit var loginPanel: LinearLayout
    private lateinit var actionsPanel: LinearLayout
    private lateinit var syncButton: Button
    private lateinit var webView: WebView
    private var tokenInjected = false

    data class PhoneContact(val name: String, val phone: String)

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
        val password = EditText(this).apply { hint = "Contraseña"; inputType = 0x00000081 }
        val login = Button(this).apply { text = "Entrar" }
        loginPanel.addView(usernameInput)
        loginPanel.addView(password)
        loginPanel.addView(login)

        status = TextView(this).apply { text = "Inicia sesión para continuar."; setPadding(0, 12, 0, 12) }
        actionsPanel = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; visibility = View.GONE }
        syncButton = Button(this).apply { text = "Personal de soporte" }
        val dashboard = Button(this).apply { text = "Dashboard" }
        val logout = Button(this).apply { text = "Salir" }
        actionsPanel.addView(syncButton, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        actionsPanel.addView(dashboard, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        actionsPanel.addView(logout, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))

        webView = WebView(this).apply {
            visibility = View.GONE
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    val currentToken = token
                    val currentRole = role
                    if (currentToken != null && !tokenInjected && url.startsWith(baseUrl)) {
                        tokenInjected = true
                        val quotedToken = JSONObject.quote(currentToken)
                        val quotedRole = JSONObject.quote(currentRole ?: "")
                        view.evaluateJavascript("localStorage.setItem('phygital_token', $quotedToken); localStorage.setItem('phygital_role', $quotedRole); location.reload();", null)
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
            val pass = password.text.toString()
            if (user.isBlank() || pass.isBlank()) status.text = "Escribe usuario y contraseña."
            else { status.text = "Iniciando sesión..."; login(user, pass) }
        }
        syncButton.setOnClickListener {
            if (role == "admin") ensureContactsPermissionAndChoose()
            else status.text = "Solo el administrador puede cambiar el personal de soporte autorizado."
        }
        dashboard.setOnClickListener { tokenInjected = false; webView.visibility = View.VISIBLE; webView.loadUrl("$baseUrl/dashboard") }
        logout.setOnClickListener { logout() }
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(notificationChannelId, "Alertas de soporte Phygital", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Solicitudes de ayuda, escalamiento y cierre de casos"
            enableVibration(true)
        }
        manager.createNotificationChannel(channel)
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2001)
        }
    }

    private fun login(userName: String, password: String) {
        Thread {
            try {
                val body = JSONObject().put("username", userName).put("password", password).toString()
                val json = JSONObject(request("POST", "/api/auth/login", body, null))
                token = json.getString("access_token")
                role = json.optString("rol", "")
                username = json.optString("username", userName)
                runOnUiThread {
                    loginPanel.visibility = View.GONE
                    actionsPanel.visibility = View.VISIBLE
                    syncButton.visibility = if (role == "admin") View.VISIBLE else View.GONE
                    status.text = "Sesión ${role ?: "usuario"}. Alertas de soporte activas mientras la sesión permanezca activa."
                }
                startNotificationPolling()
            } catch (e: Exception) {
                runOnUiThread { status.text = "No se pudo iniciar sesión: ${e.message}" }
            }
        }.start()
    }

    private fun startNotificationPolling() {
        if (notificationPolling) return
        notificationPolling = true
        Thread {
            val auth = token ?: return@Thread
            val userKey = username ?: "user"
            val prefs = getSharedPreferences("phygital_notifications", MODE_PRIVATE)
            val prefKey = "last_notification_$userKey"
            var lastId = prefs.getInt(prefKey, -1)
            try {
                if (lastId < 0) {
                    val baseline = JSONArray(request("GET", "/api/notifications?after_id=0", null, auth))
                    var maxId = 0
                    for (i in 0 until baseline.length()) maxId = maxOf(maxId, baseline.getJSONObject(i).optInt("id", 0))
                    lastId = maxId
                    prefs.edit().putInt(prefKey, lastId).apply()
                }
            } catch (_: Exception) {}

            while (notificationPolling && token != null) {
                try {
                    val events = JSONArray(request("GET", "/api/notifications?after_id=$lastId", null, token))
                    for (i in 0 until events.length()) {
                        val event = events.getJSONObject(i)
                        val id = event.optInt("id", 0)
                        showSupportNotification(id, event.optString("title", "Phygital Bot"), event.optString("body", "Nueva alerta de soporte"))
                        lastId = maxOf(lastId, id)
                    }
                    prefs.edit().putInt(prefKey, lastId).apply()
                } catch (_: Exception) {}
                try { Thread.sleep(30000) } catch (_: InterruptedException) { break }
            }
        }.start()
    }

    private fun showSupportNotification(id: Int, title: String, body: String) {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val intent = Intent(this, MainActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP }
        val pendingIntent = PendingIntent.getActivity(this, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = android.app.Notification.Builder(this, notificationChannelId)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(android.app.Notification.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()
        getSystemService(NotificationManager::class.java).notify(id, notification)
    }

    private fun logout() {
        notificationPolling = false
        token = null
        role = null
        username = null
        tokenInjected = false
        webView.loadUrl("about:blank")
        webView.visibility = View.GONE
        actionsPanel.visibility = View.GONE
        loginPanel.visibility = View.VISIBLE
        status.text = "Sesión cerrada."
    }

    private fun ensureContactsPermissionAndChoose() {
        if (role != "admin") { status.text = "Solo el administrador puede administrar personal de soporte."; return }
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) chooseContacts()
        else requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), 1001)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 1001 && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) chooseContacts()
        else if (requestCode == 1001) status.text = "Permiso de contactos rechazado. Puedes seguir usando el dashboard."
    }

    private fun chooseContacts() {
        status.text = "Cargando agenda..."
        Thread {
            try {
                val contacts = readPhoneContacts()
                runOnUiThread {
                    if (contacts.isEmpty()) { status.text = "No se encontraron contactos. Revisa el permiso de contactos."; return@runOnUiThread }
                    val labels = contacts.map { if (it.name.isBlank()) it.phone else "${it.name} — ${it.phone}" }.toTypedArray()
                    val checked = BooleanArray(contacts.size)
                    status.text = "Selecciona únicamente personal interno que pueda ser soporte primario o secundario."
                    AlertDialog.Builder(this)
                        .setTitle("Selecciona personal de soporte")
                        .setMultiChoiceItems(labels, checked) { _, which, isChecked -> checked[which] = isChecked }
                        .setNegativeButton("Cancelar", null)
                        .setPositiveButton("Guardar") { _, _ -> syncSelectedContacts(contacts.filterIndexed { index, _ -> checked[index] }) }
                        .show()
                }
            } catch (e: Exception) { runOnUiThread { status.text = "No se pudo leer la agenda: ${e.message}" } }
        }.start()
    }

    private fun readPhoneContacts(): List<PhoneContact> {
        val result = linkedMapOf<String, PhoneContact>()
        val projection = arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.NUMBER)
        contentResolver.query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI, projection, null, null, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " ASC")?.use { cursor ->
            val nameIndex = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val phoneIndex = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (cursor.moveToNext()) {
                val name = if (nameIndex >= 0) cursor.getString(nameIndex) ?: "" else ""
                val phone = if (phoneIndex >= 0) cursor.getString(phoneIndex) ?: "" else ""
                val normalized = phone.filter { it.isDigit() || it == '+' }
                if (normalized.isNotBlank()) result[normalized] = PhoneContact(name, phone)
            }
        }
        return result.values.toList()
    }

    private fun syncSelectedContacts(selected: List<PhoneContact>) {
        val auth = token ?: return
        if (role != "admin") return
        status.text = "Guardando ${selected.size} contactos de soporte..."
        Thread {
            try {
                val contacts = JSONArray()
                selected.forEach { contacts.put(JSONObject().put("name", it.name).put("phone", it.phone)) }
                val response = JSONObject(request("POST", "/api/contacts/sync", JSONObject().put("contacts", contacts).toString(), auth))
                runOnUiThread { status.text = "Personal de soporte autorizado: ${response.optInt("synced")} contacto(s)." }
            } catch (e: Exception) { runOnUiThread { status.text = "Error guardando personal de soporte: ${e.message}" } }
        }.start()
    }

    private fun request(method: String, path: String, body: String?, bearer: String?): String {
        val connection = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 20000
            readTimeout = 20000
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Accept", "application/json")
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
