/// Mirrors the backend `Page[T]` envelope.
library;

class PageMeta {
  const PageMeta({
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
    required this.hasNext,
    required this.hasPrevious,
  });

  factory PageMeta.fromJson(Map<String, dynamic> json) => PageMeta(
        total: json['total'] as int,
        page: json['page'] as int,
        pageSize: json['page_size'] as int,
        totalPages: json['total_pages'] as int,
        hasNext: json['has_next'] as bool,
        hasPrevious: json['has_previous'] as bool,
      );

  final int total;
  final int page;
  final int pageSize;
  final int totalPages;
  final bool hasNext;
  final bool hasPrevious;
}

class Paged<T> {
  const Paged({required this.items, required this.meta});

  factory Paged.fromJson(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) itemFromJson,
  ) =>
      Paged(
        items: (json['items'] as List<dynamic>)
            .map((item) => itemFromJson(item as Map<String, dynamic>))
            .toList(),
        meta: PageMeta.fromJson(json['meta'] as Map<String, dynamic>),
      );

  final List<T> items;
  final PageMeta meta;
}
