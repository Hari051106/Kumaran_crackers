/// Money must be formatted exactly, without ever passing through a double.
library;
import 'package:flutter_test/flutter_test.dart';
import 'package:kumaran_crackers/core/money.dart';

void main() {
  group('formatMoney', () {
    test('formats a plain amount', () {
      expect(formatMoney('1874.25'), '₹1,874.25');
    });

    test('keeps a trailing zero rather than dropping it', () {
      expect(formatMoney('2499.00'), '₹2,499.00');
      expect(formatMoney('1234.50'), '₹1,234.50');
    });

    test('groups in the Indian style', () {
      expect(formatMoney('100.00'), '₹100.00');
      expect(formatMoney('1000.00'), '₹1,000.00');
      expect(formatMoney('100000.00'), '₹1,00,000.00');
      expect(formatMoney('1234567.89'), '₹12,34,567.89');
      expect(formatMoney('12345678.00'), '₹1,23,45,678.00');
    });

    test('pads a missing or short fraction', () {
      expect(formatMoney('50'), '₹50.00');
      expect(formatMoney('50.5'), '₹50.50');
    });

    test('handles null, empty and negative values', () {
      expect(formatMoney(null), '₹0.00');
      expect(formatMoney(''), '₹0.00');
      expect(formatMoney('-250.75'), '-₹250.75');
    });

    test('can omit the symbol', () {
      expect(formatMoney('99.99', showSymbol: false), '99.99');
    });

    test('never loses precision the way a double would', () {
      // 0.1 + 0.2 != 0.3 in binary floating point. Staying on the string means
      // the value the server sent is the value shown.
      expect(formatMoney('0.10'), '₹0.10');
      expect(formatMoney('1999.99'), '₹1,999.99');
      expect(formatMoney('0.07'), '₹0.07');
    });
  });

  group('formatMoneyShort', () {
    test('drops the paise', () {
      expect(formatMoneyShort('140568.75'), '₹1,40,568');
    });
  });

  group('formatDiscount', () {
    test('drops a pointless trailing .0', () {
      expect(formatDiscount('25.0'), '25% OFF');
      expect(formatDiscount('12.5'), '12.5% OFF');
    });

    test('returns empty for a missing value', () {
      expect(formatDiscount(null), '');
    });
  });

  group('hasDiscount', () {
    test('is false at full price', () {
      expect(hasDiscount('0.0'), isFalse);
      expect(hasDiscount('0.00'), isFalse);
      expect(hasDiscount(null), isFalse);
    });

    test('is true for any real saving', () {
      expect(hasDiscount('25.0'), isTrue);
      expect(hasDiscount('0.5'), isTrue);
    });
  });

  group('compareMoney', () {
    test('orders amounts correctly', () {
      expect(compareMoney('100.00', '200.00'), lessThan(0));
      expect(compareMoney('200.00', '100.00'), greaterThan(0));
      expect(compareMoney('100.00', '100.00'), 0);
    });

    test('compares the paise, not just the rupees', () {
      expect(compareMoney('100.01', '100.00'), greaterThan(0));
      expect(compareMoney('99.99', '100.00'), lessThan(0));
    });

    test('is exact where a double would round', () {
      // Beyond 2^53 a double cannot represent these distinctly.
      expect(compareMoney('9007199254740993.00', '9007199254740992.00'), greaterThan(0));
    });

    test('handles negatives', () {
      expect(compareMoney('-50.00', '10.00'), lessThan(0));
      expect(compareMoney('-10.00', '-50.00'), greaterThan(0));
    });
  });

  group('groupIndian', () {
    test('matches the Indian convention', () {
      expect(groupIndian('1'), '1');
      expect(groupIndian('999'), '999');
      expect(groupIndian('1000'), '1,000');
      expect(groupIndian('10000'), '10,000');
      expect(groupIndian('100000'), '1,00,000');
      expect(groupIndian('10000000'), '1,00,00,000');
    });
  });
}
