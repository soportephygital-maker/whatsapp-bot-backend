plugins {
    id("com.android.application")
}

android {
    namespace = "com.phygital.bot"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.phygital.bot"
        minSdk = 26
        targetSdk = 36
        versionCode = 60
        versionName = "0.6.32"
    }

    signingConfigs {
        create("stable") {
            val keyStorePath = System.getenv("ANDROID_KEYSTORE_PATH")
            if (!keyStorePath.isNullOrBlank()) {
                storeFile = file(keyStorePath)
                storePassword = System.getenv("ANDROID_SIGNING_PASSWORD")
                keyAlias = "phygital-release"
                keyPassword = System.getenv("ANDROID_SIGNING_PASSWORD")
            }
        }
    }

    buildTypes {
        getByName("debug") {
            signingConfig = signingConfigs.getByName("stable")
        }
        getByName("release") {
            signingConfig = signingConfigs.getByName("stable")
            isMinifyEnabled = false
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.core:core:1.15.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:okhttp-dnsoverhttps:4.12.0")
}

val patchBridgeDiagnostics = tasks.register("patchBridgeDiagnostics") {
    doLast {
        val service = file("src/main/java/com/phygital/bot/LocalWhatsAppBridgeService.kt")
        var s = service.readText()
        s = s.replace(
            "        if (!allowedPackages.contains(sbn.packageName)) return\n",
            "        if (!allowedPackages.contains(sbn.packageName)) return\n        BridgeDiagnostics.record(this, \"NOTIFICATION_DETECTED\", packageName = sbn.packageName)\n"
        )
        s = s.replace(
            "        if (!prefs.getBoolean(\"app_enabled_\$suffix\", false)) return\n",
            "        if (!prefs.getBoolean(\"app_enabled_\$suffix\", false)) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Aplicación de WhatsApp desactivada en Phygital Bot\", sbn.packageName); return }\n"
        )
        s = s.replace(
            "        if (selectedStoreIds.isEmpty()) return\n",
            "        if (selectedStoreIds.isEmpty()) { BridgeDiagnostics.record(this, \"DISCARDED\", \"No hay tienda seleccionada\", sbn.packageName); return }\n"
        )
        s = s.replace(
            "        val token = getSharedPreferences(sessionPrefsName, MODE_PRIVATE).getString(\"token\", null) ?: return\n",
            "        val token = getSharedPreferences(sessionPrefsName, MODE_PRIVATE).getString(\"token\", null) ?: run { BridgeDiagnostics.record(this, \"DISCARDED\", \"No hay sesión/token móvil\", sbn.packageName); return }\n"
        )
        s = s.replace(
            "        if ((notification.flags and Notification.FLAG_GROUP_SUMMARY) != 0) return\n",
            "        if ((notification.flags and Notification.FLAG_GROUP_SUMMARY) != 0) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Resumen de grupo de Android\", sbn.packageName); return }\n"
        )
        s = s.replace(
            "            else -> return\n        }\n        if (looksLikeGroup(notification, title)) return\n        if (isSelfAuthoredNotification(title, extras)) return\n        if (isRemoteInputHistoryBounce(notification, text)) return\n        if (isRecentBotReply(sbn.packageName, text)) return\n        if (isBounceDuplicate(sbn.packageName, sbn.key, text)) return\n        if (isSavedContact(title)) return\n        if (isRapidDuplicate(sbn.packageName, title, text)) return\n\n        val replyAction = findReplyAction(notification)\n",
            "            else -> { BridgeDiagnostics.record(this, \"DISCARDED\", \"Notificación sin texto ni imagen\", sbn.packageName, title); return }\n        }\n        BridgeDiagnostics.record(this, \"MESSAGE_PARSED\", \"Notificación de WhatsApp leída\", sbn.packageName, title, text)\n        if (looksLikeGroup(notification, title)) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Detectada como grupo\", sbn.packageName, title, text); return }\n        if (isSelfAuthoredNotification(title, extras)) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Detectada como mensaje propio\", sbn.packageName, title, text); return }\n        if (isRemoteInputHistoryBounce(notification, text)) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Rebote de RemoteInput\", sbn.packageName, title, text); return }\n        if (isRecentBotReply(sbn.packageName, text)) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Coincide con respuesta reciente del bot\", sbn.packageName, title, text); return }\n        if (isBounceDuplicate(sbn.packageName, sbn.key, text)) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Notificación duplicada/rebote\", sbn.packageName, title, text); return }\n        if (isSavedContact(title)) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Contacto guardado\", sbn.packageName, title, text); return }\n        if (isRapidDuplicate(sbn.packageName, title, text)) { BridgeDiagnostics.record(this, \"DISCARDED\", \"Duplicado rápido\", sbn.packageName, title, text); return }\n\n        val replyAction = findReplyAction(notification)\n        BridgeDiagnostics.record(this, \"READY_TO_POST\", \"Listo para enviar al backend\", sbn.packageName, title, text, replyAction != null)\n"
        )
        s = s.replace(
            "                    val response = JSONObject(request(\"POST\", \"/api/local-bridge/inbound\", payload.toString(), token))\n",
            "                    BridgeDiagnostics.record(this, \"POST_SENDING\", \"Enviando /api/local-bridge/inbound\", sbn.packageName, title, text, replyAction != null)\n                    val response = JSONObject(request(\"POST\", \"/api/local-bridge/inbound\", payload.toString(), token))\n"
        )
        s = s.replace(
            "                    outboundMessageId = response.optInt(\"outbound_message_id\", 0)\n",
            "                    outboundMessageId = response.optInt(\"outbound_message_id\", 0)\n                    BridgeDiagnostics.record(this, \"BACKEND_RESPONSE\", \"should_reply=\$shouldReply, ticket_id=\$ticketId, outbound_message_id=\$outboundMessageId\", sbn.packageName, title, text, replyAction != null)\n"
        )
        s = s.replace(
            "                        reportDelivery(token, outboundMessageId, sent, sbn.key, if (sent) null else \"Android no pudo ejecutar RemoteInput\")\n",
            "                        reportDelivery(token, outboundMessageId, sent, sbn.key, if (sent) null else \"Android no pudo ejecutar RemoteInput\")\n                        BridgeDiagnostics.record(this, if (sent) \"REMOTE_INPUT_SENT\" else \"REMOTE_INPUT_FAILED\", if (sent) \"Respuesta enviada a WhatsApp\" else \"Android no pudo ejecutar RemoteInput\", sbn.packageName, title, replyText, replyAction != null)\n"
        )
        s = s.replace(
            "                } catch (e: Exception) {\n                    if (media != null) queuePendingMedia(mediaQueueKey, media!!)\n",
            "                } catch (e: Exception) {\n                    BridgeDiagnostics.record(this, \"ERROR\", e.message ?: \"Error local sin detalle\", sbn.packageName, title, text, replyAction != null)\n                    if (media != null) queuePendingMedia(mediaQueueKey, media!!)\n"
        )
        service.writeText(s)

        val activity = file("src/main/java/com/phygital/bot/MainActivity.kt")
        var a = activity.readText()
        a = a.replace(
            "    private fun showNotificationOnlySettings() {\n        buildBridgeSettingsDialog(JSONArray())\n    }\n",
            "    private fun showNotificationOnlySettings() {\n        buildBridgeSettingsDialog(JSONArray())\n    }\n\n    private fun diagnosticsButton(): Button = Button(this).apply {\n        text = \"Diagnóstico del puente\"\n        setOnClickListener {\n            AlertDialog.Builder(this@MainActivity)\n                .setTitle(\"Diagnóstico WhatsApp\")\n                .setMessage(BridgeDiagnostics.snapshot(this@MainActivity))\n                .setNegativeButton(\"Limpiar\") { _, _ -> BridgeDiagnostics.clear(this@MainActivity) }\n                .setPositiveButton(\"Cerrar\", null)\n                .show()\n        }\n    }\n"
        )
        a = a.replace(
            "        content.addView(notificationAccessButton())\n        content.addView(appSettingsButton())\n        content.addView(updateButton())\n",
            "        content.addView(notificationAccessButton())\n        content.addView(appSettingsButton())\n        content.addView(diagnosticsButton())\n        content.addView(updateButton())\n"
        )
        activity.writeText(a)
    }
}

tasks.named("preBuild").configure {
    dependsOn(patchBridgeDiagnostics)
}

// Android publisher trigger: workflow_run registered on main.
