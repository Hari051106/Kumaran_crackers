/// Riverpod wiring for the whole application.
library;

import 'dart:async';

import 'package:flutter/foundation.dart' show ChangeNotifier;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../core/token_storage.dart';
import '../models/category.dart';
import '../models/paged.dart';
import '../models/product.dart';
import '../models/address.dart';
import '../models/cart.dart';
import '../models/order.dart';
import '../models/user.dart';
import '../repositories/auth_repository.dart';
import '../repositories/catalog_repository.dart';
import '../repositories/order_repository.dart';
import '../repositories/shopping_repository.dart';

// ---- Infrastructure ---------------------------------------------------------
/// Broadcasts that a refresh failed and the session is gone.
///
/// This exists so the API client never has to reach back into the auth
/// provider. Doing that directly would make apiClient -> auth -> authRepository
/// -> apiClient a dependency cycle, which Riverpod cannot resolve.
class SessionExpirySignal extends ChangeNotifier {
  void signal() => notifyListeners();
}

final sessionExpiryProvider = Provider<SessionExpirySignal>((ref) {
  final signal = SessionExpirySignal();
  ref.onDispose(signal.dispose);
  return signal;
});

final tokenStorageProvider = Provider<TokenStorage>((ref) => TokenStorage());

final apiClientProvider = Provider<ApiClient>((ref) {
  final expiry = ref.watch(sessionExpiryProvider);
  return ApiClient(tokenStorage: ref.watch(tokenStorageProvider))
    ..onSessionExpired = expiry.signal;
});

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(
    client: ref.watch(apiClientProvider),
    tokenStorage: ref.watch(tokenStorageProvider),
  ),
);

final catalogRepositoryProvider = Provider<CatalogRepository>(
  (ref) => CatalogRepository(ref.watch(apiClientProvider)),
);

final shoppingRepositoryProvider = Provider<ShoppingRepository>(
  (ref) => ShoppingRepository(ref.watch(apiClientProvider)),
);

final orderRepositoryProvider = Provider<OrderRepository>(
  (ref) => OrderRepository(ref.watch(apiClientProvider)),
);

// ---- Authentication ---------------------------------------------------------
enum AuthStatus { checking, signedIn, signedOut }

class AuthState {
  const AuthState({required this.status, this.user});

  const AuthState.checking() : this(status: AuthStatus.checking);
  const AuthState.signedOut() : this(status: AuthStatus.signedOut);

  final AuthStatus status;
  final AppUser? user;

  bool get isSignedIn => status == AuthStatus.signedIn && user != null;
  bool get isChecking => status == AuthStatus.checking;
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._repository) : super(const AuthState.checking());

  final AuthRepository _repository;

  /// Restore a stored session at launch, so a returning shopper is not asked
  /// to sign in again.
  Future<void> restore() async {
    final user = await _repository.restore();
    if (!mounted) return;
    state = user == null
        ? const AuthState.signedOut()
        : AuthState(status: AuthStatus.signedIn, user: user);
  }

  Future<void> login({required String email, required String password}) async {
    final user = await _repository.login(email: email, password: password);
    if (!mounted) return;
    state = AuthState(status: AuthStatus.signedIn, user: user);
  }

  Future<void> register({
    required String email,
    required String password,
    required String fullName,
    String? phone,
  }) async {
    final user = await _repository.register(
      email: email,
      password: password,
      fullName: fullName,
      phone: phone,
    );
    if (!mounted) return;
    state = AuthState(status: AuthStatus.signedIn, user: user);
  }

  Future<void> logout() async {
    await _repository.logout();
    if (!mounted) return;
    state = const AuthState.signedOut();
  }

  /// Called by the API client when a refresh fails irrecoverably.
  void handleExpiry() {
    if (!mounted) return;
    state = const AuthState.signedOut();
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final notifier = AuthNotifier(ref.watch(authRepositoryProvider));

  // Listening to the signal keeps the dependency one-way.
  final expiry = ref.watch(sessionExpiryProvider);
  expiry.addListener(notifier.handleExpiry);
  ref.onDispose(() => expiry.removeListener(notifier.handleExpiry));

  return notifier;
});

// ---- Catalogue --------------------------------------------------------------
final categoriesProvider = FutureProvider<List<Category>>(
  (ref) => ref.watch(catalogRepositoryProvider).categories(),
);

/// A single page of products for a given query.
final productsProvider = FutureProvider.family<Paged<Product>, ProductQuery>(
  (ref, query) => ref.watch(catalogRepositoryProvider).products(query),
);

final productDetailProvider = FutureProvider.family<Product, String>(
  (ref, slug) => ref.watch(catalogRepositoryProvider).productBySlug(slug),
);

// ---- Home sections ----------------------------------------------------------
/// Admin-curated highlights.
final featuredProductsProvider = FutureProvider<List<Product>>((ref) async {
  final page = await ref.watch(catalogRepositoryProvider).products(
        const ProductQuery(featuredOnly: true, pageSize: 10),
      );
  return page.items;
});

/// Anything priced below its MRP.
final offerProductsProvider = FutureProvider<List<Product>>((ref) async {
  final page = await ref.watch(catalogRepositoryProvider).products(
        const ProductQuery(
          discountedOnly: true,
          sort: ProductSort.biggestDiscount,
          pageSize: 10,
        ),
      );
  return page.items;
});

/// Most recently added to the catalogue.
///
/// Note there is deliberately no "best sellers" section: nothing has been sold
/// until the order system exists, so such a row would be an arbitrary ordering
/// dressed up as popularity.
final newArrivalsProvider = FutureProvider<List<Product>>((ref) async {
  final page = await ref.watch(catalogRepositoryProvider).products(
        const ProductQuery(sort: ProductSort.newest, pageSize: 10),
      );
  return page.items;
});


// ---- Cart -------------------------------------------------------------------
/// The basket, as priced by the server.
///
/// Every mutation returns the recomputed basket, so the notifier simply stores
/// what came back rather than adjusting totals itself. The app never does
/// money arithmetic.
class CartNotifier extends StateNotifier<AsyncValue<Cart>> {
  CartNotifier(this._repository) : super(const AsyncValue.loading());

  final ShoppingRepository _repository;

  Future<void> load() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(_repository.cart);
  }

  /// Runs a mutation and stores the basket the server returns.
  ///
  /// Rethrows so the caller can surface the reason - a sell-out, say - while
  /// leaving the previous basket on screen.
  Future<void> _mutate(Future<Cart> Function() action) async {
    try {
      final updated = await action();
      if (mounted) state = AsyncValue.data(updated);
    } catch (error) {
      // Refresh anyway: the failure often means the catalogue moved on.
      if (mounted) unawaited(load());
      rethrow;
    }
  }

  Future<void> add({required int productId, int quantity = 1}) =>
      _mutate(() => _repository.addItem(productId: productId, quantity: quantity));

  Future<void> setQuantity({required int lineId, required int quantity}) =>
      _mutate(() => _repository.setQuantity(lineId: lineId, quantity: quantity));

  Future<void> remove(int lineId) => _mutate(() => _repository.removeItem(lineId));

  Future<void> clear() => _mutate(_repository.clear);

  /// Forget the basket when the customer signs out.
  void reset() {
    if (mounted) state = const AsyncValue.loading();
  }
}

final cartProvider = StateNotifierProvider<CartNotifier, AsyncValue<Cart>>(
  (ref) => CartNotifier(ref.watch(shoppingRepositoryProvider)),
);

/// How many units are in the basket, for the badge on the home screen.
final cartCountProvider = Provider<int>((ref) {
  return ref.watch(cartProvider).maybeWhen(
        data: (cart) => cart.itemCount,
        orElse: () => 0,
      );
});

// ---- Addresses --------------------------------------------------------------
final addressesProvider = FutureProvider<List<Address>>(
  (ref) => ref.watch(shoppingRepositoryProvider).addresses(),
);

/// The address checkout should start with.
final defaultAddressProvider = Provider<AsyncValue<Address?>>((ref) {
  return ref.watch(addressesProvider).whenData((list) {
    if (list.isEmpty) return null;
    return list.firstWhere((a) => a.isDefault, orElse: () => list.first);
  });
});

// ---- Checkout ---------------------------------------------------------------
final checkoutQuoteProvider = FutureProvider.family<CheckoutQuote, int>(
  (ref, addressId) => ref.watch(shoppingRepositoryProvider).quote(addressId),
);

// ---- Orders -----------------------------------------------------------------
/// The first page of the customer's order history.
///
/// Later pages are appended by the history screen; keeping page one in a
/// provider means placing or cancelling an order can simply invalidate it.
final myOrdersProvider = FutureProvider<Paged<OrderSummary>>(
  (ref) => ref.watch(orderRepositoryProvider).myOrders(),
);

final orderDetailProvider = FutureProvider.family<OrderDetail, String>(
  (ref, orderNumber) => ref.watch(orderRepositoryProvider).detail(orderNumber),
);
