// DoinaDress – aplicația Android nativă (Kotlin). Cele 4 variante se construiesc deodată (python src/build_kotlin.py):
//   familieRealist  ro.doinadress.doinadress          „DoinaDress”
//   familieSimplu   ro.doinadress.doinadress.simplu   „DoinaDress Simplu”
//   magazinRealist  ro.doinadress.magazin             „DoinaDress Magazin”
//   magazinSimplu   ro.doinadress.magazin.simplu      „DoinaDress Magazin Simplu”
// Compatibil Android 5.0 (API 21) … 16 (API 36); orice ecran: telefon, tabletă, pliabil, Chromebook, ferestre multiple.
// Pagina web a fiecărei variante stă în app/src/<variantă>/assets/web (generată, nu se pune în git).
// Aceleași id-uri ca aplicația Flutter: APK-ul Kotlin o actualizează pe loc și păstrează modelele salvate.
plugins {
    id("com.android.application")
}

android {
    namespace = "ro.doinadress"
    compileSdk = 36

    defaultConfig {
        minSdk = 21                  // Android 5.0+ (pagina cere WebView actualizat — vezi verificarea din MainActivity)
        targetSdk = 36
        versionCode = 2              // > 1 (aplicația Flutter), ca să se instaleze peste ea
        versionName = "1.1.0"
    }

    flavorDimensions += listOf("public", "corp")
    productFlavors {
        create("familie") { dimension = "public"; applicationId = "ro.doinadress.doinadress" }
        create("magazin") { dimension = "public"; applicationId = "ro.doinadress.magazin" }
        create("realist") { dimension = "corp" }
        create("simplu") { dimension = "corp"; applicationIdSuffix = ".simplu" }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("debug")   // aceeași cheie ca aplicația Flutter (actualizare pe loc)
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    androidResources {
        noCompress += listOf("pack")      // mh.pack (14 MB) se citește direct, fără dezarhivare
    }
}

// numele aplicației, din combinația de variante
androidComponents {
    onVariants { v ->
        val f = v.productFlavors.toMap()
        val label = (if (f["public"] == "magazin") "DoinaDress Magazin" else "DoinaDress") +
            (if (f["corp"] == "simplu") " Simplu" else "")
        v.manifestPlaceholders.put("appLabel", label)
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.16.0")
}
