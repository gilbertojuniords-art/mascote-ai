// O app da digital: sem nenhuma biblioteca extra e sem permissão de internet, de propósito.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "app.sexta.digital"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.sexta.digital"
        minSdk = 30          // Android 11: a digital "forte" com chave presa ao chip
        targetSdk = 35
        versionCode = 2
        versionName = "0.2"
    }
    buildTypes {
        release { isMinifyEnabled = false }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
