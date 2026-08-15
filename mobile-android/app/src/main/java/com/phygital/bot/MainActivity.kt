package com.phygital.bot

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
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
    private var token: String? = null
    private lateinit var status: TextView
    private lateinit var loginPanel: LinearLayout
    private lateinit var actionsPanel: LinearLayout
    private lateinit var webView: WebView
    private var tokenInjected = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }

        loginPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val username = EditText(this).apply { hint = "Usuario" }
        val password = EditText(this).apply {
            hint = "Contraseña"
            inputType = 0x00000081
        }
        val login = Button(this).apply { text = "Entrar" }
        status = TextView(this).apply { text = "Inicia sesión para sincronizar contactos." }
        loginPanel.addView(username)
        loginPanel.addView(password)
        loginPanel.addView(login)
        loginPanel.addView(status)

        actionsPanel = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            visibility = View.GONE
        }
        val sync = Button(this).apply { text = "Sincronizar contactos" }
        val dashboard = Button(this).apply { text = "Dashboard" }
        actionsPanel.addView(sync, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        actionsPanel.addView(dashboard, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))

        webView = WebView(this).apply {
            visibility = View.GONE
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    val currentToken = token
                    if (currentToken != null && !tokenInjected && url.startsWith(baseUrl)) {
                        tokenInjected = true
                        val quoted = JSONObject.quote(currentToken)
                        view.evaluateJavascript("localStorage.setItem('phygital_token', $quoted); location.reload();", null)
                    }
                }
            }
        }

        root.addView(loginPanel)
        root.addView(actionsPanel)
        root.addView(webView, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)

        login.setOnClickListener {
            val user = username.text.toString().trim()
            val pass = password.text.toString()
            if (user.isBlank() || pass.isBlank()) {
                status.text = "Escribe usuario y contraseña."
            } else {
                status.text = "Iniciando sesión..."
                login(user, pass)
            }
        }

        sync.setOnClickListener { ensureContactsPermissionAndSync() }
        dashboard.setOnClickListener {
            tokenInjected = false
            webView.visibility = View.VISIBLE
            webView.loadUrl("$baseUrl/dashboard")
        }
    }

    private fun login(username: String, password: String) {
        Thread {
            try {
                val body = JSONObject().put("username", username).put("password", password).toString()
                val response = request("POST", "/api/auth/login", body, null)
                val json = JSONObject(response)
                token = json.getString("access_token")
                runOnUiThread {
                    status.text = "Sesión iniciada."
                    loginPanel.visibility = View.GONE
                    actionsPanel.visibility = View.VISIBLE
                    ensureContactsPermissionAndSync()
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "No se pudo iniciar sesión: ${e.message}" }
            }
        }.start()
    }

    private fun ensureContactsPermissionAndSync() {
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) {
            syncContacts()
        } else {
            requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), 1001)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 1001 && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            syncContacts()
        } else if (requestCode == 1001) {
            status.text = "Permiso de contactos rechazado. Puedes usar el dashboard, pero no se podrá clasificar la agenda."
        }
    }

    private fun syncContacts() {
        val auth = token ?: return
        status.text = "Sincronizando agenda..."
        Thread {
            try {
                val contacts = JSONArray()
                val projection = arrayOf(
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER
                )
                contentResolver.query(
                    ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                    projection,
                    null,
                    null,
                    null
                )?.use { cursor ->
                    val nameIndex = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                    val phoneIndex = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
                    while (cursor.moveToNext()) {
                        val name = if (nameIndex >= 0) cursor.getString(nameIndex) ?: "" else ""
                        val phone = if (phoneIndex >= 0) cursor.getString(phoneIndex) ?: "" else ""
                        if (phone.isNotBlank()) contacts.put(JSONObject().put("name", name).put("phone", phone))
                    }
                }
                val body = JSONObject().put("contacts", contacts).toString()
                val response = JSONObject(request("POST", "/api/contacts/sync", body, auth))
                runOnUiThread {
                    status.text = "Agenda sincronizada: ${response.optInt("synced")} contactos."
                }
            } catch (e: Exception) {
                runOnUiThread { status.text = "Error sincronizando contactos: ${e.message}" }
            }
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
