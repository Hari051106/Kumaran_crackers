/// Product detail: gallery, pricing, stock and a quantity selector.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api_exception.dart';
import '../../core/money.dart';
import '../../core/theme.dart';
import '../../models/product.dart';
import '../../providers/providers.dart';
import '../../widgets/product_card.dart';
import '../../widgets/state_views.dart';

class ProductDetailScreen extends ConsumerStatefulWidget {
  const ProductDetailScreen({super.key, required this.slug});

  final String slug;

  @override
  ConsumerState<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends ConsumerState<ProductDetailScreen> {
  int _quantity = 1;
  int _imageIndex = 0;

  @override
  Widget build(BuildContext context) {
    final product = ref.watch(productDetailProvider(widget.slug));

    return Scaffold(
      appBar: AppBar(title: const Text('Product')),
      body: product.when(
        loading: () => const LoadingView(),
        error: (error, _) => ErrorView(
          error: error,
          onRetry: () => ref.invalidate(productDetailProvider(widget.slug)),
        ),
        data: _buildDetail,
      ),
      bottomNavigationBar: product.maybeWhen(
        data: (item) => _BuyBar(
          product: item,
          quantity: _quantity,
          onQuantityChanged: (value) => setState(() => _quantity = value),
        ),
        orElse: () => null,
      ),
    );
  }

  Widget _buildDetail(Product product) {
    final gallery = product.galleryUrls;
    final discounted = hasDiscount(product.discountPercentage);

    return ListView(
      padding: EdgeInsets.zero,
      children: [
        // ---- Gallery ----
        ColoredBox(
          color: Colors.white,
          child: Column(
            children: [
              AspectRatio(
                aspectRatio: 1,
                child: gallery.isEmpty
                    ? const ProductImageBox(url: null)
                    : PageView.builder(
                        onPageChanged: (index) => setState(() => _imageIndex = index),
                        itemCount: gallery.length,
                        itemBuilder: (context, index) =>
                            ProductImageBox(url: gallery[index]),
                      ),
              ),
              if (gallery.length > 1)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(
                      gallery.length,
                      (index) => AnimatedContainer(
                        duration: const Duration(milliseconds: 180),
                        margin: const EdgeInsets.symmetric(horizontal: 3),
                        width: index == _imageIndex ? 18 : 6,
                        height: 6,
                        decoration: BoxDecoration(
                          color: index == _imageIndex ? AppTheme.brand : AppTheme.hairline,
                          borderRadius: BorderRadius.circular(999),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),

        // ---- Headline ----
        Container(
          width: double.infinity,
          color: Colors.white,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                product.category.name.toUpperCase(),
                style: const TextStyle(
                  fontSize: 11,
                  letterSpacing: 0.8,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.brand,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                product.name,
                style: const TextStyle(
                  fontSize: 21,
                  height: 1.28,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.ink,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'SKU ${product.sku}',
                style: const TextStyle(fontSize: 12, color: AppTheme.muted),
              ),
              const SizedBox(height: 16),

              // ---- Pricing ----
              Row(
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                children: [
                  Text(
                    formatMoney(product.sellingPrice),
                    style: const TextStyle(
                      fontSize: 27,
                      fontWeight: FontWeight.w800,
                      color: AppTheme.ink,
                      letterSpacing: -0.5,
                    ),
                  ),
                  if (discounted) ...[
                    const SizedBox(width: 10),
                    Text(
                      formatMoney(product.mrp),
                      style: const TextStyle(
                        fontSize: 15,
                        color: AppTheme.muted,
                        decoration: TextDecoration.lineThrough,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppTheme.brand,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        formatDiscount(product.discountPercentage),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 11.5,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
              if (discounted)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    'You save ${formatMoney(product.discountAmount)}',
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppTheme.inStock,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              const SizedBox(height: 14),
              Row(
                children: [
                  StockChip(status: product.stockStatus),
                  if (product.stockQuantity != null && product.inStock) ...[
                    const SizedBox(width: 10),
                    Text(
                      '${product.stockQuantity} available',
                      style: const TextStyle(fontSize: 12.5, color: AppTheme.muted),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),

        // ---- Description ----
        if ((product.description ?? '').trim().isNotEmpty)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.only(top: 10),
            color: Colors.white,
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'About this product',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.ink,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  product.description!,
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.55,
                    color: Color(0xFF424A61),
                  ),
                ),
              ],
            ),
          ),

        // ---- Safety ----
        Container(
          width: double.infinity,
          margin: const EdgeInsets.only(top: 10),
          color: Colors.white,
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 22),
          child: const Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.shield_outlined, size: 18, color: AppTheme.muted),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Sold to adults aged 18 and over. Store away from heat, light outdoors '
                  'and keep a safe distance. Local rules on sale and delivery apply.',
                  style: TextStyle(fontSize: 12.5, color: AppTheme.muted, height: 1.45),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }
}

/// The sticky bar carrying the quantity selector and the basket action.
class _BuyBar extends ConsumerStatefulWidget {
  const _BuyBar({
    required this.product,
    required this.quantity,
    required this.onQuantityChanged,
  });

  final Product product;
  final int quantity;
  final ValueChanged<int> onQuantityChanged;

  @override
  ConsumerState<_BuyBar> createState() => _BuyBarState();
}

class _BuyBarState extends ConsumerState<_BuyBar> {
  bool _adding = false;

  Future<void> _addToBasket() async {
    // Signed-out shoppers browse freely; a basket needs an account.
    if (!ref.read(authProvider).isSignedIn) {
      final signIn = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Sign in to add to your basket'),
          content: const Text('You can keep browsing without an account.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Not now'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Sign in'),
            ),
          ],
        ),
      );
      // Navigation completes when the login route pops; nothing here waits
      // on it, so the future is explicitly discarded.
      if ((signIn ?? false) && mounted) unawaited(context.push('/login'));
      return;
    }

    setState(() => _adding = true);
    try {
      await ref.read(cartProvider.notifier).add(
            productId: widget.product.id,
            quantity: widget.quantity,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text('${widget.product.name} added to your basket'),
            action: SnackBarAction(
              label: 'View basket',
              onPressed: () => context.push('/cart'),
            ),
          ),
        );
    } on ApiException catch (error) {
      // The server is the authority on stock, so its reason is shown as-is.
      if (mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _adding = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final product = widget.product;
    final quantity = widget.quantity;
    final onQuantityChanged = widget.onQuantityChanged;
    final maximum = product.maxSelectableQuantity;
    final available = product.inStock && maximum > 0;

    return SafeArea(
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: AppTheme.hairline)),
        ),
        child: Row(
          children: [
            if (available)
              Container(
                decoration: BoxDecoration(
                  border: Border.all(color: AppTheme.hairline),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      key: const Key('quantity-decrease'),
                      tooltip: 'Reduce quantity',
                      onPressed:
                          quantity > 1 ? () => onQuantityChanged(quantity - 1) : null,
                      icon: const Icon(Icons.remove_rounded, size: 20),
                    ),
                    SizedBox(
                      width: 28,
                      child: Text(
                        '$quantity',
                        key: const Key('quantity-value'),
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontSize: 15.5,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.ink,
                        ),
                      ),
                    ),
                    IconButton(
                      key: const Key('quantity-increase'),
                      tooltip: 'Increase quantity',
                      // Capped at what is actually in stock.
                      onPressed: quantity < maximum
                          ? () => onQuantityChanged(quantity + 1)
                          : null,
                      icon: const Icon(Icons.add_rounded, size: 20),
                    ),
                  ],
                ),
              ),
            if (available) const SizedBox(width: 12),
            Expanded(
              child: FilledButton.icon(
                key: const Key('add-to-cart'),
                onPressed: available && !_adding ? _addToBasket : null,
                icon: _adding
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.shopping_bag_outlined, size: 20),
                label: Text(available ? 'Add to basket' : 'Out of stock'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
