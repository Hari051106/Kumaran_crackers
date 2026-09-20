/// Order history.
///
/// A signed-in shopper's own orders, newest first. The list is paged; the
/// first page comes from a provider so placing or cancelling an order can
/// simply invalidate it.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_exception.dart';
import '../../core/dates.dart';
import '../../core/money.dart';
import '../../core/theme.dart';
import '../../models/order.dart';
import '../../providers/providers.dart';
import '../../widgets/order_status_chip.dart';
import '../../widgets/state_views.dart';

class OrdersScreen extends ConsumerStatefulWidget {
  const OrdersScreen({super.key});

  @override
  ConsumerState<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends ConsumerState<OrdersScreen> {
  final _scrollController = ScrollController();

  /// Pages beyond the first, appended as the shopper scrolls.
  final List<OrderSummary> _extraPages = [];
  int _lastPage = 1;
  bool _loadingMore = false;
  bool _hasMore = true;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_onScroll)
      ..dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients || _loadingMore || !_hasMore) return;
    final position = _scrollController.position;
    if (position.pixels >= position.maxScrollExtent - 300) {
      unawaited(_loadMore());
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || !_hasMore) return;
    setState(() => _loadingMore = true);
    try {
      final next = _lastPage + 1;
      final page = await ref.read(orderRepositoryProvider).myOrders(page: next);
      if (!mounted) return;
      setState(() {
        _lastPage = next;
        _extraPages.addAll(page.items);
        _hasMore = page.meta.hasNext;
      });
    } on ApiException {
      // Keep what is on screen; a later scroll can try again.
      if (mounted) setState(() => _hasMore = false);
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _refresh() async {
    setState(() {
      _extraPages.clear();
      _lastPage = 1;
      _hasMore = true;
    });
    ref.invalidate(myOrdersProvider);
    await ref.read(myOrdersProvider.future);
  }

  @override
  Widget build(BuildContext context) {
    final signedIn = ref.watch(authProvider).isSignedIn;

    return Scaffold(
      appBar: AppBar(title: const Text('My orders')),
      body: signedIn ? _list() : _signedOut(context),
    );
  }

  Widget _signedOut(BuildContext context) => EmptyView(
        title: 'Sign in to see your orders',
        message: 'Your order history and tracking live in your account.',
        icon: Icons.receipt_long_outlined,
        action: FilledButton(
          key: const Key('orders-sign-in'),
          onPressed: () => context.push('/login'),
          child: const Text('Sign in'),
        ),
      );

  Widget _list() {
    final firstPage = ref.watch(myOrdersProvider);

    return firstPage.when(
      loading: () => const LoadingView(label: 'Loading your orders…'),
      error: (error, _) => ErrorView(
        error: error,
        onRetry: () => ref.invalidate(myOrdersProvider),
      ),
      data: (page) {
        if (page.items.isEmpty) {
          return EmptyView(
            title: 'No orders yet',
            message: 'When you place an order it will appear here, with live tracking.',
            icon: Icons.receipt_long_outlined,
            action: FilledButton(
              key: const Key('orders-start-shopping'),
              onPressed: () => context.go('/home'),
              child: const Text('Start shopping'),
            ),
          );
        }

        final orders = [...page.items, ..._extraPages];
        return RefreshIndicator(
          color: AppTheme.brand,
          onRefresh: _refresh,
          child: ListView.separated(
            key: const Key('orders-list'),
            controller: _scrollController,
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
            itemCount: orders.length + (_loadingMore ? 1 : 0),
            separatorBuilder: (context, index) => const SizedBox(height: 10),
            itemBuilder: (context, index) {
              if (index >= orders.length) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 18),
                  child: Center(
                    child: SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(strokeWidth: 2.4),
                    ),
                  ),
                );
              }
              return _OrderRow(order: orders[index]);
            },
          ),
        );
      },
    );
  }
}

class _OrderRow extends StatelessWidget {
  const _OrderRow({required this.order});

  final OrderSummary order;

  @override
  Widget build(BuildContext context) => Card(
        child: InkWell(
          key: Key('order-row-${order.orderNumber}'),
          borderRadius: BorderRadius.circular(14),
          onTap: () => context.push('/orders/${order.orderNumber}'),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        order.orderNumber,
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.ink,
                        ),
                      ),
                    ),
                    OrderStatusChip(status: order.status, label: order.statusLabel),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  formatDateTime(order.placedAt),
                  style: const TextStyle(fontSize: 12.5, color: AppTheme.muted),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Text(
                      '${order.itemCount} ${order.itemCount == 1 ? 'item' : 'items'}',
                      style: const TextStyle(fontSize: 13, color: AppTheme.muted),
                    ),
                    const Spacer(),
                    Text(
                      formatMoney(order.total),
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.ink,
                      ),
                    ),
                    const SizedBox(width: 4),
                    const Icon(Icons.chevron_right_rounded, color: AppTheme.muted),
                  ],
                ),
              ],
            ),
          ),
        ),
      );
}
