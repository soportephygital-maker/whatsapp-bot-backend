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
        versionCode = 2
        versionName = "0.2.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
