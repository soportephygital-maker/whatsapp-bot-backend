package com.phygital.bot

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.ComponentName
import android.content.Intent
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.service.notification.NotificationListenerService

class BridgeKeepAliveService : Service() {
    companion object {
        const val CHANNEL_ID = "phygital_bridge_keepalive"
        const val NOTIFICATION_ID = 31001
        const val RUNTIME_PREFS = "phygital_bridge_runtime"
        const val HEARTBEAT_KEY = "keep_alive_last_seen"
        const val ACTIVE_KEY = "keep_alive_active"
    }

    private val handler = Handler(Looper.getMainLooper())
    private val heartbeat = object : Runnable {
        override fun run() {
            markAlive(true)
            requestListenerRebind()
            handler.postDelayed(this, 60_000L)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        markAlive(true)
        requestListenerRebind()
        handler.postDelayed(heartbeat, 60_000L)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        markAlive(true)
        requestListenerRebind()
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        markAlive(false)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Puente de WhatsApp activo",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Mantiene activo el puente local de Phygital Bot cuando la pantalla está apagada"
            setShowBadge(false)
        }
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val openIntent = Intent(this, AdminGateActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pending = PendingIntent.getActivity(
            this,
            31001,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
            .setContentTitle("Phygital Bot activo")
            .setContentText("Puente de WhatsApp funcionando en segundo plano")
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(pending)
            .build()
    }

    private fun markAlive(active: Boolean) {
        getSharedPreferences(RUNTIME_PREFS, MODE_PRIVATE).edit()
            .putBoolean(ACTIVE_KEY, active)
            .putLong(HEARTBEAT_KEY, System.currentTimeMillis())
            .apply()
    }

    private fun requestListenerRebind() {
        try {
            val enabled = Settings.Secure.getString(contentResolver, "enabled_notification_listeners").orEmpty()
            val component = ComponentName(this, LocalWhatsAppBridgeService::class.java)
            if (enabled.split(":").any { it.equals(component.flattenToString(), ignoreCase = true) }) {
                NotificationListenerService.requestRebind(component)
            }
        } catch (_: Exception) {
        }
    }
}
