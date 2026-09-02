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
import android.os.PowerManager
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
    private var persistentWakeLock: PowerManager.WakeLock? = null

    private val heartbeat = object : Runnable {
        override fun run() {
            markAlive(true)
            ensureWakeLock()
            requestListenerRebind()
            handler.postDelayed(this, 20_000L)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        ensureWakeLock()
        markAlive(true)
        requestListenerRebind()
        handler.postDelayed(heartbeat, 20_000L)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ensureWakeLock()
        markAlive(true)
        requestListenerRebind()
        return START_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        // El servicio es independiente de la actividad. Mantener el listener enlazado
        // aunque el usuario quite la app de recientes o la pantalla esté bloqueada.
        ensureWakeLock()
        requestListenerRebind()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        try {
            if (persistentWakeLock?.isHeld == true) persistentWakeLock?.release()
        } catch (_: Exception) {
        }
        persistentWakeLock = null
        markAlive(false)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun ensureWakeLock() {
        try {
            if (persistentWakeLock?.isHeld == true) return
            val power = getSystemService(PowerManager::class.java) ?: return
            persistentWakeLock = power.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "PhygitalBot:BridgeKeepAlive"
            ).apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (_: Exception) {
        }
    }

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
            .setContentText("Puente de WhatsApp funcionando incluso con pantalla bloqueada")
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
