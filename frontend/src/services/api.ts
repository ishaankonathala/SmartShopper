import type { HealthResponse } from '../types/health'
import type {
  AmazonCatalogueFilters,
  AmazonCataloguePage,
  AmazonCatalogueProduct,
} from '../types/amazonCatalogue'
import type {
  AssistantCategory,
  AssistantChatRequest,
  AgentActivityEvent,
  AgentExecutionMetadata,
  AssistantChatResponse,
  AssistantIntent,
  AssistantRecommendation,
} from '../types/assistant'
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

export class ApiRequestError extends Error {
  readonly path: string
  readonly status: number

  constructor(path: string, status: number) {
    super(`API ${path} failed with status ${status}`)
    this.name = 'ApiRequestError'
    this.path = path
    this.status = status
  }
}

export class InvalidAssistantResponseError extends Error {
  constructor() {
    super('The shopping service returned an unexpected response.')
    this.name = 'InvalidAssistantResponseError'
  }
}

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
    throw new ApiRequestError(path, response.status)
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isNullablePriority(value: unknown): value is number | null {
  return (
    value === null ||
    (typeof value === 'number' &&
      Number.isInteger(value) &&
      value >= 0 &&
      value <= 100)
  )
}

function isAssistantCategory(value: unknown): value is AssistantCategory {
  return (
    value === 'Headphones' ||
    value === 'Laptops' ||
    value === 'Smartwatches' ||
    value === 'Home Appliances' ||
    value === 'Computers & Accessories' ||
    value === 'Camera & Photo' ||
    value === 'Headphones & Earbuds' ||
    value === 'Television & Video' ||
    value === 'Home Audio' ||
    value === 'Car Electronics' ||
    value === 'Portable Audio & Video' ||
    value === 'Wearable Technology' ||
    value === 'Other Electronics'
  )
}

function isNumberRecord(value: unknown): value is Record<string, number> {
  return (
    isRecord(value) &&
    Object.values(value).every((item) => isFiniteNumber(item))
  )
}

function isAssistantIntent(value: unknown): value is AssistantIntent {
  if (!isRecord(value)) return false

  const category = value.category

  return (
    (category === null || isAssistantCategory(category)) &&
    (value.max_budget_override === null ||
      (isFiniteNumber(value.max_budget_override) && value.max_budget_override >= 0)) &&
    (value.min_budget_override === undefined ||
      value.min_budget_override === null ||
      (isFiniteNumber(value.min_budget_override) && value.min_budget_override >= 0)) &&
    (value.brand === undefined ||
      value.brand === null ||
      (typeof value.brand === 'string' && value.brand.trim().length > 0)) &&
    (value.min_rating === undefined ||
      value.min_rating === null ||
      (isFiniteNumber(value.min_rating) &&
        value.min_rating >= 1 &&
        value.min_rating <= 5)) &&
    (value.min_battery_life_hours === undefined ||
      value.min_battery_life_hours === null ||
      (isFiniteNumber(value.min_battery_life_hours) &&
        value.min_battery_life_hours > 0)) &&
    (value.require_battery_life_data === undefined ||
      value.require_battery_life_data === null ||
      typeof value.require_battery_life_data === 'boolean') &&
    (value.availability_requirement === undefined ||
      value.availability_requirement === null ||
      value.availability_requirement === 'available') &&
    isNullablePriority(value.comfort_priority) &&
    isNullablePriority(value.brand_loyalty) &&
    isNullablePriority(value.battery_life_priority) &&
    isNullablePriority(value.portability_priority) &&
    (value.connectivity_requirement === null ||
      value.connectivity_requirement === 'wireless' ||
      value.connectivity_requirement === 'wired') &&
    (value.product_type_requirement === undefined ||
    value.product_type_requirement === null ||
    value.product_type_requirement === 'headphones' ||
    value.product_type_requirement === 'earbuds' ||
    value.product_type_requirement === 'sleep_headphones') &&
    Array.isArray(value.unsupported_requirements) &&
    value.unsupported_requirements.every((item) => typeof item === 'string')
  )
}

function isAssistantRecommendation(
  value: unknown,
): value is AssistantRecommendation {
  return (
    isRecord(value) &&
    typeof value.product_id === 'string' &&
    (value.catalogue_source === undefined ||
      value.catalogue_source === 'curated' ||
      value.catalogue_source === 'amazon') &&
    (value.availability_status === undefined ||
      value.availability_status === 'available' ||
      value.availability_status === 'unavailable' ||
      value.availability_status === 'unverified') &&
    (value.price_is_historical === undefined ||
      typeof value.price_is_historical === 'boolean') &&
    (value.rating_count === undefined ||
      value.rating_count === null ||
      (isFiniteNumber(value.rating_count) && value.rating_count >= 0)) &&
    typeof value.name === 'string' &&
    typeof value.brand === 'string' &&
    typeof value.category === 'string' &&
    isFiniteNumber(value.price) &&
    isFiniteNumber(value.rating) &&
    (value.image_url === null || typeof value.image_url === 'string') &&
    isFiniteNumber(value.score) &&
    value.score >= 0 &&
    value.score <= 100 &&
    isFiniteNumber(value.confidence) &&
    value.confidence >= 0 &&
    value.confidence <= 100 &&
    Array.isArray(value.reasons) &&
    value.reasons.every((reason) => typeof reason === 'string') &&
    isNumberRecord(value.attribute_breakdown) &&
    isNumberRecord(value.score_breakdown)
  )
}

function isAssistantChatResponse(
  value: unknown,
): value is AssistantChatResponse {
  return (
    isRecord(value) &&
    Number.isInteger(value.user_id) &&
    typeof value.answer === 'string' &&
    isAssistantIntent(value.intent) &&
    Array.isArray(value.recommendations) &&
    value.recommendations.every(isAssistantRecommendation) &&
    typeof value.fallback_used === 'boolean' &&
    typeof value.has_more === 'boolean' &&
    (value.kind === 'shopping' ||
      value.kind === 'acknowledgement' ||
      value.kind === 'clarification' ||
      value.kind === 'answer') &&
    Array.isArray(value.notes) &&
    value.notes.every((note) => typeof note === 'string') &&
    (value.agent_metadata === undefined ||
      value.agent_metadata === null ||
      isAgentExecutionMetadata(value.agent_metadata))
  )
}

function isAgentExecutionMetadata(
  value: unknown,
): value is AgentExecutionMetadata {
  return (
    isRecord(value) &&
    typeof value.execution_id === 'string' &&
    (value.status === 'completed' ||
      value.status === 'partial' ||
      value.status === 'fallback' ||
      value.status === 'unavailable') &&
    typeof value.plan_summary === 'string' &&
    Array.isArray(value.tools_executed) &&
    value.tools_executed.every(
      (tool) =>
        tool === 'product_search' ||
        tool === 'product_comparison' ||
        tool === 'get_shopper_profile' ||
        tool === 'simulate_preferences' ||
        tool === 'evaluate_results',
    ) &&
    Number.isInteger(value.tool_execution_count) &&
    typeof value.evaluation_outcome === 'string' &&
    Array.isArray(value.activity) &&
    value.activity.every((activity) => typeof activity === 'string') &&
    (value.events === undefined ||
      (Array.isArray(value.events) && value.events.every(isAgentActivityEvent)))
  )
}

function isAgentActivityEvent(value: unknown): value is AgentActivityEvent {
  return (
    isRecord(value) &&
    Number.isInteger(value.sequence) &&
    (value.kind === 'understanding' ||
      value.kind === 'planning' ||
      value.kind === 'selection' ||
      value.kind === 'tool_execution' ||
      value.kind === 'evaluation' ||
      value.kind === 'completion') &&
    typeof value.title === 'string' &&
    (value.status === 'completed' ||
      value.status === 'failed' ||
      value.status === 'partial') &&
    typeof value.summary === 'string' &&
    (value.tool_name === undefined ||
      value.tool_name === null ||
      value.tool_name === 'product_search' ||
      value.tool_name === 'product_comparison' ||
      value.tool_name === 'get_shopper_profile' ||
      value.tool_name === 'simulate_preferences' ||
      value.tool_name === 'evaluate_results') &&
    (value.succeeded === undefined ||
      value.succeeded === null ||
      typeof value.succeeded === 'boolean')
  )
}

export async function chatWithAssistant(
  payload: AssistantChatRequest,
): Promise<AssistantChatResponse> {
  const response = await request<unknown>('/api/assistant/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

  if (!isAssistantChatResponse(response)) {
    throw new InvalidAssistantResponseError()
  }

  return response
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

export function listAmazonCatalogueProducts(
  filters: AmazonCatalogueFilters = {},
): Promise<AmazonCataloguePage> {
  return request<AmazonCataloguePage>(
    `/api/discover/products${toQuery(filters)}`,
  )
}

export function getAmazonCatalogueProduct(
  asin: string,
): Promise<AmazonCatalogueProduct> {
  return request<AmazonCatalogueProduct>(
    `/api/discover/products/${encodeURIComponent(asin)}`,
  )
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
