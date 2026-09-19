/**
 * TypeScript mirrors of the backend Pydantic schemas.
 *
 * Money arrives as an exact decimal STRING (e.g. "1874.25"), never a number.
 * Keep it a string: converting to `number` reintroduces the floating-point
 * error the backend's Decimal columns exist to prevent. Format for display
 * with the helpers in `lib/money.ts`.
 */

export type RoleName = 'ADMIN' | 'STAFF' | 'CUSTOMER';
export type StockStatus = 'IN_STOCK' | 'LOW_STOCK' | 'OUT_OF_STOCK';

export type ProductSort =
  | 'newest'
  | 'price_asc'
  | 'price_desc'
  | 'name_asc'
  | 'discount'
  | 'popularity';

export interface Role {
  id: number;
  name: RoleName;
  description: string | null;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  is_active: boolean;
  is_verified: boolean;
  date_of_birth: string | null;
  last_login_at: string | null;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: TokenPair;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  image_url: string | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

export interface CategoryWithCount extends Category {
  product_count: number;
}

export interface CategorySummary {
  id: number;
  name: string;
  slug: string;
}

export interface ProductImage {
  id: number;
  image_url: string;
  alt_text: string | null;
  display_order: number;
  is_primary: boolean;
}

export interface ProductListItem {
  id: number;
  name: string;
  slug: string;
  sku: string;
  category: CategorySummary;
  /** Decimal string. */
  mrp: string;
  /** Decimal string. */
  selling_price: string;
  /** Decimal string. */
  discount_percentage: string;
  /** Decimal string. */
  discount_amount: string;
  stock_status: StockStatus;
  in_stock: boolean;
  primary_image_url: string | null;
  is_featured: boolean;
  is_active: boolean;
}

export interface ProductDetail extends ProductListItem {
  description: string | null;
  stock_quantity: number;
  images: ProductImage[];
  created_at: string;
  updated_at: string;
}

export interface ProductAdminDetail extends ProductDetail {
  low_stock_threshold: number;
  sold_quantity: number;
}

export interface PaginationMeta {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface Page<T> {
  items: T[];
  meta: PaginationMeta;
}

export interface DashboardStats {
  catalogue: {
    total_products: number;
    active_products: number;
    inactive_products: number;
    total_categories: number;
    active_categories: number;
  };
  inventory: {
    low_stock_count: number;
    out_of_stock_count: number;
    /** Decimal string. */
    inventory_retail_value: string;
  };
  customers: {
    total_customers: number;
    active_customers: number;
  };
  products_per_category: { category: string; product_count: number }[];
  recent_products: ProductListItem[];
  /** False until the order system exists. No sales figures are invented. */
  sales_metrics_available: boolean;
}

/** The single error envelope every failing endpoint returns. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, string>;
  };
}
