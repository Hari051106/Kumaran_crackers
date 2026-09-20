/// One order: what was bought, where it is going, and how far along it is.
///
/// Every figure shown is the snapshot the server took when the order was
/// placed. Nothing is recalculated here, so the amount on this screen is the
/// amount that was charged even if the catalogue price has changed since.
library;

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

class OrderDetailScreen extends ConsumerStatefulWidget {
  const OrderDetailScreen({
    super.key,
    required this.orderNumber,
    this.justPlaced = false,
  });

  final String orderNumber;

  /// True when the shopper has just arrived from checkout.
  final bool justPlaced;

  @override
  ConsumerState<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends ConsumerState<OrderDetailScreen> {
  bool _cancelling = false;

  @override
  Widget build(BuildContext context) {
    final order = ref.watch(orderDetailProvider(widget.orderNumber));

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.orderNumber),
        // Arriving from checkout, "back" should lead to the shop rather than
        // to the basket that no longer exists.
        leading: widget.justPlaced
            ? IconButton(
                icon: const Icon(Icons.close_rounded),
                tooltip: 'Back to shop',
                onPressed: () => context.go('/home'),
              )
            : null,
      ),
      body: order.when(
        loading: () => const LoadingView(label: 'Loading your order…'),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.invalidate(orderDetailProvider(widget.orderNumber)),
        ),
        data: _buildOrder,
      ),
    );
  }

  Widget _buildOrder(OrderDetail order) => ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
        children: [
          if (widget.justPlaced) const _PlacedBanner(),
          _Header(order: order),
          const SizedBox(height: 14),
          if (order.status.isCancelled)
            _CancelledCard(order: order)
          else
            _Timeline(steps: order.timeline),
          const SizedBox(height: 14),
          _ItemsCard(order: order),
          const SizedBox(height: 14),
          _TotalsCard(totals: order.totals),
          const SizedBox(height: 14),
          _AddressCard(address: order.deliveryAddress, status: order.status),
          if (order.isCancellableByCustomer) ...[
            const SizedBox(height: 18),
            OutlinedButton.icon(
              key: const Key('cancel-order'),
              onPressed: _cancelling ? null : () => _confirmCancel(order),
              icon: _cancelling
                  ? const SizedBox(
                      width: 17,
                      height: 17,
                      child: CircularProgressIndicator(strokeWidth: 2.2),
                    )
                  : const Icon(Icons.cancel_outlined, size: 19),
              label: const Text('Cancel this order'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppTheme.outOfStock,
                side: BorderSide(color: AppTheme.outOfStock.withValues(alpha: 0.4)),
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'You can cancel until we start packing your order.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12.5, color: AppTheme.muted),
            ),
          ],
        ],
      );

  Future<void> _confirmCancel(OrderDetail order) async {
    final reasonController = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel this order?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Order ${order.orderNumber} for ${formatMoney(order.total)} will be '
              'withdrawn and the items returned to the shop.',
              style: const TextStyle(height: 1.4),
            ),
            const SizedBox(height: 14),
            TextField(
              key: const Key('cancel-reason'),
              controller: reasonController,
              maxLength: 300,
              decoration: const InputDecoration(
                labelText: 'Reason (optional)',
                counterText: '',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Keep it'),
          ),
          FilledButton(
            key: const Key('confirm-cancel-order'),
            style: FilledButton.styleFrom(backgroundColor: AppTheme.outOfStock),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Cancel order'),
          ),
        ],
      ),
    );

    final reason = reasonController.text.trim();
    reasonController.dispose();
    if (!(confirmed ?? false) || !mounted) return;

    setState(() => _cancelling = true);
    try {
      await ref
          .read(orderRepositoryProvider)
          .cancel(order.orderNumber, reason: reason.isEmpty ? null : reason);
      if (!mounted) return;
      // The history rows and this screen both changed.
      ref
        ..invalidate(orderDetailProvider(order.orderNumber))
        ..invalidate(myOrdersProvider);
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(content: Text('${order.orderNumber} has been cancelled.')),
        );
    } on ApiException catch (error) {
      // The server is the authority on whether it is too late; show its reason.
      if (!mounted) return;
      ref.invalidate(orderDetailProvider(order.orderNumber));
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) setState(() => _cancelling = false);
    }
  }
}

class _PlacedBanner extends StatelessWidget {
  const _PlacedBanner();

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('order-placed-banner'),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.inStock.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.inStock.withValues(alpha: 0.3)),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.check_circle_rounded, color: AppTheme.inStock, size: 22),
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Thank you — your order is placed',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: AppTheme.ink,
                      fontSize: 15,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Celebrate Every Moment with Kumaran Crackers. '
                    'We will keep this page updated as it moves.',
                    style: TextStyle(fontSize: 12.5, color: AppTheme.muted, height: 1.4),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
}

class _Header extends StatelessWidget {
  const _Header({required this.order});

  final OrderDetail order;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Placed ${formatDateTime(order.placedAt)}',
                      style: const TextStyle(fontSize: 12.5, color: AppTheme.muted),
                    ),
                    const SizedBox(height: 8),
                    OrderStatusChip(status: order.status, label: order.statusLabel),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  const Text(
                    'Total paid',
                    style: TextStyle(fontSize: 12, color: AppTheme.muted),
                  ),
                  Text(
                    formatMoney(order.total),
                    key: const Key('order-total'),
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      color: AppTheme.ink,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      );
}

class _CancelledCard extends StatelessWidget {
  const _CancelledCard({required this.order});

  final OrderDetail order;

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('order-cancelled'),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.outOfStock.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.outOfStock.withValues(alpha: 0.28)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.cancel_outlined, size: 19, color: AppTheme.outOfStock),
                const SizedBox(width: 9),
                Text(
                  order.cancelledAt == null
                      ? 'This order was cancelled'
                      : 'Cancelled on ${formatDate(order.cancelledAt!)}',
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: AppTheme.outOfStock,
                  ),
                ),
              ],
            ),
            if ((order.cancellationReason ?? '').trim().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                order.cancellationReason!,
                style: const TextStyle(fontSize: 13, height: 1.4, color: Color(0xFF8A2121)),
              ),
            ],
            const SizedBox(height: 8),
            const Text(
              'Nothing was dispatched and the items went back to the shop.',
              style: TextStyle(fontSize: 12.5, color: AppTheme.muted, height: 1.4),
            ),
          ],
        ),
      );
}

/// The tracking rail. A stage is filled once the server says it was reached;
/// the app never guesses progress from elapsed time.
class _Timeline extends StatelessWidget {
  const _Timeline({required this.steps});

  final List<TimelineStep> steps;

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('order-timeline'),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 6),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Tracking',
                style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.ink),
              ),
              const SizedBox(height: 14),
              ...List.generate(steps.length, (index) {
                final isLast = index == steps.length - 1;
                return _TimelineRow(
                  step: steps[index],
                  isLast: isLast,
                  // The rail below a step is only filled once the *next* stage
                  // has been reached, so progress is never overstated.
                  nextReached: !isLast && steps[index + 1].reached,
                );
              }),
            ],
          ),
        ),
      );
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({
    required this.step,
    required this.isLast,
    required this.nextReached,
  });

  final TimelineStep step;
  final bool isLast;
  final bool nextReached;

  @override
  Widget build(BuildContext context) {
    final active = step.reached;
    final colour = active ? AppTheme.brand : AppTheme.hairline;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  color: active ? AppTheme.brand : Colors.white,
                  shape: BoxShape.circle,
                  border: Border.all(color: colour, width: 2),
                ),
                child: active
                    ? const Icon(Icons.check_rounded, size: 13, color: Colors.white)
                    : null,
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: nextReached ? AppTheme.brand : AppTheme.hairline,
                  ),
                ),
            ],
          ),
          const SizedBox(width: 13),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 14 : 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    step.label,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: step.isCurrent ? FontWeight.w700 : FontWeight.w500,
                      color: active ? AppTheme.ink : AppTheme.muted,
                    ),
                  ),
                  if (step.reachedAt != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        formatDateTime(step.reachedAt!),
                        style: const TextStyle(fontSize: 12, color: AppTheme.muted),
                      ),
                    ),
                  if (step.isCurrent)
                    const Padding(
                      padding: EdgeInsets.only(top: 3),
                      child: Text(
                        'Current stage',
                        style: TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.brand,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ItemsCard extends StatelessWidget {
  const _ItemsCard({required this.order});

  final OrderDetail order;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${order.itemCount} ${order.itemCount == 1 ? 'item' : 'items'}',
                style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.ink),
              ),
              const SizedBox(height: 12),
              ...order.lines.map(
                (line) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 26,
                        height: 26,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: AppTheme.hairline,
                          borderRadius: BorderRadius.circular(7),
                        ),
                        child: Text(
                          '${line.quantity}',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.ink,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              line.productName,
                              style: const TextStyle(fontSize: 13.5, color: AppTheme.ink),
                            ),
                            Text(
                              '${formatMoney(line.unitPrice)} each · SKU ${line.productSku}',
                              style: const TextStyle(fontSize: 11.5, color: AppTheme.muted),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        formatMoney(line.lineTotal),
                        style: const TextStyle(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.ink,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      );
}

class _TotalsCard extends StatelessWidget {
  const _TotalsCard({required this.totals});

  final OrderTotals totals;

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('order-totals'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              const Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Bill',
                  style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.ink),
                ),
              ),
              const SizedBox(height: 12),
              _row('Subtotal', formatMoney(totals.subtotal)),
              if (compareMoney(totals.discount, '0.00') > 0)
                _row(
                  'Discount',
                  '- ${formatMoney(totals.discount)}',
                  valueColor: AppTheme.inStock,
                ),
              _row(
                'Delivery charge',
                compareMoney(totals.deliveryCharge, '0.00') == 0
                    ? 'FREE'
                    : formatMoney(totals.deliveryCharge),
                valueColor: compareMoney(totals.deliveryCharge, '0.00') == 0
                    ? AppTheme.inStock
                    : null,
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

class _AddressCard extends StatelessWidget {
  const _AddressCard({required this.address, required this.status});

  final DeliverySnapshot address;
  final OrderStatus status;

  /// Says where the order is going, or where it went - never both.
  String get _heading => switch (status) {
        OrderStatus.delivered => 'Delivered to',
        OrderStatus.cancelled => 'Delivery address',
        _ => 'Delivering to',
      };

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('order-address'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.location_on_outlined, size: 18, color: AppTheme.brand),
                  const SizedBox(width: 8),
                  Text(
                    _heading,
                    style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.ink),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                address.fullName,
                style: const TextStyle(fontWeight: FontWeight.w600, color: AppTheme.ink),
              ),
              const SizedBox(height: 3),
              Text(
                address.singleLine,
                style: const TextStyle(fontSize: 13.5, height: 1.45, color: AppTheme.muted),
              ),
              Text(address.phone, style: const TextStyle(fontSize: 13, color: AppTheme.muted)),
              if ((address.instructions ?? '').trim().isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  'Note: ${address.instructions}',
                  style: const TextStyle(fontSize: 12.5, color: AppTheme.muted),
                ),
              ],
            ],
          ),
        ),
      );
}
