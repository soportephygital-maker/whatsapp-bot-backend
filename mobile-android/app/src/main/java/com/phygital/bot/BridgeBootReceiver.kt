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
            action != Intent.ACTION_MY_PACKAGE_REPLACED) return

        val token = context.getSharedPreferences("phygital_session", Context.MODE_PRIVATE)
            .getString("token", null)
        if (token.isNullOrBlank()) return

        val service = Intent(context, BridgeKeepAliveService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(service)
            else context.startService(service)
        } catch (_: Exception) {
        }
    }
}
