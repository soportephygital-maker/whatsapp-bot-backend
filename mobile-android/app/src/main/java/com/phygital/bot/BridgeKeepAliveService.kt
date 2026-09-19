package com.phygital.bot

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.net.wifi.WifiManager
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
    private var wifiLock: WifiManager.WifiLock? = null
    private var screenReceiverRegistered = false

    private val screenReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                Intent.ACTION_SCREEN_OFF -> {
                    markScreenState("SCREEN_OFF")
                    ensureWakeLock()
                    ensureWifiLock()
                    requestListenerRebind()
                }
                Intent.ACTION_SCREEN_ON -> {
                    markScreenState("SCREEN_ON")
                    ensureWakeLock()
                    ensureWifiLock()
                    requestListenerRebind()
                }
                Intent.ACTION_USER_PRESENT -> {
                    markScreenState("USER_PRESENT")
                    requestListenerRebind()
                }
            }
        }
    }

    private val heartbeat = object : Runnable {
        override fun run() {
            markAlive(true)
            ensureWakeLock()
            ensureWifiLock()
            requestListenerRebind()
            handler.postDelayed(this, 10_000L)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        ensureWakeLock()
        ensureWifiLock()
        registerScreenReceiver()
        markAlive(true)
        requestListenerRebind()
        handler.postDelayed(heartbeat, 10_000L)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ensureWakeLock()
        ensureWifiLock()
        markAlive(true)
        requestListenerRebind()
        return START_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        ensureWakeLock()
        ensureWifiLock()
        requestListenerRebind()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (screenReceiverRegistered) {
            try { unregisterReceiver(screenReceiver) } catch (_: Exception) {}
            screenReceiverRegistered = false
        }
        try {
            if (persistentWakeLock?.isHeld == true) persistentWakeLock?.release()
        } catch (_: Exception) {
        }
        try {
            if (wifiLock?.isHeld == true) wifiLock?.release()
        } catch (_: Exception) {
        }
        persistentWakeLock = null
        wifiLock = null
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

    private fun ensureWifiLock() {
        try {
            if (wifiLock?.isHeld == true) return
            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager ?: return
            wifiLock = wifi.createWifiLock(
                WifiManager.WIFI_MODE_FULL_HIGH_PERF,
                "PhygitalBot:BridgeWifi"
            ).apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (_: Exception) {
        }
    }

    private fun registerScreenReceiver() {
        if (screenReceiverRegistered) return
        try {
            val filter = IntentFilter().apply {
                addAction(Intent.ACTION_SCREEN_OFF)
                addAction(Intent.ACTION_SCREEN_ON)
                addAction(Intent.ACTION_USER_PRESENT)
            }
            registerReceiver(screenReceiver, filter)
            screenReceiverRegistered = true
        } catch (_: Exception) {
        }
    }

    private fun markScreenState(state: String) {
        getSharedPreferences(RUNTIME_PREFS, MODE_PRIVATE).edit()
            .putString("last_screen_state", state)
            .putLong("last_screen_event", System.currentTimeMillis())
            .apply()
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
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val openPending = PendingIntent.getActivity(
            this,
            31001,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val updateIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val updatePending = PendingIntent.getActivity(
            this,
            31002,
            updateIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val settingsIntent = Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.parse("package:$packageName")
        )
        val settingsPending = PendingIntent.getActivity(
            this,
            31003,
            settingsIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
            .setContentTitle("Phygital Bot activo")
            .setContentText("Puente de WhatsApp funcionando incluso con pantalla bloqueada")
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(openPending)
            .addAction(android.R.drawable.stat_notify_sync_noanim, "Actualización", updatePending)
            .addAction(android.R.drawable.ic_menu_manage, "Configuraciones", settingsPending)
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
