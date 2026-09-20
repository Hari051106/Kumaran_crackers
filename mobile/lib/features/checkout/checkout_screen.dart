/// Checkout review.
///
/// Shows the server's quote: the items, the delivery address, and the exact
/// amount payable. Nothing is calculated here — the figures come from
/// `/checkout/quote`, which is the same pricing the order will be created
/// with, so the customer cannot be quoted one amount and charged another.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_exception.dart';
import '../../core/money.dart';
import '../../core/theme.dart';
import '../../models/address.dart';
import '../../models/cart.dart';
import '../../providers/providers.dart';
import '../../widgets/state_views.dart';

class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key});

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  Address? _selected;

  @override
  Widget build(BuildContext context) {
    final addresses = ref.watch(addressesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: addresses.when(
        loading: () => const LoadingView(label: 'Getting ready…'),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.invalidate(addressesProvider),
        ),
        data: (items) {
          if (items.isEmpty) return _needsAddress(context);

          // Default to the customer's default address on first build.
          final address = _selected ??
              items.firstWhere((a) => a.isDefault, orElse: () => items.first);
          return _quoteView(address);
        },
      ),
    );
  }

  Widget _needsAddress(BuildContext context) => EmptyView(
        title: 'Where should we deliver?',
        message: 'Add a delivery address to continue with your order.',
        icon: Icons.location_on_outlined,
        action: FilledButton(
          key: const Key('checkout-add-address'),
          onPressed: () => context.push('/addresses/new'),
          child: const Text('Add an address'),
        ),
      );

  Widget _quoteView(Address address) {
    final quote = ref.watch(checkoutQuoteProvider(address.id));

    return quote.when(
      loading: () => const LoadingView(label: 'Checking availability and prices…'),
      error: (error, _) => ErrorView(
        error: error,
        onRetry: () => ref.invalidate(checkoutQuoteProvider(address.id)),
      ),
      data: (data) => Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              children: [
                if (data.blockers.isNotEmpty) _Blockers(blockers: data.blockers),
                _AddressCard(
                  address: data.deliveryAddress,
                  onChange: () => _pickAddress(context),
                ),
                const SizedBox(height: 14),
                _ItemsCard(cart: data.cart),
                const SizedBox(height: 14),
                _PaymentSummary(totals: data.cart.totals),
                const SizedBox(height: 14),
                const _AgeNotice(),
              ],
            ),
          ),
          _PlaceOrderBar(quote: data),
        ],
      ),
    );
  }

  Future<void> _pickAddress(BuildContext context) async {
    final chosen = await context.push<Address>('/addresses?select=true');
    if (chosen != null && mounted) setState(() => _selected = chosen);
  }
}

class _Blockers extends StatelessWidget {
  const _Blockers({required this.blockers});

  final List<String> blockers;

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('checkout-blockers'),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.outOfStock.withValues(alpha: 0.07),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.outOfStock.withValues(alpha: 0.3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'We cannot place this order yet',
              style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.outOfStock),
            ),
            const SizedBox(height: 8),
            ...blockers.map(
              (blocker) => Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Text(
                  blocker,
                  style: const TextStyle(fontSize: 13, height: 1.35, color: Color(0xFF8A2121)),
                ),
              ),
            ),
          ],
        ),
      );
}

class _AddressCard extends StatelessWidget {
  const _AddressCard({required this.address, required this.onChange});

  final Address address;
  final VoidCallback onChange;

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('checkout-address'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.location_on_outlined, size: 18, color: AppTheme.brand),
                  const SizedBox(width: 8),
                  const Text(
                    'Delivering to',
                    style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.ink),
                  ),
                  const Spacer(),
                  TextButton(
                    key: const Key('change-address'),
                    onPressed: onChange,
                    child: const Text('Change'),
                  ),
                ],
              ),
              const SizedBox(height: 4),
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
            ],
          ),
        ),
      );
}

class _ItemsCard extends StatelessWidget {
  const _ItemsCard({required this.cart});

  final Cart cart;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${cart.itemCount} ${cart.itemCount == 1 ? 'item' : 'items'}',
                style: const TextStyle(fontWeight: FontWeight.w700, color: AppTheme.ink),
              ),
              const SizedBox(height: 12),
              ...cart.lines.map(
                (line) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
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
                              line.product.name,
                              style: const TextStyle(fontSize: 13.5, color: AppTheme.ink),
                            ),
                            Text(
                              '${formatMoney(line.unitPrice)} each',
                              style: const TextStyle(fontSize: 11.5, color: AppTheme.muted),
                            ),
                          ],
                        ),
                      ),
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

class _PaymentSummary extends StatelessWidget {
  const _PaymentSummary({required this.totals});

  final BasketTotals totals;

  @override
  Widget build(BuildContext context) => Card(
        key: const Key('checkout-summary'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              const Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Payment summary',
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
                totals.freeDeliveryApplied ? 'FREE' : formatMoney(totals.deliveryCharge),
                valueColor: totals.freeDeliveryApplied ? AppTheme.inStock : null,
              ),
              const Divider(height: 22),
              _row('Amount payable', formatMoney(totals.total), emphasised: true),
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

class _AgeNotice extends StatelessWidget {
  const _AgeNotice();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFF1F3F7),
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.shield_outlined, size: 18, color: AppTheme.muted),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Fireworks are sold to adults aged 18 and over. By ordering you confirm '
                'you meet the age requirement and that delivery to your area is permitted.',
                style: TextStyle(fontSize: 12.5, color: AppTheme.muted, height: 1.4),
              ),
            ),
          ],
        ),
      );
}

class _PlaceOrderBar extends ConsumerStatefulWidget {
  const _PlaceOrderBar({required this.quote});

  final CheckoutQuote quote;

  @override
  ConsumerState<_PlaceOrderBar> createState() => _PlaceOrderBarState();
}

class _PlaceOrderBarState extends ConsumerState<_PlaceOrderBar> {
  bool _placing = false;

  Future<void> _placeOrder() async {
    setState(() => _placing = true);
    try {
      final order = await ref
          .read(orderRepositoryProvider)
          .place(widget.quote.deliveryAddress.id);
      if (!mounted) return;

      // The basket became the order, and the history has a new row.
      ref
        ..invalidate(myOrdersProvider)
        ..invalidate(checkoutQuoteProvider);
      unawaited(ref.read(cartProvider.notifier).load());

      // Replace checkout in the stack: going "back" to it would show a quote
      // for a basket that no longer exists.
      context.pushReplacement('/orders/${order.orderNumber}', extra: true);
    } on ApiException catch (error) {
      // The server refuses for real reasons - a sell-out between the quote and
      // now, most often. Show its wording and refresh what is on screen.
      if (!mounted) return;
      ref.invalidate(checkoutQuoteProvider(widget.quote.deliveryAddress.id));
      unawaited(ref.read(cartProvider.notifier).load());
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) setState(() => _placing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final quote = widget.quote;
    return SafeArea(
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
                const Text('Payable', style: TextStyle(fontSize: 12, color: AppTheme.muted)),
                Text(
                  formatMoney(quote.cart.totals.total),
                  key: const Key('payable-total'),
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
                key: const Key('place-order'),
                onPressed: quote.canPlaceOrder && !_placing ? _placeOrder : null,
                child: _placing
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white),
                      )
                    : const Text('Place order'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
