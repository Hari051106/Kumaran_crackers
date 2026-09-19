/// Product catalogue: search, category and price filters, sorting, paging.
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
import '../../repositories/catalog_repository.dart';
import '../../widgets/product_card.dart';
import '../../widgets/state_views.dart';

class ProductsScreen extends ConsumerStatefulWidget {
  const ProductsScreen({
    super.key,
    this.initialCategoryId,
    this.discountedOnly = false,
    this.focusSearch = false,
  });

  final int? initialCategoryId;
  final bool discountedOnly;
  final bool focusSearch;

  @override
  ConsumerState<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends ConsumerState<ProductsScreen> {
  final _searchController = TextEditingController();
  final _searchFocus = FocusNode();
  final _scrollController = ScrollController();

  Timer? _debounce;
  late ProductQuery _query;

  /// Accumulated across pages, so scrolling appends rather than replaces.
  final List<Product> _loaded = [];
  bool _loadingMore = false;
  bool _hasMore = true;

  @override
  void initState() {
    super.initState();
    _query = ProductQuery(
      categoryId: widget.initialCategoryId,
      discountedOnly: widget.discountedOnly,
      sort: widget.discountedOnly ? ProductSort.biggestDiscount : ProductSort.newest,
    );
    _scrollController.addListener(_onScroll);
    if (widget.focusSearch) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _searchFocus.requestFocus());
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _searchFocus.dispose();
    _scrollController
      ..removeListener(_onScroll)
      ..dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients || _loadingMore || !_hasMore) return;
    final position = _scrollController.position;
    // Fetch the next page slightly before the list actually runs out.
    if (position.pixels >= position.maxScrollExtent - 400) {
      unawaited(_loadMore());
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || !_hasMore) return;
    setState(() => _loadingMore = true);
    try {
      final next = _query.copyWith(page: _query.page + 1);
      final page = await ref.read(catalogRepositoryProvider).products(next);
      if (!mounted) return;
      setState(() {
        _query = next;
        _loaded.addAll(page.items);
        _hasMore = page.meta.hasNext;
      });
    } on ApiException {
      // Keep what is already on screen; the next scroll can retry.
      if (mounted) setState(() => _hasMore = false);
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  /// Any filter change resets to page one and clears the accumulated list.
  void _applyQuery(ProductQuery next) {
    setState(() {
      _query = next.copyWith(page: 1);
      _loaded.clear();
      _hasMore = true;
    });
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      _applyQuery(_query.copyWith(search: value));
    });
  }

  @override
  Widget build(BuildContext context) {
    // The first page comes from the provider (so it is cached and refreshable);
    // subsequent pages are appended by _loadMore.
    final firstPage = ref.watch(productsProvider(_query.copyWith(page: 1)));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Products'),
        actions: [
          IconButton(
            key: const Key('open-filters'),
            tooltip: 'Filter and sort',
            onPressed: _openFilters,
            icon: Badge(
              isLabelVisible: _hasActiveFilters,
              backgroundColor: AppTheme.brand,
              child: const Icon(Icons.tune_rounded),
            ),
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
            child: TextField(
              key: const Key('product-search-field'),
              controller: _searchController,
              focusNode: _searchFocus,
              textInputAction: TextInputAction.search,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: 'Search by name or SKU…',
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: _searchController.text.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Clear search',
                        icon: const Icon(Icons.close_rounded),
                        onPressed: () {
                          _searchController.clear();
                          _applyQuery(_query.copyWith(search: ''));
                        },
                      ),
              ),
            ),
          ),
          Expanded(
            child: firstPage.when(
              loading: () => _loaded.isEmpty
                  ? const LoadingView(label: 'Loading products…')
                  : _grid(_loaded),
              error: (error, _) => ErrorView(
                error: error,
                onRetry: () => ref.invalidate(productsProvider(_query.copyWith(page: 1))),
              ),
              data: (page) {
                // Page one lives in the provider; later pages are appended.
                final items = _loaded.isEmpty ? page.items : [...page.items, ..._loaded];
                if (items.isEmpty) {
                  return EmptyView(
                    title: (_query.search ?? '').isEmpty
                        ? 'Nothing here yet'
                        : 'No products match your search',
                    message: (_query.search ?? '').isEmpty
                        ? 'New stock arrives regularly. Please check back soon.'
                        : 'Try a different word, or clear your filters.',
                    icon: Icons.search_off_rounded,
                    action: _hasActiveFilters
                        ? OutlinedButton(
                            onPressed: () {
                              _searchController.clear();
                              _applyQuery(const ProductQuery());
                            },
                            child: const Text('Clear filters'),
                          )
                        : null,
                  );
                }
                return RefreshIndicator(
                  color: AppTheme.brand,
                  onRefresh: () async {
                    setState(() {
                      _loaded.clear();
                      _hasMore = true;
                    });
                    ref.invalidate(productsProvider(_query.copyWith(page: 1)));
                    await ref.read(productsProvider(_query.copyWith(page: 1)).future);
                  },
                  child: _grid(items, total: page.meta.total),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  bool get _hasActiveFilters =>
      (_query.search ?? '').isNotEmpty ||
      _query.categoryId != null ||
      _query.minPrice != null ||
      _query.maxPrice != null ||
      _query.inStockOnly ||
      _query.sort != ProductSort.newest;

  Widget _grid(List<Product> items, {int? total}) => GridView.builder(
        controller: _scrollController,
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
        physics: const AlwaysScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisExtent(
          maxCrossAxisExtent: 220,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 0.62,
        ),
        itemCount: items.length + (_loadingMore ? 2 : 0),
        itemBuilder: (context, index) {
          if (index >= items.length) {
            return const Center(
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2.2, color: AppTheme.brand),
              ),
            );
          }
          final product = items[index];
          return ProductCard(
            key: Key('product-${product.slug}'),
            product: product,
            onTap: () => context.push('/product/${product.slug}'),
          );
        },
      );

  Future<void> _openFilters() async {
    final categories = await ref.read(categoriesProvider.future);
    if (!mounted) return;

    final result = await showModalBottomSheet<ProductQuery>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => _FilterSheet(
        query: _query,
        categories: categories.map((c) => (c.id, c.name)).toList(),
      ),
    );
    if (result != null) _applyQuery(result);
  }
}

/// Grid delegate that keeps tiles a sensible width on both phones and tablets.
class SliverGridDelegateWithFixedCrossAxisExtent extends SliverGridDelegateWithMaxCrossAxisExtent {
  const SliverGridDelegateWithFixedCrossAxisExtent({
    required super.maxCrossAxisExtent,
    super.mainAxisSpacing,
    super.crossAxisSpacing,
    super.childAspectRatio,
  });
}

class _FilterSheet extends StatefulWidget {
  const _FilterSheet({required this.query, required this.categories});

  final ProductQuery query;
  final List<(int, String)> categories;

  @override
  State<_FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends State<_FilterSheet> {
  late int? _categoryId = widget.query.categoryId;
  late ProductSort _sort = widget.query.sort;
  late bool _inStockOnly = widget.query.inStockOnly;
  late final _minPrice = TextEditingController(text: widget.query.minPrice ?? '');
  late final _maxPrice = TextEditingController(text: widget.query.maxPrice ?? '');

  String? _priceError;

  @override
  void dispose() {
    _minPrice.dispose();
    _maxPrice.dispose();
    super.dispose();
  }

  void _apply() {
    final min = _minPrice.text.trim();
    final max = _maxPrice.text.trim();

    // Compared as decimal strings, never as doubles.
    if (min.isNotEmpty && max.isNotEmpty && compareMoney(min, max) > 0) {
      setState(() => _priceError = 'The lowest price cannot be above the highest.');
      return;
    }

    Navigator.of(context).pop(
      ProductQuery(
        search: widget.query.search,
        categoryId: _categoryId,
        minPrice: min.isEmpty ? null : min,
        maxPrice: max.isEmpty ? null : max,
        inStockOnly: _inStockOnly,
        discountedOnly: widget.query.discountedOnly,
        sort: _sort,
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          bottom: MediaQuery.of(context).viewInsets.bottom + 24,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Filter & sort',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.ink,
                ),
              ),
              const SizedBox(height: 20),

              const _FilterLabel('Category'),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  ChoiceChip(
                    label: const Text('All'),
                    selected: _categoryId == null,
                    onSelected: (_) => setState(() => _categoryId = null),
                  ),
                  for (final (id, name) in widget.categories)
                    ChoiceChip(
                      label: Text(name),
                      selected: _categoryId == id,
                      onSelected: (_) => setState(() => _categoryId = id),
                    ),
                ],
              ),
              const SizedBox(height: 22),

              const _FilterLabel('Price range'),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      key: const Key('filter-min-price'),
                      controller: _minPrice,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'From', prefixText: '$rupee '),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      key: const Key('filter-max-price'),
                      controller: _maxPrice,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: 'To', prefixText: '$rupee '),
                    ),
                  ),
                ],
              ),
              if (_priceError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    _priceError!,
                    style: const TextStyle(color: AppTheme.outOfStock, fontSize: 12.5),
                  ),
                ),
              const SizedBox(height: 22),

              const _FilterLabel('Sort by'),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final option in ProductSort.values)
                    ChoiceChip(
                      label: Text(option.label),
                      selected: _sort == option,
                      onSelected: (_) => setState(() => _sort = option),
                    ),
                ],
              ),
              const SizedBox(height: 12),

              SwitchListTile.adaptive(
                contentPadding: EdgeInsets.zero,
                value: _inStockOnly,
                activeThumbColor: AppTheme.brand,
                title: const Text('In stock only'),
                onChanged: (value) => setState(() => _inStockOnly = value),
              ),
              const SizedBox(height: 12),

              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.of(context).pop(const ProductQuery()),
                      child: const Text('Reset'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      key: const Key('apply-filters'),
                      onPressed: _apply,
                      child: const Text('Show results'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      );
}

class _FilterLabel extends StatelessWidget {
  const _FilterLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text(
          text,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppTheme.ink,
          ),
        ),
      );
}
