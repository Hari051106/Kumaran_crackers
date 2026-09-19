/// Mirrors the backend `UserRead` schema.
library;

class AppUser {
  const AppUser({
    required this.id,
    required this.email,
    required this.fullName,
    required this.roleName,
    this.phone,
    this.isVerified = false,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as int,
        email: json['email'] as String,
        fullName: json['full_name'] as String,
        roleName: (json['role'] as Map<String, dynamic>)['name'] as String,
        phone: json['phone'] as String?,
        isVerified: (json['is_verified'] as bool?) ?? false,
      );

  final int id;
  final String email;
  final String fullName;
  final String roleName;
  final String? phone;
  final bool isVerified;

  String get initials {
    final parts = fullName.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first.characters.first.toUpperCase();
    return '${parts.first[0]}${parts[1][0]}'.toUpperCase();
  }
}

extension on String {
  Iterable<String> get characters => split('');
}
