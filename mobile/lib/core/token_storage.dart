/// Secure storage for the signed-in session.
///
/// Tokens go to the platform keystore - EncryptedSharedPreferences backed by
/// the Android Keystore, and the iOS Keychain - never to plain
/// SharedPreferences, which any process with the app's data directory can read.
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class StoredSession {
  const StoredSession({required this.accessToken, required this.refreshToken});

  final String accessToken;
  final String refreshToken;
}

class TokenStorage {
  TokenStorage([FlutterSecureStorage? storage])
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
              iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
            );

  final FlutterSecureStorage _storage;

  static const _accessKey = 'kumaran.access_token';
  static const _refreshKey = 'kumaran.refresh_token';

  Future<StoredSession?> read() async {
    try {
      final access = await _storage.read(key: _accessKey);
      final refresh = await _storage.read(key: _refreshKey);
      if (access == null || refresh == null) return null;
      return StoredSession(accessToken: access, refreshToken: refresh);
    } on Exception {
      // A corrupt or unreadable keystore entry must sign the user out rather
      // than crash the app on launch.
      return null;
    }
  }

  Future<void> write(StoredSession session) async {
    await _storage.write(key: _accessKey, value: session.accessToken);
    await _storage.write(key: _refreshKey, value: session.refreshToken);
  }

  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }
}
