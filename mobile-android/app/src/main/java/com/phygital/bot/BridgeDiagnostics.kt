package com.phygital.bot

import android.content.Context
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object BridgeDiagnostics {
    private const val PREFS = "phygital_bridge_diagnostics"

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

    fun snapshot(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val time = prefs.getLong("time", 0L)
        if (time <= 0L) return "Todavía no se ha detectado ninguna notificación de WhatsApp."
        val formatted = SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.getDefault()).format(Date(time))
        val pkg = prefs.getString("package", "").orEmpty()
        val app = when (pkg) {
            "com.whatsapp.w4b" -> "WhatsApp Business"
            "com.whatsapp" -> "WhatsApp"
            else -> pkg.ifBlank { "Desconocida" }
        }
        val stage = prefs.getString("stage", "").orEmpty()
        val detail = prefs.getString("detail", "").orEmpty()
        val title = prefs.getString("title", "").orEmpty()
        val text = prefs.getString("text", "").orEmpty()
        val canReply = if (prefs.contains("can_reply")) {
            if (prefs.getBoolean("can_reply", false)) "Sí" else "No"
        } else "Sin comprobar"
        return buildString {
            append("Hora: ").append(formatted)
            append("\nApp: ").append(app)
            append("\nEstado: ").append(stage.ifBlank { "Sin estado" })
            if (title.isNotBlank()) append("\nConversación: ").append(title)
            if (text.isNotBlank()) append("\nTexto: ").append(text)
            append("\nAcción Responder: ").append(canReply)
            if (detail.isNotBlank()) append("\nDetalle: ").append(detail)
        }
    }

    fun clear(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
    }
}
