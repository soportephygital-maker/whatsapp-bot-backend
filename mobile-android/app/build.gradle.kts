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
        versionCode = 6
        versionName = "0.4.1"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.core:core:1.15.0")
}
