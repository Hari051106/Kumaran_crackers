/// Product card used in the catalogue grid and the home carousels.
library;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/money.dart';
import '../core/theme.dart';
import '../models/product.dart';

class ProductImageBox extends StatelessWidget {
  const ProductImageBox({super.key, required this.url, this.size});

  final String? url;
  final double? size;

  @override
  Widget build(BuildContext context) {
    const placeholder = ColoredBox(
      color: Color(0xFFF1F3F7),
      child: Center(
        child: Icon(Icons.celebration_outlined, color: AppTheme.muted, size: 28),
      ),
    );

    if (url == null || url!.isEmpty) {
      return SizedBox(width: size, height: size, child: placeholder);
    }

    return CachedNetworkImage(
      imageUrl: url!,
      width: size,
      height: size,
      fit: BoxFit.cover,
      // A missing image must never break the card.
      placeholder: (_, __) => const ColoredBox(color: Color(0xFFF1F3F7)),
      errorWidget: (_, __, ___) => placeholder,
    );
  }
}

class StockChip extends StatelessWidget {
  const StockChip({super.key, required this.status, this.compact = false});

  final StockStatus status;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    // Colour is never the only signal: each state also carries its own words
    // and an icon, because red and green are hard to tell apart under
    // deuteranopia.
    final (color, icon) = switch (status) {
      StockStatus.inStock => (AppTheme.inStock, Icons.check_circle_outline),
      StockStatus.lowStock => (AppTheme.lowStock, Icons.warning_amber_rounded),
      StockStatus.outOfStock => (AppTheme.outOfStock, Icons.remove_circle_outline),
    };

    return Container(
      padding: EdgeInsets.symmetric(horizontal: compact ? 6 : 8, vertical: compact ? 2 : 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: compact ? 11 : 13, color: color),
          const SizedBox(width: 4),
          Text(
            status.label,
            style: TextStyle(
              fontSize: compact ? 10 : 11.5,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

class ProductCard extends StatelessWidget {
  const ProductCard({super.key, required this.product, required this.onTap});

  final Product product;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final discounted = hasDiscount(product.discountPercentage);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                AspectRatio(
                  aspectRatio: 1,
                  child: ProductImageBox(url: product.primaryImageUrl),
                ),
                if (discounted)
                  Positioned(
                    top: 8,
                    left: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                      decoration: BoxDecoration(
                        color: AppTheme.brand,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        formatDiscount(product.discountPercentage),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10.5,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                if (!product.inStock)
                  Positioned.fill(
                    child: ColoredBox(
                      color: Colors.white.withValues(alpha: 0.66),
                      child: const Center(
                        child: Text(
                          'Out of stock',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: AppTheme.outOfStock,
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 10, 10, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    product.name,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13.5,
                      height: 1.25,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.ink,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(
                        formatMoney(product.sellingPrice),
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.ink,
                        ),
                      ),
                      if (discounted) ...[
                        const SizedBox(width: 6),
                        Flexible(
                          child: Text(
                            formatMoney(product.mrp),
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppTheme.muted,
                              decoration: TextDecoration.lineThrough,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 8),
                  StockChip(status: product.stockStatus, compact: true),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
