// DoinaDress – cabina de probă 3D, ambalată ca aplicație Android / iPhone.
//
// Aplicația web (assets/web, generată de src/build.py) este servită de un mic server HTTP
// local (127.0.0.1, port fix -> baza de modele salvată în IndexedDB rămâne între porniri)
// și afișată într-un WebView. Puntea „DoinaBridge” primește fișierele pe care pagina vrea
// să le salveze (export bază, imagini) și le trimite la meniul de partajare al telefonului.
import 'dart:convert';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

const _port = 47811;
const _bg = Color(0xFF14171D);

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: _bg,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: _bg,
  ));
  await _LocalServer.start();
  runApp(const DoinaDressApp());
}

/// Server HTTP minimal care livrează fișierele din assets/web.
class _LocalServer {
  static HttpServer? _server;
  static const _types = {
    'html': 'text/html; charset=utf-8',
    'js': 'text/javascript; charset=utf-8',
    'json': 'application/json',
    'webmanifest': 'application/manifest+json',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'css': 'text/css',
  };

  static Future<void> start() async {
    if (_server != null) return;
    _server = await HttpServer.bind(InternetAddress.loopbackIPv4, _port, shared: true);
    _server!.listen((req) async {
      var path = Uri.decodeComponent(req.uri.path);
      if (path == '/' || path.isEmpty) path = '/index.html';
      try {
        final data = await rootBundle.load('assets/web$path');
        final ext = path.split('.').last.toLowerCase();
        req.response.headers.set('Content-Type', _types[ext] ?? 'application/octet-stream');
        req.response.headers.set('Cache-Control', 'no-cache');
        req.response.add(data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes));
      } catch (_) {
        req.response.statusCode = HttpStatus.notFound;
      }
      await req.response.close();
    });
  }
}

class DoinaDressApp extends StatelessWidget {
  const DoinaDressApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'DoinaDress',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(colorSchemeSeed: const Color(0xFFD4A35A), brightness: Brightness.dark),
        home: const CabinaPage(),
      );
}

class CabinaPage extends StatefulWidget {
  const CabinaPage({super.key});

  @override
  State<CabinaPage> createState() => _CabinaPageState();
}

class _CabinaPageState extends State<CabinaPage> {
  late final WebViewController _web;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _web = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(_bg)
      ..addJavaScriptChannel('DoinaBridge', onMessageReceived: (m) => _onBridge(m.message))
      ..setNavigationDelegate(NavigationDelegate(
        onPageFinished: (_) => setState(() => _loading = false),
        onNavigationRequest: (r) => r.url.startsWith('http://127.0.0.1:$_port')
            ? NavigationDecision.navigate
            : NavigationDecision.prevent,
      ));
    final platform = _web.platform;
    if (platform is AndroidWebViewController) {
      platform.setMediaPlaybackRequiresUserGesture(true);
      platform.setOnShowFileSelector(_pickFiles); // <input type="file"> pe Android
    }
    _web.loadRequest(Uri.parse('http://127.0.0.1:$_port/index.html'));
  }

  /// Alegerea fișierelor pentru pagină: poze din galerie, o bază de modele (.json) sau catalogul (.csv / .json + poze).
  Future<List<String>> _pickFiles(FileSelectorParams p) async {
    final onlyImages = p.acceptTypes.isNotEmpty && p.acceptTypes.every((t) => t.startsWith('image'));
    if (p.mode == FileSelectorMode.openMultiple) {
      final fs = await openFiles(acceptedTypeGroups: const [
        XTypeGroup(label: 'Catalog și poze', extensions: ['csv', 'json', 'txt', 'jpg', 'jpeg', 'png', 'webp']),
      ]);
      return fs.map((f) => Uri.file(f.path).toString()).toList();
    }
    if (onlyImages) {
      final img = await ImagePicker().pickImage(source: ImageSource.gallery);
      return img == null ? [] : [Uri.file(img.path).toString()];
    }
    final f = await openFile(acceptedTypeGroups: const [
      XTypeGroup(label: 'Bază de modele', extensions: ['json'], mimeTypes: ['application/json', 'text/plain', 'application/octet-stream']),
    ]);
    return f == null ? [] : [Uri.file(f.path).toString()];
  }

  /// Mesaje de la pagină: {type:'save', name, mime, b64} -> fișier temporar -> meniul „Partajează / Salvează”;
  /// {type:'text', text} -> text partajat (lista de cumpărături).
  Future<void> _onBridge(String raw) async {
    try {
      final msg = jsonDecode(raw) as Map<String, dynamic>;
      if (msg['type'] == 'text') {          // lista de cumpărături -> WhatsApp, e-mail, SMS…
        await SharePlus.instance.share(ShareParams(text: msg['text'] as String));
        return;
      }
      if (msg['type'] != 'save') return;
      final dir = await getTemporaryDirectory();
      final name = (msg['name'] as String).replaceAll(RegExp(r'[\\/:*?"<>|]'), '_');
      final file = File('${dir.path}/$name');
      await file.writeAsBytes(base64Decode(msg['b64'] as String));
      if (!mounted) return;
      final box = context.findRenderObject() as RenderBox?;
      await SharePlus.instance.share(ShareParams(
        files: [XFile(file.path, mimeType: msg['mime'] as String?)],
        title: name,
        sharePositionOrigin: box == null ? null : box.localToGlobal(Offset.zero) & box.size,
      ));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Nu am putut salva fișierul: $e')));
      }
    }
  }

  /// Butonul „Înapoi” (Android): închide întâi ferestrele din pagină, apoi aplicația.
  Future<void> _onBack() async {
    final r = await _web.runJavaScriptReturningResult('window.__doinaBack ? window.__doinaBack() : false');
    if (r != true && r.toString() != 'true') SystemNavigator.pop();
  }

  @override
  Widget build(BuildContext context) => PopScope(
        canPop: false,
        onPopInvokedWithResult: (didPop, _) { if (!didPop) _onBack(); },
        child: Scaffold(
          backgroundColor: _bg,
          body: SafeArea(
            child: Stack(children: [
              WebViewWidget(controller: _web),
              if (_loading)
                const Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                  CircularProgressIndicator(color: Color(0xFFD4A35A)),
                  SizedBox(height: 14),
                  Text('Se încarcă cabina 3D…', style: TextStyle(color: Color(0xFF9AA2B1))),
                ])),
            ]),
          ),
        ),
      );
}
