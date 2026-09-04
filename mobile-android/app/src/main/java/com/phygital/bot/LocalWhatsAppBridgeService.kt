package com.phygital.bot

import android.Manifest
import android.app.Notification
import android.app.RemoteInput
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.drawable.BitmapDrawable
import android.net.Uri
import android.os.PowerManager
import android.provider.ContactsContract
import android.provider.Settings
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.URLEncoder
import java.security.MessageDigest
import java.text.Normalizer

class LocalWhatsAppBridgeService : NotificationListenerService() {
    private val baseUrl = "https://whatsapp-bot-backend-142e.onrender.com"
    private val allowedPackages = setOf("com.whatsapp", "com.whatsapp.w4b")
    private val sessionPrefsName = "phygital_session"
    private val bridgePrefsName = "phygital_local_bridge"
    private val loopGuardPrefsName = "phygital_loop_guard"
    private val bounceWindowMs = 45_000L
    private val duplicateWindowMs = 12_000L
    private val maxReplyHistory = 8
    private val maxMediaBytes = 15 * 1024 * 1024
    @Volatile private var manualPollRunning = false

    private data class MediaCandidate(
        val bytes: ByteArray,
        val filename: String,
        val contentType: String,
        val source: String,
    )

    override fun onListenerConnected() {
        super.onListenerConnected()
        startManualReplyPolling()
    }

    override fun onListenerDisconnected() {
        manualPollRunning = false
        try { requestRebind(android.content.ComponentName(this, LocalWhatsAppBridgeService::class.java)) } catch (_: Exception) {}
        super.onListenerDisconnected()
    }

    override fun onDestroy() {
        manualPollRunning = false
        super.onDestroy()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        startManualReplyPolling()
        if (!allowedPackages.contains(sbn.packageName)) return
        val prefs = getSharedPreferences(bridgePrefsName, MODE_PRIVATE)
        val suffix = packageSuffix(sbn.packageName)
        if (!prefs.getBoolean("app_enabled_$suffix", false)) return
        val selectedStoreIds = prefs.getStringSet("selected_store_ids", emptySet())
            ?.mapNotNull { it.toIntOrNull() }
            ?.distinct()
            ?: emptyList()
        if (selectedStoreIds.isEmpty()) return
        val token = getSharedPreferences(sessionPrefsName, MODE_PRIVATE).getString("token", null) ?: return

        val notification = sbn.notification ?: return
        if ((notification.flags and Notification.FLAG_GROUP_SUMMARY) != 0) return

        val extras = notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()?.trim().orEmpty()
        val media = extractMediaCandidate(notification, sbn.postTime)
        val rawText = extractText(notification).trim()
        val text = when {
            rawText.isNotBlank() -> rawText
            media != null -> "[Imagen recibida]"
            else -> return
        }
        if (looksLikeGroup(notification, title)) return
        if (isSelfAuthoredNotification(title, extras)) return
        if (isRemoteInputHistoryBounce(notification, text)) return
        if (isRecentBotReply(sbn.packageName, text)) return
        if (isBounceDuplicate(sbn.packageName, sbn.key, text)) return
        if (isSavedContact(title)) return
        if (isRapidDuplicate(sbn.packageName, title, text)) return

        val replyAction = findReplyAction(notification)
        val senderKey = extras.getString(Notification.EXTRA_CONVERSATION_TITLE)
            ?: extras.getCharSequence(Notification.EXTRA_SUB_TEXT)?.toString()
            ?: title
        val deviceId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID) ?: "android-device"

        Thread {
            withWakeLock("inbound", 60_000L) {
                var outboundMessageId = 0
                try {
                    val storesJson = JSONArray()
                    selectedStoreIds.forEach { storesJson.put(it) }
                    val metadata = JSONObject()
                        .put("category", notification.category ?: "")
                        .put("saved_contact", false)
                        .put("contacts_permission", checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED)
                        .put("bounce_filter", "v2")
                        .put("media_capture", if (media != null) "available" else "none")
                        .put("media_source", media?.source ?: "")
                        .put("app_label", if (sbn.packageName == "com.whatsapp.w4b") "WhatsApp Business" else "WhatsApp")
                    val payload = JSONObject()
                        .put("package_name", sbn.packageName)
                        .put("device_id", deviceId)
                        .put("notification_key", sbn.key)
                        .put("post_time", sbn.postTime)
                        .put("sender", if (title.isBlank()) "Contacto" else title)
                        .put("sender_key", senderKey)
                        .put("text", text)
                        .put("selected_store_ids", storesJson)
                        .put("is_group", false)
                        .put("can_reply", replyAction != null)
                        .put("metadata", metadata)

                    val response = JSONObject(request("POST", "/api/local-bridge/inbound", payload.toString(), token))
                    val shouldReply = response.optBoolean("should_reply", false)
                    val replyText = response.optString("reply_text", "")
                    val ticketId = response.optInt("ticket_id", 0)
                    outboundMessageId = response.optInt("outbound_message_id", 0)

                    if (media != null && ticketId > 0) {
                        tryUploadMedia(token, ticketId, media)
                    }

                    if (shouldReply && replyText.isNotBlank() && replyAction != null && outboundMessageId > 0) {
                        rememberBotReply(sbn.packageName, replyText)
                        val sent = sendInlineReply(replyAction, replyText)
                        if (!sent) clearRememberedBotReply(sbn.packageName, replyText)
                        reportDelivery(token, outboundMessageId, sent, sbn.key, if (sent) null else "Android no pudo ejecutar RemoteInput")
                    }
                } catch (e: Exception) {
                    if (outboundMessageId > 0) {
                        try { reportDelivery(token, outboundMessageId, false, sbn.key, e.message ?: "Error local") } catch (_: Exception) {}
                    }
                }
            }
        }.start()
    }

    private fun tryUploadMedia(token: String, ticketId: Int, media: MediaCandidate) {
        if (media.bytes.isEmpty() || media.bytes.size > maxMediaBytes) return
        val digest = MessageDigest.getInstance("SHA-256").digest(media.bytes).joinToString("") { "%02x".format(it) }
        val prefs = getSharedPreferences(loopGuardPrefsName, MODE_PRIVATE)
        val key = "media_uploaded_${ticketId}_$digest"
        if (prefs.getBoolean(key, false)) return
        try {
            NetworkClient.uploadFile(
                path = "/api/tickets/$ticketId/adjuntos",
                bearer = token,
                bytes = media.bytes,
                filename = media.filename,
                contentType = media.contentType,
                fields = emptyMap(),
            )
            prefs.edit().putBoolean(key, true).apply()
        } catch (_: Exception) {
            // The chat itself must continue even if WhatsApp does not grant access to media bytes.
        }
    }

    private fun extractMediaCandidate(notification: Notification, postTime: Long): MediaCandidate? {
        extractMessagingStyleMedia(notification, postTime)?.let { return it }
        extractPictureExtra(notification, postTime)?.let { return it }
        extractLargeIconPreview(notification, postTime)?.let { return it }
        return null
    }

    private fun extractMessagingStyleMedia(notification: Notification, postTime: Long): MediaCandidate? {
        val messaging = notification.extras.getParcelableArray(Notification.EXTRA_MESSAGES) ?: return null
        for (item in messaging.reversed()) {
            val bundle = item as? android.os.Bundle ?: continue
            val mime = bundle.getString("type")?.trim().orEmpty()
            val uri = when (val raw = bundle.get("uri")) {
                is Uri -> raw
                is String -> runCatching { Uri.parse(raw) }.getOrNull()
                else -> null
            } ?: continue
            if (!mime.startsWith("image/")) continue
            readUriBytes(uri)?.let { bytes ->
                val extension = extensionForMime(mime)
                return MediaCandidate(bytes, "whatsapp-${postTime}.$extension", mime, "messaging_style_uri")
            }
        }
        return null
    }

    private fun extractPictureExtra(notification: Notification, postTime: Long): MediaCandidate? {
        @Suppress("DEPRECATION")
        val bitmap = notification.extras.getParcelable(Notification.EXTRA_PICTURE) as? Bitmap ?: return null
        val bytes = bitmapToJpeg(bitmap) ?: return null
        return MediaCandidate(bytes, "whatsapp-${postTime}.jpg", "image/jpeg", "notification_picture")
    }

    private fun extractLargeIconPreview(notification: Notification, postTime: Long): MediaCandidate? {
        val icon = notification.getLargeIcon() ?: return null
        val drawable = runCatching { icon.loadDrawable(this) }.getOrNull() ?: return null
        val bitmap = (drawable as? BitmapDrawable)?.bitmap ?: return null
        if (bitmap.width < 96 || bitmap.height < 96) return null
        val bytes = bitmapToJpeg(bitmap) ?: return null
        return MediaCandidate(bytes, "whatsapp-preview-${postTime}.jpg", "image/jpeg", "large_icon_preview")
    }

    private fun readUriBytes(uri: Uri): ByteArray? {
        return try {
            contentResolver.openInputStream(uri)?.use { input ->
                val out = ByteArrayOutputStream()
                val buffer = ByteArray(32 * 1024)
                var total = 0
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) break
                    total += read
                    if (total > maxMediaBytes) return null
                    out.write(buffer, 0, read)
                }
                out.toByteArray()
            }
        } catch (_: Exception) { null }
    }

    private fun bitmapToJpeg(bitmap: Bitmap): ByteArray? = try {
        val out = ByteArrayOutputStream()
        if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 90, out)) null else out.toByteArray()
    } catch (_: Exception) { null }

    private fun extensionForMime(mime: String): String = when (mime.lowercase()) {
        "image/png" -> "png"
        "image/webp" -> "webp"
        "image/gif" -> "gif"
        "image/heic", "image/heif" -> "heic"
        else -> "jpg"
    }

    private fun isSelfAuthoredNotification(title: String, extras: android.os.Bundle): Boolean {
        val normalizedTitle = normalizeName(title)
        if (normalizedTitle in setOf("tu", "you", "me", "yo")) return true

        val people = extras.getParcelableArray(Notification.EXTRA_PEOPLE_LIST)
        if (!people.isNullOrEmpty()) {
            people.forEach { item ->
                val bundle = item as? android.os.Bundle ?: return@forEach
                val name = normalizeName(bundle.getCharSequence("name")?.toString().orEmpty())
                if (name in setOf("tu", "you", "me", "yo")) return true
            }
        }
        return false
    }

    private fun isRemoteInputHistoryBounce(notification: Notification, text: String): Boolean {
        val candidate = normalizedMessage(text)
        val history = notification.extras.getCharSequenceArray(Notification.EXTRA_REMOTE_INPUT_HISTORY) ?: return false
        return history.any { item ->
            val sent = normalizedMessage(item?.toString().orEmpty())
            sent.isNotBlank() && (candidate == sent ||
                (sent.length >= 12 && candidate.contains(sent)) ||
                (candidate.length >= 12 && sent.contains(candidate)))
        }
    }

    private fun withWakeLock(tag: String, timeoutMs: Long, block: () -> Unit) {
        val power = getSystemService(PowerManager::class.java)
        val wakeLock = power?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PhygitalBot:$tag")
        try {
            wakeLock?.setReferenceCounted(false)
            wakeLock?.acquire(timeoutMs)
            block()
        } finally {
            if (wakeLock?.isHeld == true) {
                try { wakeLock.release() } catch (_: Exception) {}
            }
        }
    }

    private fun startManualReplyPolling() {
        if (manualPollRunning) return
        manualPollRunning = true
        Thread {
            while (manualPollRunning) {
                try {
                    withWakeLock("manual-poll", 30_000L) { pollManualReplies() }
                } catch (_: Exception) {
                }
                try { Thread.sleep(2500) } catch (_: InterruptedException) {}
            }
        }.start()
    }

    private fun notificationTitle(sbn: StatusBarNotification): String =
        sbn.notification?.extras?.getCharSequence(Notification.EXTRA_TITLE)?.toString()?.trim().orEmpty()

    private fun normalizeConversationLabel(value: String): String =
        normalizeName(value).removePrefix("52 ").removePrefix("521 ").trim()

    private fun findActiveConversationNotification(notificationKey: String, packageName: String, senderDisplay: String): StatusBarNotification? {
        val active = try { activeNotifications?.toList().orEmpty() } catch (_: Exception) { emptyList() }
        active.firstOrNull { it.key == notificationKey && it.packageName == packageName }?.let { return it }

        val wantedLabel = normalizeConversationLabel(senderDisplay)
        val wantedDigits = digits(senderDisplay)
        return active
            .asSequence()
            .filter { it.packageName == packageName }
            .filter { findReplyAction(it.notification ?: return@filter false) != null }
            .firstOrNull { candidate ->
                val title = notificationTitle(candidate)
                val titleLabel = normalizeConversationLabel(title)
                val titleDigits = digits(title)
                (wantedLabel.isNotBlank() && titleLabel == wantedLabel) ||
                    (wantedDigits.length >= 7 && titleDigits.length >= 7 &&
                        (wantedDigits.endsWith(titleDigits.takeLast(10)) || titleDigits.endsWith(wantedDigits.takeLast(10))))
            }
    }

    private fun pollManualReplies() {
        val bridgePrefs = getSharedPreferences(bridgePrefsName, MODE_PRIVATE)
        val anyEnabled = allowedPackages.any { bridgePrefs.getBoolean("app_enabled_${packageSuffix(it)}", false) }
        if (!anyEnabled) return
        val token = getSharedPreferences(sessionPrefsName, MODE_PRIVATE).getString("token", null) ?: return
        val deviceId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID) ?: return
        val encodedDevice = URLEncoder.encode(deviceId, "UTF-8")
        val response = request("GET", "/api/local-bridge/manual-pending?device_id=$encodedDevice", null, token)
        val rows = JSONArray(response)
        for (i in 0 until rows.length()) {
            val row = rows.optJSONObject(i) ?: continue
            val messageId = row.optInt("message_id", 0)
            val notificationKey = row.optString("notification_key", "")
            val packageName = row.optString("package_name", "")
            val senderDisplay = row.optString("sender_display", "")
            val text = row.optString("text", "").trim()
            if (messageId <= 0 || text.isBlank() || !allowedPackages.contains(packageName)) continue

            val active = findActiveConversationNotification(notificationKey, packageName, senderDisplay)
            if (active == null) continue
            val action = findReplyAction(active.notification ?: continue)
            if (action == null) {
                reportDelivery(token, messageId, false, active.key, "La notificación activa no permite respuesta remota")
                continue
            }

            rememberBotReply(packageName, text)
            val sent = sendInlineReply(action, text)
            if (!sent) clearRememberedBotReply(packageName, text)
            reportDelivery(token, messageId, sent, active.key, if (sent) null else "Android no pudo ejecutar RemoteInput manual")
        }
    }

    private fun packageSuffix(packageName: String): String = packageName.replace('.', '_')

    private fun guardKey(packageName: String, kind: String): String = "${kind}_${packageSuffix(packageName)}"

    private fun normalizedMessage(value: String): String = value.trim().replace("\\s+".toRegex(), " ")

    private fun rememberBotReply(packageName: String, text: String) {
        val prefs = getSharedPreferences(loopGuardPrefsName, MODE_PRIVATE)
        val now = System.currentTimeMillis()
        val normalized = normalizedMessage(text)
        val historyKey = guardKey(packageName, "reply_history")
        val history = try { JSONArray(prefs.getString(historyKey, "[]") ?: "[]") } catch (_: Exception) { JSONArray() }
        val fresh = JSONArray()
        fresh.put(JSONObject().put("text", normalized).put("time", now))
        for (i in 0 until history.length()) {
            if (fresh.length() >= maxReplyHistory) break
            val row = history.optJSONObject(i) ?: continue
            val rowText = row.optString("text", "")
            val rowTime = row.optLong("time", 0L)
            if (rowText.isBlank() || now - rowTime !in 0..bounceWindowMs) continue
            if (rowText == normalized) continue
            fresh.put(JSONObject().put("text", rowText).put("time", rowTime))
        }
        prefs.edit()
            .putString(guardKey(packageName, "reply_text"), normalized)
            .putLong(guardKey(packageName, "reply_time"), now)
            .putString(historyKey, fresh.toString())
            .apply()
    }

    private fun clearRememberedBotReply(packageName: String, text: String) {
        val prefs = getSharedPreferences(loopGuardPrefsName, MODE_PRIVATE)
        val normalized = normalizedMessage(text)
        if (prefs.getString(guardKey(packageName, "reply_text"), null) == normalized) {
            prefs.edit()
                .remove(guardKey(packageName, "reply_text"))
                .remove(guardKey(packageName, "reply_time"))
                .apply()
        }
    }

    private fun isRecentBotReply(packageName: String, text: String): Boolean {
        val prefs = getSharedPreferences(loopGuardPrefsName, MODE_PRIVATE)
        val candidate = normalizedMessage(text)
        val now = System.currentTimeMillis()
        val historyKey = guardKey(packageName, "reply_history")
        val history = try { JSONArray(prefs.getString(historyKey, "[]") ?: "[]") } catch (_: Exception) { JSONArray() }

        for (i in 0 until history.length()) {
            val row = history.optJSONObject(i) ?: continue
            val sent = row.optString("text", "")
            val sentAt = row.optLong("time", 0L)
            if (sent.isBlank() || now - sentAt !in 0..bounceWindowMs) continue
            if (candidate == sent) return true
            if (sent.length >= 12 && candidate.contains(sent)) return true
            if (candidate.length >= 12 && sent.contains(candidate)) return true
        }

        val sentText = prefs.getString(guardKey(packageName, "reply_text"), null) ?: return false
        val sentAt = prefs.getLong(guardKey(packageName, "reply_time"), 0L)
        if (now - sentAt !in 0..bounceWindowMs) return false
        return candidate == sentText ||
            (sentText.length >= 12 && candidate.contains(sentText)) ||
            (candidate.length >= 12 && sentText.contains(candidate))
    }

    private fun isBounceDuplicate(packageName: String, notificationKey: String, text: String): Boolean {
        val prefs = getSharedPreferences(loopGuardPrefsName, MODE_PRIVATE)
        val now = System.currentTimeMillis()
        val candidate = normalizedMessage(text)
        val key = guardKey(packageName, "bounce_text")
        val notificationKeyPref = guardKey(packageName, "bounce_notification_key")
        val timeKey = guardKey(packageName, "bounce_time")
        val previousText = prefs.getString(key, null)
        val previousNotificationKey = prefs.getString(notificationKeyPref, null)
        val previousAt = prefs.getLong(timeKey, 0L)
        val recent = now - previousAt in 0..duplicateWindowMs
        val sameText = previousText == candidate
        val sameNotification = previousNotificationKey == notificationKey
        if (recent && sameText && sameNotification) return true
        if (recent && sameText) return true
        prefs.edit()
            .putString(key, candidate)
            .putString(notificationKeyPref, notificationKey)
            .putLong(timeKey, now)
            .apply()
        return false
    }

    private fun isRapidDuplicate(packageName: String, sender: String, text: String): Boolean {
        val prefs = getSharedPreferences(loopGuardPrefsName, MODE_PRIVATE)
        val fingerprint = "$packageName|${normalizedMessage(sender)}|${normalizedMessage(text)}"
        val key = guardKey(packageName, "inbound_fingerprint")
        val timeKey = guardKey(packageName, "inbound_time")
        val previous = prefs.getString(key, null)
        val previousAt = prefs.getLong(timeKey, 0L)
        val now = System.currentTimeMillis()
        if (previous == fingerprint && now - previousAt in 0..duplicateWindowMs) return true
        prefs.edit().putString(key, fingerprint).putLong(timeKey, now).apply()
        return false
    }

    private fun extractText(notification: Notification): String {
        val extras = notification.extras
        val messaging = extras.getParcelableArray(Notification.EXTRA_MESSAGES)
        if (!messaging.isNullOrEmpty()) {
            val latest = messaging.lastOrNull()
            if (latest is android.os.Bundle) {
                val messageText = latest.getCharSequence("text")?.toString()
                if (!messageText.isNullOrBlank()) return messageText
            }
        }
        return extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString()
            ?: extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()
            ?: ""
    }

    private fun looksLikeGroup(notification: Notification, title: String): Boolean {
        val extras = notification.extras
        if (extras.getBoolean("android.isGroupConversation", false)) return true
        val conversationTitle = extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString().orEmpty()
        if (conversationTitle.isNotBlank() && conversationTitle != title) return true
        val info = extras.getCharSequence(Notification.EXTRA_INFO_TEXT)?.toString().orEmpty()
        return info.contains("messages from", ignoreCase = true) || info.contains("mensajes de", ignoreCase = true)
    }

    private fun normalizeName(value: String): String {
        val noAccents = Normalizer.normalize(value.lowercase().trim(), Normalizer.Form.NFD)
            .replace("\\p{M}+".toRegex(), "")
        return noAccents.replace("[^a-z0-9+]".toRegex(), " ").replace("\\s+".toRegex(), " ").trim()
    }

    private fun digits(value: String): String = value.filter { it.isDigit() }

    private fun isSavedContact(sender: String): Boolean {
        if (sender.isBlank()) return false
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) return false
        val senderName = normalizeName(sender)
        val senderDigits = digits(sender)
        val projection = arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.NUMBER)
        contentResolver.query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI, projection, null, null, null)?.use { cursor ->
            val nameIx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val numberIx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (cursor.moveToNext()) {
                val name = if (nameIx >= 0) cursor.getString(nameIx).orEmpty() else ""
                val number = if (numberIx >= 0) cursor.getString(numberIx).orEmpty() else ""
                if (name.isNotBlank() && normalizeName(name) == senderName) return true
                val contactDigits = digits(number)
                if (senderDigits.length >= 7 && contactDigits.length >= 7 &&
                    (senderDigits.endsWith(contactDigits.takeLast(10)) || contactDigits.endsWith(senderDigits.takeLast(10)))) return true
            }
        }
        return false
    }

    private fun findReplyAction(notification: Notification): Notification.Action? =
        notification.actions?.firstOrNull { !it.remoteInputs.isNullOrEmpty() }

    private fun sendInlineReply(action: Notification.Action, replyText: String): Boolean {
        val remoteInputs = action.remoteInputs ?: return false
        if (remoteInputs.isEmpty()) return false
        val intent = Intent()
        val results = android.os.Bundle()
        remoteInputs.forEach { input -> results.putCharSequence(input.resultKey, replyText) }
        RemoteInput.addResultsToIntent(remoteInputs, intent, results)
        return try {
            action.actionIntent.send(this, 0, intent)
            true
        } catch (_: Exception) { false }
    }

    private fun reportDelivery(token: String, messageId: Int, sent: Boolean, key: String, error: String?) {
        val body = JSONObject().put("message_id", messageId).put("sent", sent).put("notification_key", key)
        if (error != null) body.put("error", error)
        request("POST", "/api/local-bridge/delivery", body.toString(), token)
    }

    private fun request(method: String, path: String, body: String?, bearer: String): String =
        NetworkClient.request(method, path, body, bearer)
}
