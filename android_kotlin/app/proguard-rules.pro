# Puntea JavaScript („DoinaBridge”): metodele @JavascriptInterface sunt apelate din pagină, nu din Kotlin.
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
