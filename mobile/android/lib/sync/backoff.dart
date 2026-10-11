// Retry and backoff (contract project-log §8): waits of 1, 2, 4 … 60 s with
// ±20 % jitter, `Retry-After` honoured, on network errors and 408, 429, 500,
// 502, 503, 504 and 530. 409 and 422 are never retried as sent.

import 'dart:math';

const retryStatuses = {408, 429, 500, 502, 503, 504, 530};

/// A request that failed with `status` (0 = no answer) may be sent again unchanged.
bool retryable(int status) => status == 0 || retryStatuses.contains(status);

class Backoff {
  Backoff({Random? random, this.base = const Duration(seconds: 1), this.cap = const Duration(seconds: 60)})
      : _random = random ?? Random();

  final Random _random;
  final Duration base;
  final Duration cap;
  int _attempt = 0;

  int get attempt => _attempt;

  /// The wait before the next try; a server's `Retry-After` wins when longer.
  Duration next({Duration? retryAfter}) {
    final raw = min(cap.inMilliseconds, base.inMilliseconds * pow(2, min(_attempt, 30)).toInt());
    _attempt++;
    final jittered = Duration(milliseconds: (raw * (0.8 + _random.nextDouble() * 0.4)).round());
    if (retryAfter != null && retryAfter > jittered) return retryAfter;
    return jittered;
  }

  void reset() => _attempt = 0;
}

/// `Retry-After` as seconds or an HTTP date; the envelope's `retry_after_s` otherwise.
Duration? parseRetryAfter(String? header, {Object? envelopeSeconds, DateTime? now}) {
  if (header != null && header.trim().isNotEmpty) {
    final seconds = int.tryParse(header.trim());
    if (seconds != null) return Duration(seconds: max(0, seconds));
    try {
      final at = _parseHttpDate(header.trim());
      final wait = at.difference(now ?? DateTime.now().toUtc());
      return wait.isNegative ? Duration.zero : wait;
    } on FormatException {
      // fall through to the envelope
    }
  }
  if (envelopeSeconds is num && envelopeSeconds >= 0) return Duration(seconds: envelopeSeconds.ceil());
  return null;
}

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/// IMF-fixdate (RFC 9110 §5.6.7): `Sun, 06 Nov 1994 08:49:37 GMT`.
DateTime _parseHttpDate(String text) {
  final m = RegExp(r'^\w{3}, (\d{2}) (\w{3}) (\d{4}) (\d{2}):(\d{2}):(\d{2}) GMT$').firstMatch(text);
  if (m == null) throw const FormatException('not an HTTP date');
  final month = _months.indexOf(m.group(2)!) + 1;
  if (month == 0) throw const FormatException('not an HTTP date');
  return DateTime.utc(int.parse(m.group(3)!), month, int.parse(m.group(1)!), int.parse(m.group(4)!),
      int.parse(m.group(5)!), int.parse(m.group(6)!));
}
