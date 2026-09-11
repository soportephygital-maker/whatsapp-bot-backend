package com.phygital.bot

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

class BridgeBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (action != Intent.ACTION_BOOT_COMPLETED &&
            action != Intent.ACTION_LOCKED_BOOT_COMPLETED &&
            action != Intent.ACTION_MY_PACKAGE_REPLACED &&
            action != Intent.ACTION_USER_UNLOCKED) return

        val session = context.getSharedPreferences("phygital_session", Context.MODE_PRIVATE)
        val token = session.getString("token", null)
        val role = session.getString("role", "").orEmpty().trim().lowercase()

        // El teléfono funciona como bot/puente y no debe arrancar con una sesión
        // administrativa. Al actualizar o reiniciar, cualquier sesión distinta de
        // soporte/operador se elimina antes de levantar el servicio.
        if (!token.isNullOrBlank() && role != "operador") {
            session.edit().clear().apply()
            return
        }
        if (token.isNullOrBlank() || role != "operador") return

        val service = Intent(context, BridgeKeepAliveService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(service)
            else context.startService(service)
        } catch (_: Exception) {
        }
    }
}
