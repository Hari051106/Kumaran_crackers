/// Customer home screen.
///
/// Every section is backed by a real query. There is deliberately no
/// "best sellers" row: nothing has been sold until the order system exists, so
/// such a row would be an arbitrary ordering presented as popularity.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/config.dart';
import '../../core/theme.dart';
import '../../models/category.dart';
import '../../models/product.dart';
import '../../providers/providers.dart';
import '../../widgets/product_card.dart';
import '../../widgets/state_views.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppTheme.brand,
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Center(
                child: Text(
                  'K',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 17,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 10),
            const Text(AppConfig.appName),
          ],
        ),
        actions: [
          if (auth.isSignedIn) const _BasketButton(),
          IconButton(
            onPressed: () => context.push('/profile'),
            tooltip: auth.isSignedIn ? 'Your account' : 'Sign in',
            icon: Icon(
              auth.isSignedIn ? Icons.account_circle_rounded : Icons.person_outline_rounded,
            ),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: RefreshIndicator(
        color: AppTheme.brand,
        onRefresh: () async {
          ref
            ..invalidate(categoriesProvider)
            ..invalidate(featuredProductsProvider)
            ..invalidate(offerProductsProvider)
            ..invalidate(newArrivalsProvider);
          await ref.read(categoriesProvider.future);
        },
        child: ListView(
          padding: const EdgeInsets.only(bottom: 32),
          children: [
            const _SearchBar(),
            const _CategoryStrip(),
            _ProductRow(
              title: 'Featured',
              subtitle: 'Hand-picked by our team',
              provider: featuredProductsProvider,
            ),
            _ProductRow(
              title: 'Special offers',
              subtitle: 'Biggest savings right now',
              provider: offerProductsProvider,
              onSeeAll: () => context.push('/products?discounted=true'),
            ),
            _ProductRow(
              title: 'New arrivals',
              subtitle: 'Just added to the shop',
              provider: newArrivalsProvider,
              onSeeAll: () => context.push('/products'),
            ),
            const _SafetyNote(),
          ],
        ),
      ),
    );
  }
}

class _SearchBar extends StatelessWidget {
  const _SearchBar();

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
        child: GestureDetector(
          key: const Key('home-search'),
          onTap: () => context.push('/products?focus=search'),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.hairline),
            ),
            child: const Row(
              children: [
                Icon(Icons.search_rounded, color: AppTheme.muted, size: 21),
                SizedBox(width: 10),
                Text(
                  'Search sparklers, rockets, gift packs…',
                  style: TextStyle(color: AppTheme.muted, fontSize: 14.5),
                ),
              ],
            ),
          ),
        ),
      );
}

class _CategoryStrip extends ConsumerWidget {
  const _CategoryStrip();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final categories = ref.watch(categoriesProvider);

    return categories.when(
      loading: () => const SizedBox(
        height: 116,
        child: Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2.4, color: AppTheme.brand),
          ),
        ),
      ),
      error: (error, _) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: ErrorView(
          error: error,
          onRetry: () => ref.invalidate(categoriesProvider),
        ),
      ),
      data: (items) {
        if (items.isEmpty) return const SizedBox.shrink();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _SectionHeader(title: 'Shop by category'),
            SizedBox(
              height: 104,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(width: 12),
                itemBuilder: (context, index) => _CategoryTile(category: items[index]),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _CategoryTile extends StatelessWidget {
  const _CategoryTile({required this.category});

  final Category category;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 84,
        child: InkWell(
          key: Key('category-${category.slug}'),
          borderRadius: BorderRadius.circular(12),
          onTap: () => context.push('/products?category=${category.id}'),
          child: Column(
            children: [
              Container(
                width: 60,
                height: 60,
                decoration: BoxDecoration(
                  color: AppTheme.brand.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(16),
                ),
                clipBehavior: Clip.antiAlias,
                child: category.imageUrl == null
                    ? const Icon(Icons.celebration_rounded, color: AppTheme.brand, size: 26)
                    : ProductImageBox(url: category.imageUrl, size: 60),
              ),
              const SizedBox(height: 7),
              Text(
                category.name,
                maxLines: 2,
                textAlign: TextAlign.center,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 11.5,
                  height: 1.2,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.ink,
                ),
              ),
            ],
          ),
        ),
      );
}

class _ProductRow extends ConsumerWidget {
  const _ProductRow({
    required this.title,
    required this.subtitle,
    required this.provider,
    this.onSeeAll,
  });

  final String title;
  final String subtitle;
  final ProviderListenable<AsyncValue<List<Product>>> provider;
  final VoidCallback? onSeeAll;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final products = ref.watch(provider);

    return products.when(
      loading: () => const SizedBox(
        height: 150,
        child: Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2.4, color: AppTheme.brand),
          ),
        ),
      ),
      // A single row failing must not take down the whole home screen.
      error: (_, __) => const SizedBox.shrink(),
      data: (items) {
        if (items.isEmpty) return const SizedBox.shrink();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SectionHeader(title: title, subtitle: subtitle, onSeeAll: onSeeAll),
            SizedBox(
              height: 262,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(width: 12),
                itemBuilder: (context, index) {
                  final product = items[index];
                  return SizedBox(
                    width: 158,
                    child: ProductCard(
                      product: product,
                      onTap: () => context.push('/product/${product.slug}'),
                    ),
                  );
                },
              ),
            ),
          ],
        );
      },
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.subtitle, this.onSeeAll});

  final String title;
  final String? subtitle;
  final VoidCallback? onSeeAll;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 22, 8, 12),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.ink,
                      letterSpacing: -0.2,
                    ),
                  ),
                  if (subtitle != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        subtitle!,
                        style: const TextStyle(fontSize: 12.5, color: AppTheme.muted),
                      ),
                    ),
                ],
              ),
            ),
            if (onSeeAll != null)
              TextButton(onPressed: onSeeAll, child: const Text('See all')),
          ],
        ),
      );
}

/// Fireworks are age-restricted goods; the shop says so rather than burying it.
class _SafetyNote extends StatelessWidget {
  const _SafetyNote();

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 28, 16, 0),
        child: Container(
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
                  'Fireworks are sold to adults aged 18 and over. Please follow local '
                  'rules on storage, use and delivery, and celebrate safely.',
                  style: TextStyle(fontSize: 12.5, color: AppTheme.muted, height: 1.4),
                ),
              ),
            ],
          ),
        ),
      );
}


/// Basket icon with a live count, shown only to signed-in shoppers.
class _BasketButton extends ConsumerStatefulWidget {
  const _BasketButton();

  @override
  ConsumerState<_BasketButton> createState() => _BasketButtonState();
}

class _BasketButtonState extends ConsumerState<_BasketButton> {
  @override
  void initState() {
    super.initState();
    // Load once so the badge is accurate as soon as the home screen appears.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(cartProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final count = ref.watch(cartCountProvider);

    return IconButton(
      key: const Key('open-basket'),
      tooltip: 'Your basket',
      onPressed: () => context.push('/cart'),
      icon: Badge(
        isLabelVisible: count > 0,
        backgroundColor: AppTheme.brand,
        label: Text('$count'),
        child: const Icon(Icons.shopping_bag_outlined),
      ),
    );
  }
}
