package com.phygital.bot

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject

class AdminGateActivity : Activity() {
    private val sessionPrefsName = "phygital_session"
    private val imagePermissionRequest = 2401

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
            hint = "Usuario de soporte"
            setText("")
        }
        passwordInput = EditText(this).apply {
            hint = "Contraseña de soporte"
            inputType = 0x00000081
        }
        loginButton = Button(this).apply { text = "Activar bot" }
        status = TextView(this).apply {
            text = "Phygital Bot ${BuildConfig.VERSION_NAME}\nUsa una cuenta de soporte (operador), no una cuenta administrativa."
            setPadding(0, 16, 0, 0)
        }

        root.addView(usernameInput)
        root.addView(passwordInput)
        root.addView(loginButton)
        root.addView(status)
        setContentView(root)

        val prefs = getSharedPreferences(sessionPrefsName, MODE_PRIVATE)
        val savedToken = prefs.getString("token", null)
        val savedRole = prefs.getString("role", "").orEmpty().trim().lowercase()
        if (!savedToken.isNullOrBlank() && savedRole == "operador") {
            startBridgeKeepAlive()
            ensureImagePermissionThenOpenMain()
            return
        }
        if (!savedToken.isNullOrBlank()) {
            prefs.edit().clear().apply()
            status.text = "Se eliminó la sesión administrativa guardada en este teléfono.\nInicia sesión con credenciales de soporte."
        }

        loginButton.setOnClickListener {
            val user = usernameInput.text.toString().trim()
            val pass = passwordInput.text.toString()
            if (user.isBlank() || pass.isBlank()) {
                status.text = "Escribe usuario y contraseña de soporte."
            } else {
                login(user, pass)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        val prefs = getSharedPreferences(sessionPrefsName, MODE_PRIVATE)
        val token = prefs.getString("token", null)
        val role = prefs.getString("role", "").orEmpty().trim().lowercase()
        if (!token.isNullOrBlank() && role == "operador") startBridgeKeepAlive()
    }

    private fun login(userName: String, password: String) {
        loginButton.isEnabled = false
        usernameInput.isEnabled = false
        passwordInput.isEnabled = false
        status.text = "Activando bot con cuenta de soporte..."

        Thread {
            try {
                val body = JSONObject()
                    .put("username", userName)
                    .put("password", password)
                    .toString()

                val json = JSONObject(NetworkClient.request("POST", "/api/auth/mobile-login", body, null))
                val token = json.getString("access_token")
                val role = json.optString("rol", "")
                val username = json.optString("username", userName)

                if (role.trim().lowercase() != "operador") {
                    throw IllegalStateException("La cuenta no es de soporte/operador")
                }

                getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit()
                    .clear()
                    .putString("token", token)
                    .putString("role", role)
                    .putString("username", username)
                    .putString("session_type", "support_bridge")
                    .apply()

                runOnUiThread {
                    startBridgeKeepAlive()
                    ensureImagePermissionThenOpenMain()
                }
            } catch (e: Exception) {
                getSharedPreferences(sessionPrefsName, MODE_PRIVATE).edit().clear().apply()
                runOnUiThread {
                    loginButton.isEnabled = true
                    usernameInput.isEnabled = true
                    passwordInput.isEnabled = true
                    status.text = "No se pudo activar el bot con esa cuenta.\nUsa credenciales de soporte con rol operador.\nVersión: ${BuildConfig.VERSION_NAME}\nDetalle: ${e.message}"
                }
            }
        }.start()
    }

    private fun ensureImagePermissionThenOpenMain() {
        val permission = if (Build.VERSION.SDK_INT >= 33) Manifest.permission.READ_MEDIA_IMAGES else Manifest.permission.READ_EXTERNAL_STORAGE
        if (checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED) {
            openMain()
            return
        }
        status.text = "Permite acceso a fotos para guardar evidencias de WhatsApp en los reportes."
        requestPermissions(arrayOf(permission), imagePermissionRequest)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == imagePermissionRequest) {
            openMain()
        }
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
