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
        versionCode = 54
        versionName = "0.6.36"
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

// Build-time hotfix for WhatsApp Business notification metadata.
// Some individual Business chats expose EXTRA_CONVERSATION_TITLE with labels such as
// "Cuenta de empresa". The old heuristic interpreted any title mismatch as a group and
// returned before POST /api/local-bridge/inbound. Also remove the legacy saved-contact
// early return; the backend is responsible for deciding which explicit support contacts
// should bypass the bot.
val patchWhatsAppBridgeSource = tasks.register("patchWhatsAppBridgeSource") {
    doLast {
        val source = file("src/main/java/com/phygital/bot/LocalWhatsAppBridgeService.kt")
        var text = source.readText()
        text = text.replace("        if (isSavedContact(title)) return\n", "")
        val oldGroup = """    private fun looksLikeGroup(notification: Notification, title: String): Boolean {
        val extras = notification.extras
        if (extras.getBoolean(\"android.isGroupConversation\", false)) return true
        val conversationTitle = extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString().orEmpty()
        if (conversationTitle.isNotBlank() && conversationTitle != title) return true
        val info = extras.getCharSequence(Notification.EXTRA_INFO_TEXT)?.toString().orEmpty()
        return info.contains(\"messages from\", ignoreCase = true) || info.contains(\"mensajes de\", ignoreCase = true)
    }"""
        val newGroup = """    private fun looksLikeGroup(notification: Notification, title: String): Boolean {
        // Only trust Android/WhatsApp's explicit group flag. WhatsApp Business may set
        // EXTRA_CONVERSATION_TITLE to labels such as \"Cuenta de empresa\" even for a 1:1 chat.
        return notification.extras.getBoolean(\"android.isGroupConversation\", false)
    }"""
        text = text.replace(oldGroup, newGroup)
        source.writeText(text)
    }
}

tasks.named("preBuild").configure {
    dependsOn(patchWhatsAppBridgeSource)
}

// Android publisher trigger: workflow_run registered on main.
