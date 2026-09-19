package com.phygital.bot

import android.content.ComponentName
import android.content.Context
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object BridgeDiagnostics {
    private const val PREFS = "phygital_bridge_diagnostics"
    private const val RUNTIME_PREFS = "phygital_bridge_runtime"
    private const val BRIDGE_PREFS = "phygital_local_bridge"
    private const val SESSION_PREFS = "phygital_session"

    fun record(
        context: Context,
        stage: String,
        detail: String = "",
        packageName: String = "",
        title: String = "",
        text: String = "",
        canReply: Boolean? = null,
    ) {
        val now = System.currentTimeMillis()
        runCatching {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putLong("time", now)
                .putString("stage", stage)
                .putString("detail", detail.take(700))
                .putString("package", packageName)
                .putString("title", title.take(180))
                .putString("text", text.take(300))
                .apply {
                    if (canReply == null) remove("can_reply") else putBoolean("can_reply", canReply)
                }
                .apply()
        }
        uploadToAdminDashboard(context, now, stage, detail, packageName, title, text, canReply)
    }

    private fun requestUrl(stage: String, detail: String): String {
        // In a Kotlin raw string, \\s inside a character class excluded the
        // letter "s", so "https://..." was being truncated to "http".
        val fromError = Regex("""URL=([^|\\s]+)""".replace("\\\\s", "\\s")).find(detail)?.groupValues?.getOrNull(1).orEmpty()
        if (fromError.isNotBlank()) return fromError
        return when (stage.uppercase()) {
            "POST_SENDING", "BACKEND_RESPONSE", "ERROR" -> NetworkClient.absoluteUrl("/api/local-bridge/inbound")
            else -> ""
        }
    }

    private fun uploadToAdminDashboard(
        context: Context,
        now: Long,
        stage: String,
        detail: String,
        packageName: String,
        title: String,
        text: String,
        canReply: Boolean?,
    ) {
        val token = context.getSharedPreferences(SESSION_PREFS, Context.MODE_PRIVATE).getString("token", null)
        if (token.isNullOrBlank()) return
        val bridge = context.getSharedPreferences(BRIDGE_PREFS, Context.MODE_PRIVATE)
        val stores = bridge.getStringSet("selected_store_ids", emptySet()).orEmpty().sorted()
        val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "android-device"
        val payload = JSONObject()
            .put("event_time_ms", now)
            .put("device_id", deviceId)
            .put("app_version", BuildConfig.VERSION_NAME)
            .put("build_code", BuildConfig.VERSION_CODE)
            .put("stage", stage.take(80))
            .put("detail", detail.take(4000))
            .put("package_name", packageName.take(160))
            .put("conversation", title.take(240))
            .put("text", text.take(2000))
            .put("request_url", requestUrl(stage, detail))
            .put("whatsapp_enabled", bridge.getBoolean("app_enabled_com_whatsapp", false))
            .put("whatsapp_business_enabled", bridge.getBoolean("app_enabled_com_whatsapp_w4b", false))
            .put("selected_whatsapp_package", bridge.getString("selected_whatsapp_package", "com.whatsapp.w4b"))
            .put("selected_store_ids", JSONArray(stores))
        if (canReply == null) payload.put("can_reply", JSONObject.NULL) else payload.put("can_reply", canReply)

        Thread {
            runCatching {
                NetworkClient.request("POST", "/api/local-bridge/diagnostics", payload.toString(), token)
            }
        }.start()
    }

    private fun fmtTime(value: Long): String {
        if (value <= 0L) return "Nunca"
        return SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.getDefault()).format(Date(value))
    }

    private fun listenerAccessEnabled(context: Context): Boolean {
        return runCatching {
            val enabled = Settings.Secure.getString(context.contentResolver, "enabled_notification_listeners").orEmpty()
            val component = ComponentName(context, LocalWhatsAppBridgeService::class.java)
            enabled.split(":").any {
                it.equals(component.flattenToString(), ignoreCase = true) ||
                    it.equals(component.flattenToShortString(), ignoreCase = true)
            }
        }.getOrDefault(false)
    }

    private fun packageInstalled(context: Context, pkg: String): Boolean {
        return runCatching {
            @Suppress("DEPRECATION")
            context.packageManager.getApplicationInfo(pkg, 0)
            true
        }.getOrDefault(false)
    }

    fun snapshot(context: Context): String {
        val diag = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val runtime = context.getSharedPreferences(RUNTIME_PREFS, Context.MODE_PRIVATE)
        val bridge = context.getSharedPreferences(BRIDGE_PREFS, Context.MODE_PRIVATE)
        val session = context.getSharedPreferences(SESSION_PREFS, Context.MODE_PRIVATE)

        val time = diag.getLong("time", 0L)
        val pkg = diag.getString("package", "").orEmpty()
        val app = when (pkg) {
            "com.whatsapp.w4b" -> "WhatsApp Business"
            "com.whatsapp" -> "WhatsApp"
            else -> pkg.ifBlank { "Sin evento de WhatsApp" }
        }
        val stage = diag.getString("stage", "").orEmpty()
        val detail = diag.getString("detail", "").orEmpty()
        val title = diag.getString("title", "").orEmpty()
        val text = diag.getString("text", "").orEmpty()
        val canReply = if (diag.contains("can_reply")) {
            if (diag.getBoolean("can_reply", false)) "Sí" else "No"
        } else "Sin comprobar"

        val access = listenerAccessEnabled(context)
        val keepAliveActive = runtime.getBoolean(BridgeKeepAliveService.ACTIVE_KEY, false)
        val heartbeat = runtime.getLong(BridgeKeepAliveService.HEARTBEAT_KEY, 0L)
        val heartbeatAge = if (heartbeat > 0L) ((System.currentTimeMillis() - heartbeat).coerceAtLeast(0L) / 1000L) else -1L
        val lastScreenState = runtime.getString("last_screen_state", "SIN EVENTO").orEmpty()
        val power = context.getSystemService(PowerManager::class.java)
        val batteryExempt = Build.VERSION.SDK_INT < Build.VERSION_CODES.M || power?.isIgnoringBatteryOptimizations(context.packageName) == true
        val waEnabled = bridge.getBoolean("app_enabled_com_whatsapp", false)
        val wabEnabled = bridge.getBoolean("app_enabled_com_whatsapp_w4b", false)
        val stores = bridge.getStringSet("selected_store_ids", emptySet()).orEmpty().sorted()
        val tokenPresent = !session.getString("token", null).isNullOrBlank()
        val waInstalled = packageInstalled(context, "com.whatsapp")
        val wabInstalled = packageInstalled(context, "com.whatsapp.w4b")

        return buildString {
            append("=== ESTADO DEL PUENTE ===")
            append("\nAcceso a notificaciones: ").append(if (access) "ACTIVO" else "NO ACTIVO")
            append("\nKeepAlive: ").append(if (keepAliveActive) "ACTIVO" else "INACTIVO")
            append("\nÚltimo heartbeat: ").append(fmtTime(heartbeat))
            if (heartbeatAge >= 0) append(" (").append(heartbeatAge).append(" s)")
            append("\nSesión/token: ").append(if (tokenPresent) "OK" else "FALTA")
            append("\nBatería sin restricciones: ").append(if (batteryExempt) "Sí" else "NO")
            append("\nÚltimo estado de pantalla: ").append(lastScreenState)
            append("\nWhatsApp instalado: ").append(if (waInstalled) "Sí" else "No")
            append("\nWhatsApp Business instalado: ").append(if (wabInstalled) "Sí" else "No")
            val selectedPackage = bridge.getString("selected_whatsapp_package", "com.whatsapp.w4b") ?: "com.whatsapp.w4b"
            val selectedLabel = if (selectedPackage == "com.whatsapp.w4b") "WhatsApp Business" else "WhatsApp"
            append("\nAplicación seleccionada para responder: ").append(selectedLabel)
            append("\nWhatsApp habilitado: ").append(if (waEnabled) "Sí" else "No")
            append("\nWhatsApp Business habilitado: ").append(if (wabEnabled) "Sí" else "No")
            append("\nModo de selección: UNA SOLA APP")
            append("\nTiendas seleccionadas: ").append(if (stores.isEmpty()) "NINGUNA" else stores.joinToString(","))

            append("\n\n=== ÚLTIMO EVENTO ===")
            if (time <= 0L) {
                append("\nNo hay eventos registrados por el NotificationListener.")
            } else {
                append("\nHora: ").append(fmtTime(time))
                append("\nApp: ").append(app)
                append("\nEstado: ").append(stage.ifBlank { "Sin estado" })
                if (title.isNotBlank()) append("\nConversación: ").append(title)
                if (text.isNotBlank()) append("\nTexto: ").append(text)
                append("\nAcción Responder: ").append(canReply)
                if (detail.isNotBlank()) append("\nDetalle: ").append(detail)
            }

            append("\n\nInterpretación rápida:")
            when {
                !access -> append("\n• Android no está dando acceso al listener. Abre 'Acceso a notificaciones' y activa Phygital Bot.")
                !keepAliveActive || heartbeatAge !in 0..90 -> append("\n• El servicio de mantenimiento no está vivo. Usa 'Reiniciar escucha'.")
                !tokenPresent -> append("\n• Falta sesión móvil válida.")
                !batteryExempt -> append("\n• Android puede suspender el puente al bloquear la pantalla. Usa 'Permitir funcionamiento con pantalla bloqueada'.")
                stores.isEmpty() -> append("\n• No hay tienda seleccionada.")
                waEnabled == wabEnabled -> append("\n• Revisa la selección de aplicación: debe existir exactamente una app activa.")
                time <= 0L -> append("\n• El acceso parece correcto, pero el listener no ha registrado eventos. Reinicia la escucha y manda un mensaje de prueba con WhatsApp cerrado o en segundo plano.")
                else -> append("\n• Hay actividad del listener. Revisa el Estado y Detalle del último evento.")
            }
        }
    }

    fun clear(context: Context) {
        runCatching { context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply() }
    }
}
