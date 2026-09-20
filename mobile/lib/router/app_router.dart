/// Navigation.
///
/// The catalogue is browsable signed-out, so only account screens are gated.
/// The guard here is convenience; the API enforces every permission itself.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/address/address_screens.dart';
import '../features/auth/login_screen.dart';
import '../features/auth/register_screen.dart';
import '../features/cart/cart_screen.dart';
import '../features/catalog/product_detail_screen.dart';
import '../features/catalog/products_screen.dart';
import '../features/checkout/checkout_screen.dart';
import '../features/home/home_screen.dart';
import '../models/address.dart';
import '../features/profile/profile_screen.dart';
import '../features/splash/splash_screen.dart';

GoRouter buildRouter({required bool Function() isCheckingSession}) => GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const SplashScreen(),
          redirect: (context, state) => isCheckingSession() ? null : '/home',
        ),
        GoRoute(path: '/home', builder: (context, state) => const HomeScreen()),
        GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
        GoRoute(path: '/register', builder: (context, state) => const RegisterScreen()),
        GoRoute(path: '/profile', builder: (context, state) => const ProfileScreen()),
        GoRoute(
          path: '/products',
          builder: (context, state) {
            final params = state.uri.queryParameters;
            return ProductsScreen(
              initialCategoryId: int.tryParse(params['category'] ?? ''),
              discountedOnly: params['discounted'] == 'true',
              focusSearch: params['focus'] == 'search',
            );
          },
        ),
        // ---- Shopping ----
        GoRoute(path: '/cart', builder: (context, state) => const CartScreen()),
        GoRoute(path: '/checkout', builder: (context, state) => const CheckoutScreen()),
        GoRoute(
          path: '/addresses',
          builder: (context, state) => AddressListScreen(
            // `?select=true` turns the list into a picker for checkout.
            selecting: state.uri.queryParameters['select'] == 'true',
          ),
          routes: [
            GoRoute(
              path: 'new',
              builder: (context, state) => const AddressFormScreen(),
            ),
            GoRoute(
              path: ':id/edit',
              builder: (context, state) =>
                  AddressFormScreen(existing: state.extra as Address?),
            ),
          ],
        ),
        GoRoute(
          path: '/product/:slug',
          builder: (context, state) =>
              ProductDetailScreen(slug: state.pathParameters['slug']!),
        ),
      ],
      errorBuilder: (context, state) => Scaffold(
        appBar: AppBar(title: const Text('Not found')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('That page could not be found.'),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => context.go('/home'),
                  child: const Text('Back to shop'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
