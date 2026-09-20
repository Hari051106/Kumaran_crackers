/// Date and time formatting for order screens.
///
/// Deliberately hand-rolled rather than pulling in `intl`: the app needs three
/// fixed formats in one locale, and a formatting package would be a large
/// dependency for that.
library;

const List<String> _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

String _two(int value) => value.toString().padLeft(2, '0');

/// `20 Sep 2026`
String formatDate(DateTime when) =>
    '${when.day} ${_months[when.month - 1]} ${when.year}';

/// `3:04 pm`
String formatTime(DateTime when) {
  final hour = when.hour % 12 == 0 ? 12 : when.hour % 12;
  final suffix = when.hour < 12 ? 'am' : 'pm';
  return '$hour:${_two(when.minute)} $suffix';
}

/// `20 Sep 2026, 3:04 pm`
String formatDateTime(DateTime when) => '${formatDate(when)}, ${formatTime(when)}';

/// A relative phrase for recent events, falling back to the date.
///
/// Used only where an approximate answer is what the reader wants; anything
/// that has to be exact uses [formatDateTime].
String formatRelative(DateTime when, {DateTime? now}) {
  final reference = now ?? DateTime.now();
  final difference = reference.difference(when);

  if (difference.isNegative) return formatDateTime(when);
  if (difference.inMinutes < 1) return 'Just now';
  if (difference.inMinutes < 60) {
    final minutes = difference.inMinutes;
    return '$minutes ${minutes == 1 ? 'minute' : 'minutes'} ago';
  }
  if (difference.inHours < 24) {
    final hours = difference.inHours;
    return '$hours ${hours == 1 ? 'hour' : 'hours'} ago';
  }
  if (difference.inDays == 1) return 'Yesterday, ${formatTime(when)}';
  if (difference.inDays < 7) return '${difference.inDays} days ago';
  return formatDate(when);
}
