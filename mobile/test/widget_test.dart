/// Widget tests for the screens that carry real behaviour.
library;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:kumaran_crackers/core/theme.dart';
import 'package:kumaran_crackers/features/auth/login_screen.dart';
import 'package:kumaran_crackers/features/auth/register_screen.dart';
import 'package:kumaran_crackers/models/product.dart';
import 'package:kumaran_crackers/widgets/product_card.dart';
import 'package:kumaran_crackers/widgets/state_views.dart';
import 'package:kumaran_crackers/core/api_exception.dart';

import 'models_test.dart' show productJson;

Widget wrap(Widget child) => ProviderScope(
      child: MaterialApp(theme: AppTheme.light(), home: child),
    );

void main() {
  group('ProductCard', () {
    testWidgets('shows the price, the struck-through MRP and the saving', (tester) async {
      final product = Product.fromJson(productJson());
      await tester.pumpWidget(
        wrap(Scaffold(
          body: SizedBox(
            width: 200,
            height: 320,
            child: ProductCard(product: product, onTap: () {}),
          ),
        )),
      );

      expect(find.text('₹1,874.25'), findsOneWidget);
      expect(find.text('₹2,499.00'), findsOneWidget);
      expect(find.text('25% OFF'), findsOneWidget);
      expect(find.text('Thunder King 12-Shot'), findsOneWidget);
    });

    testWidgets('hides the discount badge at full price', (tester) async {
      final product = Product.fromJson(
        productJson(mrp: '500.00', sellingPrice: '500.00', discountPercentage: '0.0'),
      );
      await tester.pumpWidget(
        wrap(Scaffold(
          body: SizedBox(
            width: 200,
            height: 320,
            child: ProductCard(product: product, onTap: () {}),
          ),
        )),
      );

      expect(find.text('₹500.00'), findsOneWidget);
      expect(find.textContaining('OFF'), findsNothing);
    });

    testWidgets('marks an out-of-stock product clearly', (tester) async {
      final product = Product.fromJson(
        productJson(stockStatus: 'OUT_OF_STOCK', inStock: false),
      );
      await tester.pumpWidget(
        wrap(Scaffold(
          body: SizedBox(
            width: 200,
            height: 320,
            child: ProductCard(product: product, onTap: () {}),
          ),
        )),
      );

      // Both the overlay and the chip say it in words, not colour alone.
      expect(find.text('Out of stock'), findsNWidgets(2));
    });

    testWidgets('calls back when tapped', (tester) async {
      var tapped = false;
      final product = Product.fromJson(productJson());
      await tester.pumpWidget(
        wrap(Scaffold(
          body: SizedBox(
            width: 200,
            height: 320,
            child: ProductCard(product: product, onTap: () => tapped = true),
          ),
        )),
      );

      await tester.tap(find.byType(InkWell).first);
      expect(tapped, isTrue);
    });
  });

  group('StockChip', () {
    testWidgets('always pairs colour with words', (tester) async {
      for (final (status, label) in [
        (StockStatus.inStock, 'In stock'),
        (StockStatus.lowStock, 'Only a few left'),
        (StockStatus.outOfStock, 'Out of stock'),
      ]) {
        await tester.pumpWidget(wrap(Scaffold(body: StockChip(status: status))));
        expect(find.text(label), findsOneWidget);
        // An icon accompanies it, so the state survives a greyscale screen.
        expect(find.byType(Icon), findsOneWidget);
      }
    });
  });

  group('LoginScreen', () {
    testWidgets('refuses an empty form', (tester) async {
      await tester.pumpWidget(wrap(const LoginScreen()));

      await tester.tap(find.byKey(const Key('login-submit')));
      await tester.pumpAndSettle();

      expect(find.text('Enter your email address.'), findsOneWidget);
      expect(find.text('Enter your password.'), findsOneWidget);
    });

    testWidgets('rejects a malformed email', (tester) async {
      await tester.pumpWidget(wrap(const LoginScreen()));

      await tester.enterText(find.byKey(const Key('login-email')), 'not-an-email');
      await tester.enterText(find.byKey(const Key('login-password')), 'Secret123');
      await tester.tap(find.byKey(const Key('login-submit')));
      await tester.pumpAndSettle();

      expect(find.text('Enter a valid email address.'), findsOneWidget);
    });

    testWidgets('toggles password visibility', (tester) async {
      await tester.pumpWidget(wrap(const LoginScreen()));

      expect(find.byTooltip('Show password'), findsOneWidget);
      await tester.tap(find.byTooltip('Show password'));
      await tester.pumpAndSettle();
      expect(find.byTooltip('Hide password'), findsOneWidget);
    });
  });

  group('RegisterScreen', () {
    testWidgets('enforces the password policy the server applies', (tester) async {
      await tester.pumpWidget(wrap(const RegisterScreen()));

      await tester.enterText(find.byKey(const Key('register-name')), 'Priya Selvam');
      await tester.enterText(find.byKey(const Key('register-email')), 'priya@example.com');
      await tester.enterText(find.byKey(const Key('register-password')), 'short');
      await tester.tap(find.byKey(const Key('register-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Use at least 8 characters.'), findsOneWidget);

      await tester.enterText(find.byKey(const Key('register-password')), 'onlyletters');
      await tester.tap(find.byKey(const Key('register-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Include at least one number.'), findsOneWidget);

      await tester.enterText(find.byKey(const Key('register-password')), '12345678');
      await tester.tap(find.byKey(const Key('register-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Include at least one letter.'), findsOneWidget);
    });

    testWidgets('validates an Indian mobile number but allows it to be blank', (tester) async {
      await tester.pumpWidget(wrap(const RegisterScreen()));

      await tester.enterText(find.byKey(const Key('register-name')), 'Priya Selvam');
      await tester.enterText(find.byKey(const Key('register-email')), 'priya@example.com');
      await tester.enterText(find.byKey(const Key('register-password')), 'Diwali2026');
      await tester.enterText(find.byKey(const Key('register-phone')), '12345');
      await tester.tap(find.byKey(const Key('register-submit')));
      await tester.pumpAndSettle();

      expect(find.text('Enter a valid 10-digit mobile number.'), findsOneWidget);
    });

    testWidgets('states the age restriction at sign-up', (tester) async {
      await tester.pumpWidget(wrap(const RegisterScreen()));
      expect(find.textContaining('18 or older'), findsOneWidget);
    });
  });

  group('ErrorView', () {
    testWidgets('names a connection problem for what it is', (tester) async {
      await tester.pumpWidget(
        wrap(Scaffold(body: ErrorView(error: ApiException.network, onRetry: () {}))),
      );

      expect(find.text('No connection'), findsOneWidget);
      expect(find.text('Try again'), findsOneWidget);
    });

    testWidgets('shows the server message for other failures', (tester) async {
      await tester.pumpWidget(
        wrap(const Scaffold(
          body: ErrorView(
            error: ApiException('That product is no longer available.', statusCode: 404),
          ),
        )),
      );

      expect(find.text('That product is no longer available.'), findsOneWidget);
      // Nothing to retry, so no button is offered.
      expect(find.text('Try again'), findsNothing);
    });
  });
}
