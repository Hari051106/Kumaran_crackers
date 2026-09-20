/// The basket.
///
/// Every figure shown here is the server's. The app does no money arithmetic,
/// so what the customer reads is what they will be charged.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_exception.dart';
import '../../core/money.dart';
import '../../core/theme.dart';
import '../../models/cart.dart';
import '../../providers/providers.dart';
import '../../widgets/product_card.dart';
import '../../widgets/state_views.dart';

class CartScreen extends ConsumerStatefulWidget {
  const CartScreen({super.key});

  @override
  ConsumerState<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends ConsumerState<CartScreen> {
  /// Line ids with a request in flight, so their stepper can be disabled.
  final _busyLines = <int>{};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(cartProvider.notifier).load();
    });
  }

  Future<void> _run(int lineId, Future<void> Function() action) async {
    setState(() => _busyLines.add(lineId));
    try {
      await action();
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _busyLines.remove(lineId));
    }
  }

  @override
  Widget build(BuildContext context) {
    final cart = ref.watch(cartProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Basket'),
        actions: [
          cart.maybeWhen(
            data: (data) => data.isEmpty
                ? const SizedBox.shrink()
                : TextButton(
                    key: const Key('clear-basket'),
                    onPressed: _confirmClear,
                    child: const Text('Clear'),
                  ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: cart.when(
        loading: () => const LoadingView(label: 'Loading your basket…'),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.read(cartProvider.notifier).load(),
        ),
        data: (data) => data.isEmpty ? _empty(context) : _basket(data),
      ),
      bottomNavigationBar: cart.maybeWhen(
        data: (data) => data.isEmpty ? null : _CheckoutBar(cart: data),
        orElse: () => null,
      ),
    );
  }

  Widget _empty(BuildContext context) => EmptyView(
        title: 'Your basket is empty',
        message: 'Add a few crackers and they will appear here.',
        icon: Icons.shopping_bag_outlined,
        action: FilledButton(
          onPressed: () => context.go('/home'),
          child: const Text('Start shopping'),
        ),
      );

  Widget _basket(Cart cart) => RefreshIndicator(
        color: AppTheme.brand,
        onRefresh: () => ref.read(cartProvider.notifier).load(),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: [
            if (cart.problems.isNotEmpty) _ProblemBanner(problems: cart.problems),
            ...cart.lines.map(
              (line) => _CartLineTile(
                line: line,
                busy: _busyLines.contains(line.id),
                onQuantityChanged: (quantity) => _run(
                  line.id,
                  () => ref
                      .read(cartProvider.notifier)
                      .setQuantity(lineId: line.id, quantity: quantity),
                ),
                onRemove: () => _run(
                  line.id,
                  () => ref.read(cartProvider.notifier).remove(line.id),
                ),
              ),
            ),
            const SizedBox(height: 8),
            _TotalsCard(totals: cart.totals),
          ],
        ),
      );

  Future<void> _confirmClear() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Empty your basket?'),
        content: const Text('Everything in it will be removed.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-clear'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Empty basket'),
          ),
        ],
      ),
    );
    if (confirmed ?? false) {
      await _run(-1, () => ref.read(cartProvider.notifier).clear());
    }
  }
}

class _ProblemBanner extends StatelessWidget {
  const _ProblemBanner({required this.problems});

  final List<String> problems;

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('cart-problems'),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.lowStock.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.lowStock.withValues(alpha: 0.35)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.warning_amber_rounded, size: 18, color: AppTheme.lowStock),
                SizedBox(width: 8),
                Text(
                  'Please check your basket',
                  style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.lowStock),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ...problems.map(
              (problem) => Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Text(
                  problem,
                  style: const TextStyle(
                    fontSize: 13,
                    height: 1.35,
                    color: Color(0xFF6B4A00),
                  ),
                ),
              ),
            ),
          ],
        ),
      );
}

class _CartLineTile extends StatelessWidget {
  const _CartLineTile({
    required this.line,
    required this.busy,
    required this.onQuantityChanged,
    required this.onRemove,
  });

  final CartLine line;
  final bool busy;
  final ValueChanged<int> onQuantityChanged;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final discounted = compareMoney(line.lineDiscount, '0.00') > 0;
    // Never offer more than the shelf holds.
    final maximum = line.availableQuantity < 99 ? line.availableQuantity : 99;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: ProductImageBox(url: line.product.primaryImageUrl, size: 72),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        line.product.name,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 14.5,
                          height: 1.25,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.ink,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        line.product.categoryName,
                        style: const TextStyle(fontSize: 12, color: AppTheme.muted),
                      ),
                      const SizedBox(height: 7),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.baseline,
                        textBaseline: TextBaseline.alphabetic,
                        children: [
                          Text(
                            formatMoney(line.unitPrice),
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.ink,
                            ),
                          ),
                          if (discounted) ...[
                            const SizedBox(width: 6),
                            Text(
                              formatMoney(line.unitMrp),
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppTheme.muted,
                                decoration: TextDecoration.lineThrough,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      formatMoney(line.lineTotal),
                      key: Key('line-total-${line.id}'),
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.ink,
                      ),
                    ),
                    if (discounted)
                      Text(
                        'saved ${formatMoney(line.lineDiscount)}',
                        style: const TextStyle(fontSize: 11, color: AppTheme.inStock),
                      ),
                  ],
                ),
              ],
            ),
            if (line.hasProblem)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Row(
                  children: [
                    const Icon(
                      Icons.error_outline_rounded,
                      size: 15,
                      color: AppTheme.outOfStock,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        line.problem!,
                        style: const TextStyle(fontSize: 12, color: AppTheme.outOfStock),
                      ),
                    ),
                  ],
                ),
              ),
            const Divider(height: 22),
            Row(
              children: [
                _QuantityStepper(
                  quantity: line.quantity,
                  maximum: maximum,
                  enabled: !busy,
                  onChanged: onQuantityChanged,
                  lineId: line.id,
                ),
                const Spacer(),
                TextButton.icon(
                  key: Key('remove-line-${line.id}'),
                  onPressed: busy ? null : onRemove,
                  icon: const Icon(Icons.delete_outline_rounded, size: 18),
                  label: const Text('Remove'),
                  style: TextButton.styleFrom(foregroundColor: AppTheme.muted),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _QuantityStepper extends StatelessWidget {
  const _QuantityStepper({
    required this.quantity,
    required this.maximum,
    required this.enabled,
    required this.onChanged,
    required this.lineId,
  });

  final int quantity;
  final int maximum;
  final bool enabled;
  final ValueChanged<int> onChanged;
  final int lineId;

  @override
  Widget build(BuildContext context) => Container(
        decoration: BoxDecoration(
          border: Border.all(color: AppTheme.hairline),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              key: Key('decrease-$lineId'),
              visualDensity: VisualDensity.compact,
              tooltip: 'Reduce quantity',
              onPressed: enabled && quantity > 1 ? () => onChanged(quantity - 1) : null,
              icon: const Icon(Icons.remove_rounded, size: 18),
            ),
            SizedBox(
              width: 26,
              child: Text(
                '$quantity',
                key: Key('quantity-$lineId'),
                textAlign: TextAlign.center,
                style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.ink),
              ),
            ),
            IconButton(
              key: Key('increase-$lineId'),
              visualDensity: VisualDensity.compact,
              tooltip: 'Increase quantity',
              onPressed: enabled && quantity < maximum ? () => onChanged(quantity + 1) : null,
              icon: const Icon(Icons.add_rounded, size: 18),
            ),
          ],
        ),
      );
}

class _TotalsCard extends StatelessWidget {
  const _TotalsCard({required this.totals});

  final BasketTotals totals;

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('basket-totals'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              _row('Subtotal', formatMoney(totals.subtotal)),
              if (compareMoney(totals.discount, '0.00') > 0)
                _row(
                  'Discount',
                  '- ${formatMoney(totals.discount)}',
                  valueColor: AppTheme.inStock,
                ),
              _row(
                'Delivery',
                totals.freeDeliveryApplied ? 'FREE' : formatMoney(totals.deliveryCharge),
                valueColor: totals.freeDeliveryApplied ? AppTheme.inStock : null,
              ),
              if (!totals.freeDeliveryApplied &&
                  compareMoney(totals.amountToFreeDelivery, '0.00') > 0)
                Padding(
                  padding: const EdgeInsets.only(top: 6, bottom: 2),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.local_shipping_outlined,
                        size: 15,
                        color: AppTheme.brand,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Spend ${formatMoney(totals.amountToFreeDelivery)} more for '
                          'free delivery',
                          style: const TextStyle(fontSize: 12, color: AppTheme.brand),
                        ),
                      ),
                    ],
                  ),
                ),
              const Divider(height: 22),
              _row('Total', formatMoney(totals.total), emphasised: true),
            ],
          ),
        ),
      );

  Widget _row(
    String label,
    String value, {
    bool emphasised = false,
    Color? valueColor,
  }) =>
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: emphasised ? 15.5 : 14,
                fontWeight: emphasised ? FontWeight.w700 : FontWeight.w400,
                color: emphasised ? AppTheme.ink : AppTheme.muted,
              ),
            ),
            Text(
              value,
              style: TextStyle(
                fontSize: emphasised ? 18 : 14,
                fontWeight: emphasised ? FontWeight.w800 : FontWeight.w600,
                color: valueColor ?? AppTheme.ink,
              ),
            ),
          ],
        ),
      );
}

class _CheckoutBar extends StatelessWidget {
  const _CheckoutBar({required this.cart});

  final Cart cart;

  @override
  Widget build(BuildContext context) => SafeArea(
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(top: BorderSide(color: AppTheme.hairline)),
          ),
          child: Row(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Total', style: TextStyle(fontSize: 12, color: AppTheme.muted)),
                  Text(
                    formatMoney(cart.totals.total),
                    style: const TextStyle(
                      fontSize: 19,
                      fontWeight: FontWeight.w800,
                      color: AppTheme.ink,
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 16),
              Expanded(
                child: FilledButton(
                  key: const Key('go-to-checkout'),
                  // The server decides whether this basket can be bought.
                  onPressed: cart.isPurchasable ? () => context.push('/checkout') : null,
                  child: Text(cart.isPurchasable ? 'Checkout' : 'Check your basket'),
                ),
              ),
            ],
          ),
        ),
      );
}
