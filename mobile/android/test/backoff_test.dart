// sync_backoff_matches_contract: waits of 1, 2, 4 … 60 s within ± 20 %;
// `Retry-After` honoured; 409 and 422 not retried (contract project-log §8).

import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/api/api.dart';
import 'package:truebex/sync/backoff.dart';

class _Fixed implements Random {
  _Fixed(this.value);
  final double value;
  @override
  double nextDouble() => value;
  @override
  bool nextBool() => false;
  @override
  int nextInt(int max) => 0;
}

void main() {
  test('sync_backoff_matches_contract', () {
    const expected = [1, 2, 4, 8, 16, 32, 60, 60, 60];
    for (final r in [0.0, 0.5, 0.999999]) {
      final b = Backoff(random: _Fixed(r));
      for (final seconds in expected) {
        final wait = b.next().inMilliseconds;
        expect(wait, inInclusiveRange((seconds * 800), (seconds * 1200)), reason: 'attempt ${b.attempt} r=$r');
      }
    }
    // The middle of the jitter is the contract's number exactly.
    final mid = Backoff(random: _Fixed(0.5));
    expect([for (var i = 0; i < 7; i++) mid.next().inSeconds], [1, 2, 4, 8, 16, 32, 60]);
    // Random jitter stays inside ± 20 % over many draws.
    final rnd = Backoff(random: Random(7));
    for (var i = 0; i < 200; i++) {
      final base = min(60, pow(2, min(i, 30)).toInt()) * 1000;
      final w = rnd.next().inMilliseconds;
      expect(w, inInclusiveRange(base * 0.8 - 1, base * 1.2 + 1));
    }
    mid.reset();
    expect(mid.next().inSeconds, 1);
  });

  test('Retry-After is honoured when longer than the backoff', () {
    final b = Backoff(random: _Fixed(0.5));
    expect(b.next(retryAfter: const Duration(seconds: 30)), const Duration(seconds: 30));
    expect(b.next(retryAfter: const Duration(milliseconds: 10)), const Duration(seconds: 2));
    expect(parseRetryAfter('17'), const Duration(seconds: 17));
    expect(parseRetryAfter('Sun, 11 Oct 2026 10:00:30 GMT', now: DateTime.utc(2026, 10, 11, 10, 0, 0)), const Duration(seconds: 30));
    expect(parseRetryAfter(null, envelopeSeconds: 7), const Duration(seconds: 7));
    expect(parseRetryAfter('soon'), isNull);
    final failure = TruebexApi.failureOf(429, '{"detail":"Slow down.","code":"rate_limited","status":429,"retry_after_s":12}', '12');
    expect(failure.retryAfter, const Duration(seconds: 12));
    expect(failure.code, 'rate_limited');
    expect(failure.retryable, isTrue);
  });

  test('which answers are retried as sent', () {
    for (final s in [0, 408, 429, 500, 502, 503, 504, 530]) {
      expect(retryable(s), isTrue, reason: '$s');
    }
    for (final s in [400, 401, 403, 404, 409, 413, 422]) {
      expect(retryable(s), isFalse, reason: '$s');
    }
    expect(TruebexApi.failureOf(409, '{"detail":"x","code":"idempotency_mismatch"}', null).retryable, isFalse);
    expect(TruebexApi.failureOf(422, 'not json', null).code, 'http_422');
  });
}
