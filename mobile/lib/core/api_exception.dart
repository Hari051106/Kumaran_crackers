/// A failure the UI can render without knowing anything about Dio.
///
/// The backend returns one error envelope for every failure:
///   { "error": { "code": "...", "message": "...", "details": { ... } } }
/// This turns that - and network failures, which have no envelope - into a
/// single type.
library;

class ApiException implements Exception {
  const ApiException(
    this.message, {
    this.statusCode = 0,
    this.code = 'unknown_error',
    this.fieldErrors = const {},
  });

  final String message;
  final int statusCode;
  final String code;

  /// Per-field validation messages, keyed by field name.
  final Map<String, String> fieldErrors;

  /// No response at all: the server is unreachable or the request timed out.
  bool get isNetworkError => statusCode == 0;

  bool get isAuthError => statusCode == 401;

  bool get isNotFound => statusCode == 404;

  static const ApiException network = ApiException(
    'Cannot reach Kumaran Crackers. Check your internet connection and try again.',
    code: 'network_error',
  );

  @override
  String toString() => 'ApiException($statusCode, $code): $message';
}
