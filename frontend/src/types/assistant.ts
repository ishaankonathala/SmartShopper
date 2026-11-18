export type AssistantCategory =
  | 'Headphones'
  | 'Laptops'
  | 'Smartwatches'
  | 'Home Appliances'
  | 'Computers & Accessories'
  | 'Camera & Photo'
  | 'Headphones & Earbuds'
  | 'Television & Video'
  | 'Home Audio'
  | 'Car Electronics'
  | 'Portable Audio & Video'
  | 'Wearable Technology'
  | 'Other Electronics'

export type AssistantIntent = {
  category: AssistantCategory | null
  max_budget_override: number | null
  min_budget_override?: number | null
  brand?: string | null
  min_rating?: number | null
  min_battery_life_hours?: number | null
  require_battery_life_data?: boolean | null
  availability_requirement?: 'available' | null
  comfort_priority: number | null
  brand_loyalty: number | null
  battery_life_priority: number | null
  portability_priority: number | null
  connectivity_requirement: 'wireless' | 'wired' | null
  product_type_requirement?: 'headphones' | 'earbuds' | 'sleep_headphones' | null
  unsupported_requirements: string[]
}

export type AssistantRecommendation = {
  product_id: string
  catalogue_source?: 'curated' | 'amazon'
  availability_status?: 'available' | 'unavailable' | 'unverified'
  price_is_historical?: boolean
  rating_count?: number | null
  name: string
  brand: string
  category: string
  price: number
  rating: number
  image_url: string | null
  score: number
  confidence: number
  reasons: string[]
  attribute_breakdown: Record<string, number>
  score_breakdown: Record<string, number>
}

export type AssistantChatRequest = {
  user_id: number
  message: string
  limit: number
  conversation_context?: AssistantIntent
  previous_product_ids?: string[]
}

export type AgentActivityEvent = {
  sequence: number
  kind:
    | 'understanding'
    | 'planning'
    | 'selection'
    | 'tool_execution'
    | 'evaluation'
    | 'completion'
  title: string
  status: 'completed' | 'failed' | 'partial'
  summary: string
  tool_name?:
    | 'product_search'
    | 'product_comparison'
    | 'get_shopper_profile'
    | 'simulate_preferences'
    | 'evaluate_results'
    | null
  succeeded?: boolean | null
}

export type AgentExecutionMetadata = {
  execution_id: string
  status: 'completed' | 'partial' | 'fallback' | 'unavailable'
  plan_summary: string
  tools_executed: Array<
    | 'product_search'
    | 'product_comparison'
    | 'get_shopper_profile'
    | 'simulate_preferences'
    | 'evaluate_results'
  >
  tool_execution_count: number
  evaluation_outcome: string
  activity: string[]
  events?: AgentActivityEvent[]
}

export type AssistantChatResponse = {
  user_id: number
  answer: string
  intent: AssistantIntent
  recommendations: AssistantRecommendation[]
  fallback_used: boolean
  notes: string[]
  has_more: boolean
  kind: 'shopping' | 'acknowledgement' | 'clarification' | 'answer'
  agent_metadata?: AgentExecutionMetadata | null
}
