import type { HealthResponse } from '../types/health'
import type { ShoppingHistory, ShoppingHistoryCreate, HistoryAction } from '../types/history'
import type { Product, ProductFilters } from '../types/product'
import type { Profile, ProfileCreate, ProfileUpdate } from '../types/profile'
import type { ShopperDNA, ShopperDNAUpdate } from '../types/shopperDna'

/**
 * Base URL for API calls.
 * In Vite dev, `/api` is proxied to FastAPI (see vite.config.ts).
 * Override with VITE_API_BASE_URL when talking to a remote backend.
 */
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    throw new Error(`API ${path} failed with status ${response.status}`)
  }

  return response.json() as Promise<T>
}

function toQuery(params: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value))
    }
  }
  const text = query.toString()
  return text ? `?${text}` : ''
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

export function createProfile(payload: ProfileCreate): Promise<Profile> {
  return request<Profile>('/api/profiles', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getProfile(userId: number): Promise<Profile> {
  return request<Profile>(`/api/profiles/${userId}`)
}

export function updateProfile(userId: number, payload: ProfileUpdate): Promise<Profile> {
  return request<Profile>(`/api/profiles/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function getShopperDNA(userId: number): Promise<ShopperDNA> {
  return request<ShopperDNA>(`/api/profiles/${userId}/dna`)
}

export function updateShopperDNA(userId: number, payload: ShopperDNAUpdate): Promise<ShopperDNA> {
  return request<ShopperDNA>(`/api/profiles/${userId}/dna`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function listProducts(filters: ProductFilters = {}): Promise<Product[]> {
  return request<Product[]>(`/api/products${toQuery(filters)}`)
}

export function getProduct(productId: string): Promise<Product> {
  return request<Product>(`/api/products/${encodeURIComponent(productId)}`)
}

export function recordHistory(payload: ShoppingHistoryCreate): Promise<ShoppingHistory> {
  return request<ShoppingHistory>('/api/history', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getHistory(
  userId: number,
  action?: HistoryAction,
): Promise<ShoppingHistory[]> {
  return request<ShoppingHistory[]>(
    `/api/history/${userId}${toQuery({ action })}`,
  )
}
