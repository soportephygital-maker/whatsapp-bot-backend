package com.phygital.bot

import android.app.Activity
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject

class AdminGateActivity : Activity() {
    private val sessionPrefsName = "phygital_session"
    private val serverLabel = "https://whatsapp-bot-backend-142e.onrender.com"

    private lateinit var status: TextView
    private lateinit var usernameInput: EditText
    private lateinit var passwordInput: EditText
    private lateinit var loginButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 48, 32, 48)
        }

        usernameInput = EditText(this).apply {
            hint = "Usuario"
            setText("")
        }
        passwordInput = EditText(this).apply {
            hint = "Contraseña"
            inputType = 0x00000081
        }
        loginButton = Button(this).apply { text = "Entrar" }
        status = TextView(this).apply {
            text = "Phygital Bot ${BuildConfig.VERSION_NAME}\nServidor: $serverLabel"
            setPadding(0, 16, 0, 0)
        }

        root.addView(usernameInput)
        root.addView(passwordInput)
        root.addView(loginButton)
        root.addView(status)
        setContentView(root)

        val prefs = getSharedPreferences(sessionPrefsName, MODE_PRIVATE)
        val savedToken = prefs.getString("token", null)
        if (!savedToken.isNullOrBlank()) {
            if (isAdminRole(prefs.getString("role", null))) startBridgeKeepAlive()
            openMain()
            return
        }

        loginButton.setOnClickListener {
            val user = usernameInput.text.toString().trim()
            val pass = passwordInput.text.toString()
            if (user.isBlank() || pass.isBlank()) {
                status.text = "Escribe usuario y contraseña.\nServidor: $serverLabel"
            } else {
                login(user, pass)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        val prefs = getSharedPreferences(sessionPrefsName, MODE_PRIVATE)
        val token = prefs.getString("token", null)
        if (!token.isNullOrBlank() && isAdminRole(prefs.getString("role", null))) startBridgeKeepAlive()
    }

    private fun login(userName: String, password: String) {
        loginButton.isEnabled = false
        usernameInput.isEnabled = false
        passwordInput.isEnabled = false
        status.text = "Iniciando sesión...\nServidor: $serverLabel\nEndpoint: /api/auth/login"

        Thread {
            try {
                val body = JSONObject()
                    .put("username", userName)
                    .put("password", password)
                    .toString()

                val json = JSONObject(NetworkClient.request("POST", "/api/auth/login", body, null))
                val token = json.getString("access_token")
                val role = json.optString("rol", "")
                val username = json.optString("username", userName)

                getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit()
                    .putString("token", token)
                    .putString("role", role)
                    .putString("username", username)
                    .apply()

                runOnUiThread {
                    if (isAdminRole(role)) startBridgeKeepAlive()
                    openMain()
                }
            } catch (e: Exception) {
                runOnUiThread {
                    loginButton.isEnabled = true
                    usernameInput.isEnabled = true
                    passwordInput.isEnabled = true
                    status.text = "No se pudo iniciar sesión.\nVersión: ${BuildConfig.VERSION_NAME}\nServidor: $serverLabel\nDetalle: ${e.message}"
                }
            }
        }.start()
    }

    private fun isAdminRole(value: String?): Boolean {
        val normalized = value.orEmpty().trim().lowercase().replace('-', '_').replace(' ', '_')
        return normalized == "admin" || normalized == "super_admin" || normalized == "superadmin"
    }

    private fun startBridgeKeepAlive() {
        val intent = Intent(this, BridgeKeepAliveService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent)
            else startService(intent)
        } catch (_: Exception) {
        }
    }

    private fun openMain() {
        startActivity(
            Intent(this, MainActivity::class.java)
                .putExtra("open_dashboard", true)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
        )
        finish()
    }
}
