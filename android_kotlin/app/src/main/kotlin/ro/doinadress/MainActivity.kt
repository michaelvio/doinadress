// DoinaDress – cabina de probă 3D, aplicația Android nativă (Kotlin).
//
// Aplicația web (assets/web, generată de src/build.py) se afișează într-un WebView. Cererile către
// http://127.0.0.1:47811/ sunt servite direct din assets, fără server: aceeași adresă ca în versiunea Flutter,
// deci baza de modele salvată în IndexedDB se păstrează și după actualizare. Puntea „DoinaBridge” primește
// fișierele pe care pagina vrea să le salveze (export bază, imagini) și textul de partajat (lista de cumpărături).
//
// Compatibilitate: Android 5.0 (API 21) … 16 (API 36), telefoane, tablete, pliabile, Chromebook, ferestre multiple.
// Doar API-ul Android + androidx.core (fără androidx.activity, care cere Android 6.0+).
package ro.doinadress

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.res.ColorStateList
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import android.util.Base64
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import android.window.OnBackInvokedDispatcher
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import org.json.JSONObject
import java.io.File
import java.io.IOException

private const val ORIGIN = "http://127.0.0.1:47811"
private const val MIN_CHROME = 89          // pagina folosește module ES cu „importmap” (Chromium 89+) și WebGL 2
private const val REQ_FILES = 7
private val BG = Color.parseColor("#14171D")
private val GOLD = Color.parseColor("#D4A35A")
private val MUTED = Color.parseColor("#9AA2B1")

class MainActivity : Activity() {
    private var web: WebView? = null
    private lateinit var root: FrameLayout
    private lateinit var loading: View
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // pagina desenează sub barele sistemului; marginile se adaugă din insets (la fel pe Android 5 și pe 15+)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        @Suppress("DEPRECATION")
        if (Build.VERSION.SDK_INT < 35) { window.statusBarColor = BG; window.navigationBarColor = BG }
        WindowInsetsControllerCompat(window, window.decorView).apply {
            isAppearanceLightStatusBars = false; isAppearanceLightNavigationBars = false
        }
        root = FrameLayout(this).apply { setBackgroundColor(BG) }
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val b = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
            v.setPadding(b.left, b.top, b.right, b.bottom)
            WindowInsetsCompat.CONSUMED
        }
        setContentView(root)
        registerBack()

        // WebView-ul vine din Play Store (Android System WebView / Chrome); unul vechi nu poate rula scena 3D
        val chrome = try {
            Regex("""Chrome/(\d+)""").find(WebSettings.getDefaultUserAgent(this))?.groupValues?.get(1)?.toInt() ?: 0
        } catch (e: Exception) { -1 }
        if (chrome < MIN_CHROME) { showWebViewUpdate(chrome); return }

        if (applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0) WebView.setWebContentsDebuggingEnabled(true)
        val w = WebView(this).apply {
            setBackgroundColor(BG)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true           // localStorage + IndexedDB (baza de modele, catalogul)
            @Suppress("DEPRECATION")
            settings.databaseEnabled = true
            settings.mediaPlaybackRequiresUserGesture = true
            settings.allowFileAccess = false
            settings.textZoom = 100                     // aspectul paginii nu se strică dacă telefonul are text mărit
            addJavascriptInterface(Bridge(), "DoinaBridge")
            webViewClient = Client()
            webChromeClient = Chrome()
        }
        web = w
        loading = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(BG)
            addView(ProgressBar(this@MainActivity).apply { indeterminateTintList = ColorStateList.valueOf(GOLD) })
            addView(TextView(this@MainActivity).apply {
                text = "Se încarcă cabina 3D…"; setTextColor(MUTED); setPadding(0, dp(14), 0, 0)
            }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT))
        }
        root.addView(w, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        root.addView(loading, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        if (savedInstanceState == null || w.restoreState(savedInstanceState) == null) w.loadUrl("$ORIGIN/index.html")
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    /** Ecran pentru WebView prea vechi: explică și deschide Magazin Play la actualizare. */
    private fun showWebViewUpdate(version: Int) {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setPadding(dp(28), dp(28), dp(28), dp(28))
            addView(TextView(this@MainActivity).apply {
                text = "Cabina 3D are nevoie de o versiune mai nouă de „Android System WebView”" +
                    (if (Build.VERSION.SDK_INT in 24..28) " (pe acest telefon: Google Chrome)" else "") + "." +
                    (if (version > 0) "\n\nVersiunea actuală: $version, necesar: $MIN_CHROME sau mai nouă." else "")
                setTextColor(Color.WHITE); textSize = 17f; gravity = Gravity.CENTER
            })
            addView(Button(this@MainActivity).apply {
                text = "Actualizează din Magazin Play"
                backgroundTintList = ColorStateList.valueOf(GOLD); setTextColor(BG)
                setOnClickListener {
                    val pkg = if (Build.VERSION.SDK_INT in 24..28) "com.android.chrome" else "com.google.android.webview"
                    try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$pkg"))) }
                    catch (e: ActivityNotFoundException) { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$pkg"))) }
                }
            }, LinearLayout.LayoutParams(WRAP_CONTENT, WRAP_CONTENT).apply { topMargin = dp(24) })
        }
        root.addView(box, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
    }

    // butonul / gestul „Înapoi”: închide întâi ferestrele din pagină, apoi aplicația.
    // Android 13+ (API 33) folosește OnBackInvokedCallback (gestul predictiv); versiunile vechi, onBackPressed.
    private fun registerBack() {
        if (Build.VERSION.SDK_INT >= 33) onBackInvokedDispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT) { goBack() }
    }

    @SuppressLint("GestureBackNavigation")     // Android 13+ trece prin registerBack(); aici doar versiunile vechi
    @Deprecated("doar pentru Android 12 și mai vechi")
    override fun onBackPressed() { goBack() }

    private fun goBack() {
        val w = web ?: return finish()
        w.evaluateJavascript("window.__doinaBack ? window.__doinaBack() : false") { r -> if (r != "true") finish() }
    }

    override fun onSaveInstanceState(outState: Bundle) { super.onSaveInstanceState(outState); web?.saveState(outState) }
    override fun onPause() { web?.onPause(); super.onPause() }
    override fun onResume() { super.onResume(); web?.onResume() }
    override fun onDestroy() { web?.destroy(); super.onDestroy() }

    /** Livrează fișierele din assets/web pentru adresa locală; orice altă adresă e blocată. */
    private inner class Client : WebViewClient() {
        private val types = mapOf(
            "html" to "text/html", "js" to "text/javascript", "json" to "application/json",
            "webmanifest" to "application/manifest+json", "png" to "image/png", "jpg" to "image/jpeg", "css" to "text/css",
        )

        override fun shouldInterceptRequest(view: WebView, req: WebResourceRequest): WebResourceResponse? {
            val url = req.url
            if ("${url.scheme}://${url.authority}" != ORIGIN) return error(403, "Blocat")
            var path = url.path.orEmpty().trimStart('/')
            if (path.isEmpty()) path = "index.html"
            if (path.split('/').any { it == ".." }) return error(404, "Lipsă")
            val ext = path.substringAfterLast('.', "").lowercase()
            val mime = types[ext] ?: "application/octet-stream"
            return try {
                WebResourceResponse(mime, if (mime.startsWith("text") || ext == "json") "utf-8" else null, 200, "OK",
                    mapOf("Cache-Control" to "no-cache", "Access-Control-Allow-Origin" to ORIGIN), assets.open("web/$path"))
            } catch (e: IOException) {
                error(404, "Lipsă")
            }
        }

        private fun error(code: Int, why: String) = WebResourceResponse("text/plain", "utf-8", code, why, null, null)

        override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest) = !req.url.toString().startsWith(ORIGIN)

        override fun onPageFinished(view: WebView, url: String) { loading.visibility = View.GONE }
    }

    /** <input type="file">: o poză, mai multe fișiere (catalog .csv / .json + poze) sau o bază de modele .json. */
    private inner class Chrome : WebChromeClient() {
        override fun onShowFileChooser(view: WebView, cb: ValueCallback<Array<Uri>>, p: FileChooserParams): Boolean {
            fileCallback?.onReceiveValue(null)
            fileCallback = cb
            val accept = p.acceptTypes.filter { it.isNotBlank() }
            val onlyImages = accept.isNotEmpty() && accept.all { it.startsWith("image") }
            val intent = when {
                p.mode == FileChooserParams.MODE_OPEN_MULTIPLE -> Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE); type = "*/*"; putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                }
                onlyImages && Build.VERSION.SDK_INT >= 33 -> Intent(MediaStore.ACTION_PICK_IMAGES)     // selectorul de poze (fără permisiuni)
                onlyImages -> Intent(Intent.ACTION_GET_CONTENT).apply { addCategory(Intent.CATEGORY_OPENABLE); type = "image/*" }
                else -> Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE); type = "*/*"
                    putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("application/json", "text/*", "application/octet-stream"))
                }
            }
            return try {
                @Suppress("DEPRECATION")
                startActivityForResult(intent, REQ_FILES); true
            } catch (e: ActivityNotFoundException) {
                fileCallback = null; false
            }
        }
    }

    @Deprecated("API-ul vechi, disponibil pe toate versiunile Android")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQ_FILES) return
        val uris = mutableListOf<Uri>()
        if (resultCode == RESULT_OK && data != null) {
            val clip = data.clipData
            if (clip != null) for (i in 0 until clip.itemCount) clip.getItemAt(i).uri?.let(uris::add)
            else data.data?.let(uris::add)
        }
        fileCallback?.onReceiveValue(if (uris.isEmpty()) null else uris.toTypedArray())
        fileCallback = null
    }

    /** Mesaje de la pagină: {type:'save', name, mime, b64} -> fișier temporar -> „Partajează / Salvează”;
     *  {type:'text', text} -> text partajat (lista de cumpărături: WhatsApp, e-mail, SMS…). */
    private inner class Bridge {
        @JavascriptInterface
        fun postMessage(raw: String) {
            runOnUiThread { onBridge(raw) }
        }
    }

    private fun onBridge(raw: String) {
        try {
            val msg = JSONObject(raw)
            when (msg.optString("type")) {
                "text" -> startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"; putExtra(Intent.EXTRA_TEXT, msg.getString("text"))
                }, null))
                "save" -> {
                    val name = msg.getString("name").replace(Regex("""[\\/:*?"<>|]"""), "_")
                    val mime = msg.optString("mime").ifEmpty { "application/octet-stream" }
                    val dir = File(cacheDir, "partajare").apply { mkdirs() }
                    val file = File(dir, name).apply { writeBytes(Base64.decode(msg.getString("b64"), Base64.DEFAULT)) }
                    val uri = FileProvider.getUriForFile(this, "$packageName.fisiere", file)
                    startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                        type = mime
                        putExtra(Intent.EXTRA_STREAM, uri)
                        clipData = ClipData.newRawUri(name, uri)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }, name))
                }
            }
        } catch (e: Exception) {
            Toast.makeText(this, "Nu am putut salva fișierul: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }
}
