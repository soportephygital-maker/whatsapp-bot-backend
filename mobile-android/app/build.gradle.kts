plugins {
    id("com.android.application")
}

android {
    namespace = "com.phygital.bot"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.phygital.bot"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
