package com.phygital.bot

import android.Manifest
import android.app.Notification
import android.app.RemoteInput
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.ContactsContract
import android.provider.Settings
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.Normalizer

class LocalWhatsAppBridgeService : NotificationListenerService() {
    private val baseUrl = "https://whatsapp-bot-backend-v2.onrender.com"
    private val allowedPackages = setOf("com.whatsapp", "com.whatsapp.w4b")
    private val sessionPrefsName = "phygital_session"
    private val bridgePrefsName = "phygital_local_bridge"

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (!allowedPackages.contains(sbn.packageName)) return
        val prefs = getSharedPreferences(bridgePrefsName, MODE_PRIVATE)
        val suffix = packageSuffix(sbn.packageName)
        if (!prefs.getBoolean("enabled_$suffix", false)) return
        val storeId = prefs.getInt("store_id_$suffix", -1)
        if (storeId <= 0) return
        val token = getSharedPreferences(sessionPrefsName, MODE_PRIVATE).getString("token", null) ?: return

        val notification = sbn.notification ?: return
        if ((notification.flags and Notification.FLAG_GROUP_SUMMARY) != 0) return

        val extras = notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()?.trim().orEmpty()
        val text = extractText(notification).trim()
        if (text.isBlank()) return

        // Group conversations never enter the bot.
        if (looksLikeGroup(notification, title)) return

        // Contacts already saved in the phone never enter the bot.
        if (isSavedContact(title)) return

        val replyAction = findReplyAction(notification)
        val senderKey = extras.getString(Notification.EXTRA_CONVERSATION_TITLE)
            ?: extras.getCharSequence(Notification.EXTRA_SUB_TEXT)?.toString()
            ?: title
        val deviceId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID) ?: "android-device"

        Thread {
            var outboundMessageId = 0
            try {
                val payload = JSONObject()
                    .put("package_name", sbn.packageName)
                    .put("device_id", deviceId)
                    .put("notification_key", sbn.key)
                    .put("post_time", sbn.postTime)
                    .put("sender", if (title.isBlank()) "Contacto" else title)
                    .put("sender_key", senderKey)
                    .put("text", text)
                    .put("store_id", storeId)
                    .put("is_group", false)
                    .put("can_reply", replyAction != null)
                    .put("metadata", JSONObject()
                        .put("category", notification.category ?: "")
                        .put("saved_contact", false)
                        .put("app_label", if (sbn.packageName == "com.whatsapp.w4b") "WhatsApp Business" else "WhatsApp"))

                val response = JSONObject(request("POST", "/api/local-bridge/inbound", payload.toString(), token))
                val shouldReply = response.optBoolean("should_reply", false)
                val replyText = response.optString("reply_text", "")
                outboundMessageId = response.optInt("outbound_message_id", 0)
                if (shouldReply && replyText.isNotBlank() && replyAction != null && outboundMessageId > 0) {
                    val sent = sendInlineReply(replyAction, replyText)
                    reportDelivery(token, outboundMessageId, sent, sbn.key, if (sent) null else "Android no pudo ejecutar RemoteInput")
                }
            } catch (e: Exception) {
                if (outboundMessageId > 0) {
                    try { reportDelivery(token, outboundMessageId, false, sbn.key, e.message ?: "Error local") } catch (_: Exception) {}
                }
            }
        }.start()
    }

    private fun packageSuffix(packageName: String): String = packageName.replace('.', '_')

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
        if (info.contains("messages from", ignoreCase = true) || info.contains("mensajes de", ignoreCase = true)) return true
        return false
    }

    private fun normalizeName(value: String): String {
        val noAccents = Normalizer.normalize(value.lowercase().trim(), Normalizer.Form.NFD)
            .replace("\\p{M}+".toRegex(), "")
        return noAccents.replace("[^a-z0-9+]".toRegex(), " ").replace("\\s+".toRegex(), " ").trim()
    }

    private fun digits(value: String): String = value.filter { it.isDigit() }

    private fun isSavedContact(sender: String): Boolean {
        if (sender.isBlank()) return false
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            // Fail closed for safety: without contacts permission the bridge must not process chats.
            return true
        }
        val senderName = normalizeName(sender)
        val senderDigits = digits(sender)
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            projection,
            null,
            null,
            null
        )?.use { cursor ->
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
        } catch (_: Exception) {
            false
        }
    }

    private fun reportDelivery(token: String, messageId: Int, sent: Boolean, key: String, error: String?) {
        val body = JSONObject().put("message_id", messageId).put("sent", sent).put("notification_key", key)
        if (error != null) body.put("error", error)
        request("POST", "/api/local-bridge/delivery", body.toString(), token)
    }

    private fun request(method: String, path: String, body: String?, bearer: String): String {
        val connection = (URL(baseUrl + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 20000
            readTimeout = 20000
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Authorization", "Bearer $bearer")
            if (body != null) {
                doOutput = true
                outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
        connection.disconnect()
        if (code !in 200..299) throw IllegalStateException("HTTP $code $text")
        return text
    }
}
