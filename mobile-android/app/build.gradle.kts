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
        versionCode = 66
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

// Narrow, validated source hotfix for WhatsApp menu replies after several inline
// responses. WhatsApp can keep the local user in EXTRA_PEOPLE_LIST after a
// RemoteInput reply; treating any person named "Tú/You/Me/Yo" as proof that the
// whole notification is self-authored causes later customer replies such as 2/No
// to be discarded before POSTing to the backend.
val patchInboundReplyDetection = tasks.register("patchInboundReplyDetection") {
    doLast {
        val service = file("src/main/java/com/phygital/bot/LocalWhatsAppBridgeService.kt")
        var source = service.readText()

        val oldSelfFilter = """    private fun isSelfAuthoredNotification(title: String, extras: android.os.Bundle): Boolean {
        val normalizedTitle = normalizeName(title)
        if (normalizedTitle in setOf(\"tu\", \"you\", \"me\", \"yo\")) return true
        val people = extras.getParcelableArray(Notification.EXTRA_PEOPLE_LIST)
        if (!people.isNullOrEmpty()) {
            people.forEach { item ->
                val bundle = item as? android.os.Bundle ?: return@forEach
                val name = normalizeName(bundle.getCharSequence(\"name\")?.toString().orEmpty())
                if (name in setOf(\"tu\", \"you\", \"me\", \"yo\")) return true
            }
        }
        return false
    }
"""
        val newSelfFilter = """    private fun isSelfAuthoredNotification(title: String, extras: android.os.Bundle): Boolean {
        // Only the visible notification title is authoritative for an outgoing
        // message. EXTRA_PEOPLE_LIST can retain the local user after RemoteInput
        // and must not cause future incoming customer messages to be discarded.
        val normalizedTitle = normalizeName(title)
        return normalizedTitle in setOf(\"tu\", \"you\", \"me\", \"yo\")
    }
"""
        check(source.contains(oldSelfFilter)) { "Expected self-authored filter block not found" }
        source = source.replace(oldSelfFilter, newSelfFilter)

        val oldGuardBlock = """        if (isRemoteInputHistoryBounce(notification, text)) {
            BridgeDiagnostics.record(this, \"DISCARDED\", \"Rebote de RemoteInput\", sbn.packageName, title, text)
            return
        }
        if (isRecentBotReply(sbn.packageName, text)) {
            BridgeDiagnostics.record(this, \"DISCARDED\", \"Coincide con respuesta reciente del bot\", sbn.packageName, title, text)
            return
        }
        if (isBounceDuplicate(sbn.packageName, sbn.key, text)) {
            BridgeDiagnostics.record(this, \"DISCARDED\", \"Notificación duplicada/rebote\", sbn.packageName, title, text)
            return
        }
        // No descartamos contactos guardados. Un contacto guardado también puede iniciar soporte.
        if (isRapidDuplicate(sbn.packageName, title, text)) {
            BridgeDiagnostics.record(this, \"DISCARDED\", \"Duplicado rápido\", sbn.packageName, title, text)
            return
        }
"""
        val newGuardBlock = """        val normalizedInbound = normalizeName(text)
        val criticalShortReply = normalizedInbound in setOf(
            \"1\", \"2\", \"si\", \"no\", \"listo\", \"finalizar\", \"terminar\", \"cerrar\"
        )
        if (!criticalShortReply && isRemoteInputHistoryBounce(notification, text)) {
            BridgeDiagnostics.record(this, \"DISCARDED\", \"Rebote de RemoteInput\", sbn.packageName, title, text)
            return
        }
        if (!criticalShortReply && isRecentBotReply(sbn.packageName, text)) {
            BridgeDiagnostics.record(this, \"DISCARDED\", \"Coincide con respuesta reciente del bot\", sbn.packageName, title, text)
            return
        }
        if (!criticalShortReply && isBounceDuplicate(sbn.packageName, sbn.key, text)) {
            BridgeDiagnostics.record(this, \"DISCARDED\", \"Notificación duplicada/rebote\", sbn.packageName, title, text)
            return
        }
        // No descartamos contactos guardados. Un contacto guardado también puede iniciar soporte.
        if (!criticalShortReply && isRapidDuplicate(sbn.packageName, title, text)) {
            BridgeDiagnostics.record(this, \"DISCARDED\", \"Duplicado rápido\", sbn.packageName, title, text)
            return
        }
        if (criticalShortReply) {
            BridgeDiagnostics.record(this, \"SHORT_REPLY_ACCEPTED\", \"Respuesta corta prioritaria aceptada\", sbn.packageName, title, text)
        }
"""
        check(source.contains(oldGuardBlock)) { "Expected inbound guard block not found" }
        source = source.replace(oldGuardBlock, newGuardBlock)
        service.writeText(source)
    }
}

tasks.named("preBuild").configure {
    dependsOn(patchInboundReplyDetection)
}

// Diagnostics are implemented directly in Kotlin; this hotfix only narrows two
// exact, validated notification-filter blocks.
// Android publisher trigger: workflow_run registered on main.
