/**
 * Typed wrappers over the Kumaran Crackers REST API.
 *
 * Every call the desktop app makes goes through here, so the API contract is
 * defined in one place rather than scattered across components.
 */
import { api } from './client';
import type {
  AuthResponse,
  Category,
  CategoryWithCount,
  DashboardStats,
  Page,
  ProductAdminDetail,
  ProductListItem,
  ProductSort,
  User,
} from '../types/api';

// ---- Auth -------------------------------------------------------------------
export const authApi = {
  async adminLogin(email: string, password: string): Promise<AuthResponse> {
    const { data } = await api.post<AuthResponse>('/auth/admin/login', { email, password });
    return data;
  },
  async me(): Promise<User> {
    const { data } = await api.get<User>('/auth/me');
    return data;
  },
  async logout(): Promise<void> {
    await api.post('/auth/logout');
  },
};

// ---- Dashboard --------------------------------------------------------------
export const dashboardApi = {
  async stats(): Promise<DashboardStats> {
    const { data } = await api.get<DashboardStats>('/admin/dashboard');
    return data;
  },
};

// ---- Categories -------------------------------------------------------------
export interface CategoryInput {
  name: string;
  description?: string | null;
  image_url?: string | null;
  display_order?: number;
  is_active?: boolean;
}

export const categoriesApi = {
  async list(includeInactive = false): Promise<CategoryWithCount[]> {
    const { data } = await api.get<CategoryWithCount[]>('/categories', {
      params: { include_inactive: includeInactive },
    });
    return data;
  },
  async create(payload: CategoryInput): Promise<Category> {
    const { data } = await api.post<Category>('/categories', payload);
    return data;
  },
  async update(id: number, payload: Partial<CategoryInput>): Promise<Category> {
    const { data } = await api.patch<Category>(`/categories/${id}`, payload);
    return data;
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/categories/${id}`);
  },
};

// ---- Products ---------------------------------------------------------------
export interface ProductQuery {
  query?: string;
  category_id?: number;
  min_price?: string;
  max_price?: string;
  in_stock?: boolean;
  featured?: boolean;
  discounted?: boolean;
  include_inactive?: boolean;
  sort?: ProductSort;
  page?: number;
  page_size?: number;
}

export interface ProductInput {
  name: string;
  description?: string | null;
  category_id: number;
  /** Decimal strings - never numbers. */
  mrp: string;
  selling_price: string;
  stock_quantity?: number;
  low_stock_threshold?: number;
  is_active?: boolean;
  is_featured?: boolean;
  sku?: string | null;
  images?: { image_url: string; alt_text?: string | null; is_primary?: boolean }[];
}

export const productsApi = {
  async search(params: ProductQuery = {}): Promise<Page<ProductListItem>> {
    // Strip empty values so the backend sees a clean query string.
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== ''),
    );
    const { data } = await api.get<Page<ProductListItem>>('/products', { params: cleaned });
    return data;
  },
  async getById(id: number): Promise<ProductAdminDetail> {
    const { data } = await api.get<ProductAdminDetail>(`/products/id/${id}`);
    return data;
  },
  async create(payload: ProductInput): Promise<ProductAdminDetail> {
    const { data } = await api.post<ProductAdminDetail>('/products', payload);
    return data;
  },
  async update(id: number, payload: Partial<ProductInput>): Promise<ProductAdminDetail> {
    const { data } = await api.patch<ProductAdminDetail>(`/products/id/${id}`, payload);
    return data;
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/products/id/${id}`);
  },
  async setActive(id: number, active: boolean): Promise<ProductAdminDetail> {
    const action = active ? 'activate' : 'deactivate';
    const { data } = await api.post<ProductAdminDetail>(`/products/id/${id}/${action}`);
    return data;
  },
  async adjustStock(
    id: number,
    adjustment: { set_to?: number; delta?: number; reason?: string },
  ): Promise<ProductAdminDetail> {
    const { data } = await api.post<ProductAdminDetail>(`/products/id/${id}/stock`, adjustment);
    return data;
  },
  async lowStock(limit = 50): Promise<ProductAdminDetail[]> {
    const { data } = await api.get<ProductAdminDetail[]>('/products/low-stock', {
      params: { limit },
    });
    return data;
  },
  async outOfStock(limit = 50): Promise<ProductAdminDetail[]> {
    const { data } = await api.get<ProductAdminDetail[]>('/products/out-of-stock', {
      params: { limit },
    });
    return data;
  },
};
