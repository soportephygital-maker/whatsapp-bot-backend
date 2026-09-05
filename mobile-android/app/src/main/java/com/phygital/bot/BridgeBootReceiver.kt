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

        // El keep-alive no necesita esperar a que la actividad esté abierta. Se inicia
        // incluso antes de recuperar la sesión para mantener enlazado el listener de
        // notificaciones cuando el teléfono esté bloqueado.
        val service = Intent(context, BridgeKeepAliveService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(service)
            else context.startService(service)
        } catch (_: Exception) {
        }
    }
}
