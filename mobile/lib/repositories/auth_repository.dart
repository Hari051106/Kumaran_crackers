/// Authentication calls.
library;

import 'package:dio/dio.dart';

import '../core/api_client.dart';
import '../core/token_storage.dart';
import '../models/user.dart';

class AuthRepository {
  AuthRepository({required ApiClient client, required TokenStorage tokenStorage})
      : _client = client,
        _tokenStorage = tokenStorage;

  final ApiClient _client;
  final TokenStorage _tokenStorage;

  Future<AppUser> register({
    required String email,
    required String password,
    required String fullName,
    String? phone,
  }) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>(
        '/auth/register',
        data: {
          'email': email,
          'password': password,
          'full_name': fullName,
          if (phone != null && phone.isNotEmpty) 'phone': phone,
        },
      );
      return await _persist(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  Future<AppUser> login({required String email, required String password}) async {
    try {
      final response = await _client.dio.post<Map<String, dynamic>>(
        '/auth/login',
        data: {'email': email, 'password': password},
      );
      return await _persist(response.data!);
    } on DioException catch (error) {
      throw ApiClient.toApiException(error);
    }
  }

  /// Resolve the signed-in user from a stored token, or null when signed out.
  Future<AppUser?> restore() async {
    final session = await _tokenStorage.read();
    if (session == null) return null;
    try {
      final response = await _client.dio.get<Map<String, dynamic>>('/auth/me');
      return AppUser.fromJson(response.data!);
    } on DioException {
      // Expired, revoked, or the account was deactivated.
      await _tokenStorage.clear();
      return null;
    }
  }

  Future<void> logout() async {
    try {
      await _client.dio.post<void>('/auth/logout');
    } on DioException {
      // Signing out locally must succeed even with no connection.
    }
    await _tokenStorage.clear();
  }

  Future<AppUser> _persist(Map<String, dynamic> body) async {
    final tokens = body['tokens'] as Map<String, dynamic>;
    await _tokenStorage.write(
      StoredSession(
        accessToken: tokens['access_token'] as String,
        refreshToken: tokens['refresh_token'] as String,
      ),
    );
    return AppUser.fromJson(body['user'] as Map<String, dynamic>);
  }
}
