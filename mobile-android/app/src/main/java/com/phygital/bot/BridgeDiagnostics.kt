package com.phygital.bot

import android.content.ComponentName
import android.content.Context
import android.provider.Settings
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
            append("\nWhatsApp instalado: ").append(if (waInstalled) "Sí" else "No")
            append("\nWhatsApp Business instalado: ").append(if (wabInstalled) "Sí" else "No")
            append("\nWhatsApp habilitado en Phygital: ").append(if (waEnabled) "Sí" else "No")
            append("\nWhatsApp Business habilitado en Phygital: ").append(if (wabEnabled) "Sí" else "No")
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
                stores.isEmpty() -> append("\n• No hay tienda seleccionada.")
                !waEnabled && !wabEnabled -> append("\n• Ninguna app de WhatsApp está habilitada en Phygital Bot.")
                time <= 0L -> append("\n• El acceso parece correcto, pero el listener no ha registrado eventos. Reinicia la escucha y manda un mensaje de prueba con WhatsApp cerrado o en segundo plano.")
                else -> append("\n• Hay actividad del listener. Revisa el Estado y Detalle del último evento.")
            }
        }
    }

    fun clear(context: Context) {
        runCatching { context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply() }
    }
}
