/// Dio client for the Kumaran Crackers API.
///
/// Responsibilities:
///  - attach the bearer token to every request
///  - refresh once on a 401 and replay the original request
///  - turn the backend's error envelope into an [ApiException]
library;

import 'package:dio/dio.dart';

import 'api_exception.dart';
import 'config.dart';
import 'token_storage.dart';

typedef SessionExpiredCallback = void Function();

class ApiClient {
  ApiClient({required TokenStorage tokenStorage, Dio? dio, String? baseUrl})
      : _tokenStorage = tokenStorage,
        dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: baseUrl ?? AppConfig.apiBaseUrl,
                connectTimeout: AppConfig.requestTimeout,
                receiveTimeout: AppConfig.requestTimeout,
                headers: {'Content-Type': 'application/json'},
                // We interpret status codes ourselves in the error interceptor.
                validateStatus: (status) => status != null && status < 400,
              ),
            ) {
    this.dio.interceptors.add(
          InterceptorsWrapper(onRequest: _onRequest, onError: _onError),
        );
  }

  final Dio dio;
  final TokenStorage _tokenStorage;

  /// Invoked when a refresh fails and the session cannot be recovered.
  SessionExpiredCallback? onSessionExpired;

  /// A single in-flight refresh shared by concurrent 401s, so a burst of
  /// failures does not fire N refresh calls that invalidate each other.
  Future<StoredSession?>? _refreshInFlight;

  Future<void> _onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final session = await _tokenStorage.read();
    if (session != null) {
      options.headers['Authorization'] = 'Bearer ${session.accessToken}';
    }
    handler.next(options);
  }

  Future<void> _onError(DioException error, ErrorInterceptorHandler handler) async {
    final response = error.response;
    final path = error.requestOptions.path;

    // Never try to refresh the auth calls themselves, and only retry once.
    final isAuthCall = path.contains('/auth/');
    final alreadyRetried = error.requestOptions.extra['retried'] == true;

    if (response?.statusCode == 401 && !isAuthCall && !alreadyRetried) {
      final session = await (_refreshInFlight ??= _refresh());
      _refreshInFlight = null;

      if (session != null) {
        final request = error.requestOptions
          ..extra['retried'] = true
          ..headers['Authorization'] = 'Bearer ${session.accessToken}';
        try {
          final retried = await dio.fetch<dynamic>(request);
          return handler.resolve(retried);
        } on DioException catch (retryError) {
          return handler.reject(retryError);
        }
      }
      onSessionExpired?.call();
    }

    handler.reject(error);
  }

  Future<StoredSession?> _refresh() async {
    final current = await _tokenStorage.read();
    if (current == null) return null;

    try {
      // A bare Dio instance: using `dio` here would recurse through this very
      // interceptor.
      final bare = Dio(BaseOptions(baseUrl: dio.options.baseUrl));
      final response = await bare.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh_token': current.refreshToken},
      );
      final tokens = response.data!['tokens'] as Map<String, dynamic>;
      final next = StoredSession(
        accessToken: tokens['access_token'] as String,
        refreshToken: tokens['refresh_token'] as String,
      );
      await _tokenStorage.write(next);
      return next;
    } on DioException {
      await _tokenStorage.clear();
      return null;
    }
  }

  /// Translate a Dio failure into the app's own exception type.
  static ApiException toApiException(Object error) {
    if (error is ApiException) return error;
    if (error is! DioException) {
      return const ApiException('Something went wrong. Please try again.');
    }

    final response = error.response;
    if (response == null) return ApiException.network;

    final body = response.data;
    if (body is Map && body['error'] is Map) {
      final envelope = body['error'] as Map;
      final rawDetails = envelope['details'];
      return ApiException(
        (envelope['message'] as String?) ?? 'Something went wrong. Please try again.',
        statusCode: response.statusCode ?? 0,
        code: (envelope['code'] as String?) ?? 'unknown_error',
        fieldErrors: rawDetails is Map
            ? rawDetails.map((key, value) => MapEntry('$key', '$value'))
            : const {},
      );
    }

    return ApiException(
      'Something went wrong. Please try again.',
      statusCode: response.statusCode ?? 0,
    );
  }
}
