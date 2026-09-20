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

// ---- Orders -----------------------------------------------------------------
export const ORDER_STATUSES = [
  'PLACED',
  'CONFIRMED',
  'PACKING',
  'OUT_FOR_DELIVERY',
  'DELIVERED',
  'CANCELLED',
] as const;

export type OrderStatus = (typeof ORDER_STATUSES)[number];

export interface OrderItem {
  id: number;
  product_id: number;
  product_name: string;
  product_sku: string;
  product_image_url: string | null;
  quantity: number;
  /** Decimal string. */
  unit_mrp: string;
  /** Decimal string. */
  unit_price: string;
  /** Decimal string. */
  line_total: string;
  /** Decimal string. */
  line_discount: string;
}

export interface OrderStatusEvent {
  id: number;
  from_status: OrderStatus | null;
  to_status: OrderStatus;
  changed_by_name: string | null;
  note: string | null;
  created_at: string;
}

export interface DeliveryAddressSnapshot {
  full_name: string;
  phone: string;
  house_number: string;
  street: string;
  area: string;
  city: string;
  state: string;
  pincode: string;
  instructions: string | null;
  single_line: string;
}

export interface OrderTotals {
  /** Decimal strings throughout. */
  subtotal: string;
  discount: string;
  items_total: string;
  delivery_charge: string;
  total: string;
  currency: string;
}

export interface TimelineStep {
  status: OrderStatus;
  label: string;
  reached: boolean;
  is_current: boolean;
  reached_at: string | null;
}

export interface OrderSummary {
  order_number: string;
  status: OrderStatus;
  status_label: string;
  /** Decimal string. */
  total: string;
  currency: string;
  item_count: number;
  placed_at: string;
}

export interface AdminOrderSummary extends OrderSummary {
  customer_name: string;
  customer_email: string;
  customer_phone: string | null;
}

export interface AdminOrderDetail extends AdminOrderSummary {
  items: OrderItem[];
  totals: OrderTotals;
  delivery_address: DeliveryAddressSnapshot;
  timeline: TimelineStep[];
  status_history: OrderStatusEvent[];
  is_cancellable_by_customer: boolean;
  delivered_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  /** The moves this order may still make. The server re-checks every one. */
  allowed_transitions: OrderStatus[];
}

// ---- Customers ---------------------------------------------------------------
export interface CustomerSummary {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at: string | null;
  order_count: number;
  /** Decimal string. */
  total_spent: string;
  last_order_at: string | null;
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

  sales: {
    orders_today: number;
    /** Decimal strings throughout. */
    revenue_today: string;
    orders_this_week: number;
    revenue_this_week: string;
    orders_this_month: number;
    revenue_this_month: string;
    total_orders: number;
    lifetime_revenue: string;
    average_order_value: string;
  };
  orders_by_status: { status: OrderStatus; label: string; count: number }[];
  best_sellers: { product_name: string; units_sold: number; revenue: string }[];
  recent_orders: OrderSummary[];
  /** Placed or confirmed: waiting on somebody. */
  pending_orders: number;
  /** False until the first order exists. No sales figures are invented. */
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
