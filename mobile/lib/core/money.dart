/// Money formatting that never goes through a floating-point number.
///
/// The API sends money as exact decimal strings ("1874.25"). Parsing those into
/// a Dart `double` would reintroduce binary floating-point error - precisely
/// what the backend's `Numeric(10,2)` columns exist to prevent. Everything here
/// operates on the string.
library;

const String rupee = '₹';

class _Parts {
  const _Parts(this.negative, this.whole, this.fraction);

  final bool negative;
  final String whole;
  final String fraction;
}

_Parts _split(String value) {
  final trimmed = value.trim();
  final negative = trimmed.startsWith('-');
  final unsigned = negative ? trimmed.substring(1) : trimmed;
  final dot = unsigned.indexOf('.');
  if (dot == -1) {
    return _Parts(negative, unsigned.isEmpty ? '0' : unsigned, '');
  }
  final whole = unsigned.substring(0, dot);
  return _Parts(negative, whole.isEmpty ? '0' : whole, unsigned.substring(dot + 1));
}

/// Group digits the Indian way: the last three, then pairs.
/// `1234567` becomes `12,34,567`.
String groupIndian(String digits) {
  if (digits.length <= 3) return digits;
  final last3 = digits.substring(digits.length - 3);
  final rest = digits.substring(0, digits.length - 3);

  final buffer = StringBuffer();
  for (var i = 0; i < rest.length; i++) {
    // A separator every two digits, counted from the right of `rest`.
    if (i > 0 && (rest.length - i) % 2 == 0) buffer.write(',');
    buffer.write(rest[i]);
  }
  return '$buffer,$last3';
}

/// Format a decimal string as `₹1,874.25`.
String formatMoney(String? value, {bool showSymbol = true}) {
  if (value == null || value.trim().isEmpty) {
    return showSymbol ? '${rupee}0.00' : '0.00';
  }
  final parts = _split(value);
  final paise = '${parts.fraction}00'.substring(0, 2);
  final body = '${groupIndian(parts.whole)}.$paise';
  return '${parts.negative ? '-' : ''}${showSymbol ? rupee : ''}$body';
}

/// Format a decimal string as whole rupees, e.g. `₹1,874`.
String formatMoneyShort(String? value) {
  if (value == null || value.trim().isEmpty) return '${rupee}0';
  final parts = _split(value);
  return '${parts.negative ? '-' : ''}$rupee${groupIndian(parts.whole)}';
}

/// Format `"25.0"` as `25% OFF`, dropping a pointless trailing `.0`.
String formatDiscount(String? value) {
  if (value == null || value.isEmpty) return '';
  final cleaned = value.endsWith('.0') ? value.substring(0, value.length - 2) : value;
  return '$cleaned% OFF';
}

/// True when the value represents a real saving rather than `"0.0"`.
bool hasDiscount(String? discountPercentage) {
  if (discountPercentage == null) return false;
  final parts = _split(discountPercentage);
  return parts.whole != '0' || parts.fraction.replaceAll('0', '').isNotEmpty;
}

/// Compare two decimal strings exactly, without floating point.
int compareMoney(String a, String b) {
  final pa = _split(a);
  final pb = _split(b);
  if (pa.negative != pb.negative) return pa.negative ? -1 : 1;

  BigInt scaled(_Parts p) => BigInt.parse('${p.whole}${'${p.fraction}00'.substring(0, 2)}');
  final diff = scaled(pa) - scaled(pb);
  final magnitude = diff == BigInt.zero ? 0 : (diff > BigInt.zero ? 1 : -1);
  return pa.negative ? -magnitude : magnitude;
}
