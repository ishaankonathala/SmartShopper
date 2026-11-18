import { useRef, useState } from 'react'
import {
  ApiRequestError,
  chatWithAssistant,
  InvalidAssistantResponseError,
} from '../services/api'
import type {
  AgentActivityEvent,
  AgentExecutionMetadata,
  AssistantChatResponse,
  AssistantIntent,
  AssistantRecommendation,
} from '../types/assistant'
import {
  ASSISTANT_RECOMMENDATION_LIMIT,
  DEMO_USER_ID,
  MAX_ASSISTANT_RECOMMENDATION_LIMIT,
} from '../config'

export type ConversationTurn = {
  id: string
  message: string
  response?: AssistantChatResponse
  error?: string
  moreOptionsError?: string
}

type BusyAction = 'send' | 'more' | null
type FollowUpAction = 'more' | 'cheaper' | null

type PersistedConversation = {
  version: 1
  turns: ConversationTurn[]
  conversationContext: AssistantIntent | null
  displayedProductIds: string[]
  latestShoppingTurnId: string | null
}

type RestoredConversation = PersistedConversation & {
  persistenceNotice: string | null
}

const STORAGE_KEY = `smartshopper.conversation.v1.${DEMO_USER_ID}`
const EMPTY_CONVERSATION: PersistedConversation = {
  version: 1,
  turns: [],
  conversationContext: null,
  displayedProductIds: [],
  latestShoppingTurnId: null,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isPriority(value: unknown): value is number | null {
  return (
    value === null ||
    (typeof value === 'number' &&
      Number.isInteger(value) &&
      value >= 0 &&
      value <= 100)
  )
}

function isAssistantIntent(value: unknown): value is AssistantIntent {
  if (!isRecord(value)) return false
  return (
    (value.category === null ||
      value.category === 'Headphones' ||
      value.category === 'Laptops' ||
      value.category === 'Smartwatches' ||
      value.category === 'Home Appliances' ||
      value.category === 'Computers & Accessories' ||
      value.category === 'Camera & Photo' ||
      value.category === 'Headphones & Earbuds' ||
      value.category === 'Television & Video' ||
      value.category === 'Home Audio' ||
      value.category === 'Car Electronics' ||
      value.category === 'Portable Audio & Video' ||
      value.category === 'Wearable Technology' ||
      value.category === 'Other Electronics') &&
    (value.max_budget_override === null ||
      (isNumber(value.max_budget_override) && value.max_budget_override >= 0)) &&
    (value.min_budget_override === undefined ||
      value.min_budget_override === null ||
      (isNumber(value.min_budget_override) && value.min_budget_override >= 0)) &&
    (value.brand === undefined ||
      value.brand === null ||
      (typeof value.brand === 'string' && value.brand.trim().length > 0)) &&
    (value.min_rating === undefined ||
      value.min_rating === null ||
      (isNumber(value.min_rating) && value.min_rating >= 1 && value.min_rating <= 5)) &&
    (value.min_battery_life_hours === undefined ||
      value.min_battery_life_hours === null ||
      (isNumber(value.min_battery_life_hours) && value.min_battery_life_hours > 0)) &&
    (value.require_battery_life_data === undefined ||
      value.require_battery_life_data === null ||
      typeof value.require_battery_life_data === 'boolean') &&
    (value.availability_requirement === undefined ||
      value.availability_requirement === null ||
      value.availability_requirement === 'available') &&
    isPriority(value.comfort_priority) &&
    isPriority(value.brand_loyalty) &&
    isPriority(value.battery_life_priority) &&
    isPriority(value.portability_priority) &&
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

function isRecommendation(value: unknown): value is AssistantRecommendation {
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
      isNumber(value.rating_count)) &&
    typeof value.name === 'string' &&
    typeof value.brand === 'string' &&
    typeof value.category === 'string' &&
    isNumber(value.price) &&
    isNumber(value.rating) &&
    (value.image_url === null || typeof value.image_url === 'string') &&
    isNumber(value.score) &&
    isNumber(value.confidence) &&
    Array.isArray(value.reasons) &&
    value.reasons.every((reason) => typeof reason === 'string') &&
    isRecord(value.attribute_breakdown) &&
    Object.values(value.attribute_breakdown).every(isNumber) &&
    isRecord(value.score_breakdown) &&
    Object.values(value.score_breakdown).every(isNumber)
  )
}

function isAssistantResponse(value: unknown): value is AssistantChatResponse {
  return (
    isRecord(value) &&
    Number.isInteger(value.user_id) &&
    typeof value.answer === 'string' &&
    isAssistantIntent(value.intent) &&
    Array.isArray(value.recommendations) &&
    value.recommendations.every(isRecommendation) &&
    typeof value.fallback_used === 'boolean' &&
    Array.isArray(value.notes) &&
    value.notes.every((note) => typeof note === 'string') &&
    typeof value.has_more === 'boolean' &&
    (value.kind === 'shopping' ||
      value.kind === 'acknowledgement' ||
      value.kind === 'clarification' ||
      value.kind === 'answer') &&
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

function isConversationTurn(value: unknown): value is ConversationTurn {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.message === 'string' &&
    (value.response === undefined || isAssistantResponse(value.response)) &&
    (value.error === undefined || typeof value.error === 'string') &&
    (value.moreOptionsError === undefined ||
      typeof value.moreOptionsError === 'string')
  )
}

function readConversation(): RestoredConversation {
  if (typeof window === 'undefined') {
    return { ...EMPTY_CONVERSATION, persistenceNotice: null }
  }

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored) return { ...EMPTY_CONVERSATION, persistenceNotice: null }

    const parsed: unknown = JSON.parse(stored)
    if (
      !isRecord(parsed) ||
      parsed.version !== 1 ||
      !Array.isArray(parsed.turns) ||
      !parsed.turns.every(isConversationTurn) ||
      !(parsed.conversationContext === null ||
        isAssistantIntent(parsed.conversationContext)) ||
      !Array.isArray(parsed.displayedProductIds) ||
      !parsed.displayedProductIds.every((id) => typeof id === 'string') ||
      !(parsed.latestShoppingTurnId === null ||
        typeof parsed.latestShoppingTurnId === 'string')
    ) {
      return {
        ...EMPTY_CONVERSATION,
        persistenceNotice:
          'The saved conversation could not be restored. You can start a new chat.',
      }
    }

    const turns = parsed.turns.map((turn) =>
      turn.response || turn.error
        ? turn
        : {
            ...turn,
            error: 'This request was interrupted. You can retry it here.',
          },
    )
    return {
      version: 1,
      turns,
      conversationContext: parsed.conversationContext,
      displayedProductIds: parsed.displayedProductIds,
      latestShoppingTurnId: parsed.latestShoppingTurnId,
      persistenceNotice: null,
    }
  } catch {
    return {
      ...EMPTY_CONVERSATION,
      persistenceNotice:
        'Conversation storage is unavailable. The chat will remain until you leave this page.',
    }
  }
}

function getFollowUpAction(message: string): FollowUpAction {
  const normalized = message
    .trim()
    .toLowerCase()
    .replace(/[.!?]+$/, '')
    .replace(/\s+/g, ' ')

  if (
    /^(?:(?:please )?(?:(?:can|could) you )?)?(?:(?:show|find|give|suggest)(?: me)? )?(?:(?:some|a few) )?(?:more|other|additional)(?: (?:options?|products?|ones?|recommendations?|alternatives?))?(?: please)?$/.test(
      normalized,
    ) ||
    /^(?:anything else|any other options?|any others?)$/.test(normalized)
  ) {
    return 'more'
  }
  if (
    /^(?:please )?(?:(?:show|find|give|suggest)(?: me)? )?(?:some )?(?:cheaper|less expensive|lower[- ]priced)(?: (?:ones?|options?|products?|alternatives?))?(?: please)?$/.test(
      normalized,
    )
  ) {
    return 'cheaper'
  }
  return null
}

function getUserFacingError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 404) {
      return 'Your demo shopper profile could not be found. Please check the account setup.'
    }
    if (error.status === 422) {
      return 'We could not process that request. Try rephrasing it with a product category and budget.'
    }
    if (error.status >= 500) {
      return 'The shopping service is temporarily unavailable. Please try again in a moment.'
    }
    return 'We could not complete that request. Please try again.'
  }

  if (error instanceof InvalidAssistantResponseError || error instanceof SyntaxError) {
    return 'The shopping service returned an unexpected response. Please try again.'
  }

  if (error instanceof TypeError) {
    return 'We could not connect to the shopping service. Check your connection and try again.'
  }

  return 'Something went wrong while finding recommendations. Please try again.'
}

function saveConversation(state: PersistedConversation): boolean {
  if (typeof window === 'undefined') return true
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    return true
  } catch {
    return false
  }
}

export function useAssistantChat() {
  const [restored] = useState(readConversation)
  const [turns, setTurns] = useState(restored.turns)
  const turnsRef = useRef(restored.turns)
  const [busyAction, setBusyAction] = useState<BusyAction>(null)
  const [busyTurnId, setBusyTurnId] = useState<string | null>(null)
  const [persistenceNotice, setPersistenceNotice] = useState<string | null>(
    restored.persistenceNotice,
  )
  const busyRef = useRef(false)
  const nextId = useRef(restored.turns.length)
  const conversationContext = useRef(restored.conversationContext)
  const displayedProductIds = useRef(restored.displayedProductIds)
  const latestShoppingTurnId = useRef(restored.latestShoppingTurnId)

  function persist(nextTurns: ConversationTurn[]) {
    const success = saveConversation({
      version: 1,
      turns: nextTurns,
      conversationContext: conversationContext.current,
      displayedProductIds: displayedProductIds.current,
      latestShoppingTurnId: latestShoppingTurnId.current,
    })
    setPersistenceNotice(
      success
        ? null
        : 'Conversation storage is unavailable. The chat will remain until you leave this page.',
    )
  }

  function updateTurns(
    update: (current: ConversationTurn[]) => ConversationTurn[],
  ) {
    const nextTurns = update(turnsRef.current)
    turnsRef.current = nextTurns
    setTurns(nextTurns)
    persist(nextTurns)
  }

  function recordResponse(
    response: AssistantChatResponse,
    action: FollowUpAction,
    turnId: string,
  ): AssistantChatResponse {
    if (response.kind === 'acknowledgement' || response.kind === 'answer') {
      return response
    }

    conversationContext.current = response.intent
    if (response.kind === 'clarification') return response

    const newProductIds = response.recommendations.map(
      (product) => product.product_id,
    )
    displayedProductIds.current =
      action === 'more'
        ? [...new Set([...displayedProductIds.current, ...newProductIds])].slice(
            0,
            MAX_ASSISTANT_RECOMMENDATION_LIMIT,
          )
        : newProductIds.slice(0, MAX_ASSISTANT_RECOMMENDATION_LIMIT)
    latestShoppingTurnId.current = turnId
    return {
      ...response,
      has_more:
        response.has_more &&
        displayedProductIds.current.length < MAX_ASSISTANT_RECOMMENDATION_LIMIT,
    }
  }

  async function submitTurn(
    id: string,
    message: string,
    action: FollowUpAction,
  ): Promise<void> {
    if (busyRef.current) return
    busyRef.current = true
    setBusyAction('send')
    setBusyTurnId(id)

    try {
      const response = await chatWithAssistant({
        user_id: DEMO_USER_ID,
        message,
        limit: ASSISTANT_RECOMMENDATION_LIMIT,
        conversation_context: conversationContext.current ?? undefined,
        previous_product_ids: displayedProductIds.current,
      })
      const trackedResponse = recordResponse(response, action, id)
      updateTurns((current) =>
        current.map((turn) =>
          turn.id === id
            ? { ...turn, response: trackedResponse, error: undefined }
            : turn,
        ),
      )
    } catch (error) {
      updateTurns((current) =>
        current.map((turn) =>
          turn.id === id ? { ...turn, error: getUserFacingError(error) } : turn,
        ),
      )
    } finally {
      busyRef.current = false
      setBusyAction(null)
      setBusyTurnId(null)
    }
  }

  async function sendMessage(message: string): Promise<void> {
    const trimmedMessage = message.trim()
    if (!trimmedMessage || busyRef.current) return

    nextId.current += 1
    const id = `turn-${Date.now()}-${nextId.current}`
    updateTurns((current) => [...current, { id, message: trimmedMessage }])
    await submitTurn(id, trimmedMessage, getFollowUpAction(trimmedMessage))
  }

  async function retryMessage(turnId: string): Promise<void> {
    if (busyRef.current) return
    const turn = turnsRef.current.find((item) => item.id === turnId)
    if (!turn?.error) return

    updateTurns((current) =>
      current.map((item) =>
        item.id === turnId ? { ...item, error: undefined } : item,
      ),
    )
    await submitTurn(turnId, turn.message, getFollowUpAction(turn.message))
  }

  async function showMoreOptions(turnId: string): Promise<void> {
    if (busyRef.current) return
    const turn = turnsRef.current.find((item) => item.id === turnId)
    if (
      !turn?.response ||
      turnId !== latestShoppingTurnId.current ||
      !turn.response.has_more ||
      displayedProductIds.current.length >= MAX_ASSISTANT_RECOMMENDATION_LIMIT
    ) {
      return
    }

    busyRef.current = true
    setBusyAction('more')
    setBusyTurnId(turnId)

    try {
      const response = await chatWithAssistant({
        user_id: DEMO_USER_ID,
        message: 'Show me more options.',
        limit: ASSISTANT_RECOMMENDATION_LIMIT,
        conversation_context: turn.response.intent,
        previous_product_ids: displayedProductIds.current,
      })
      const trackedResponse = recordResponse(response, 'more', turnId)
      updateTurns((current) =>
        current.map((item) => {
          if (item.id !== turnId || !item.response) return item
          const previousResponse = item.response
          const knownIds = new Set(
            previousResponse.recommendations.map(
              (product) => product.product_id,
            ),
          )
          return {
            ...item,
            response: {
              ...trackedResponse,
              recommendations: [
                ...previousResponse.recommendations,
                ...trackedResponse.recommendations.filter(
                  (product) => !knownIds.has(product.product_id),
                ),
              ],
              fallback_used:
                previousResponse.fallback_used || trackedResponse.fallback_used,
              notes: [
                ...new Set([
                  ...previousResponse.notes,
                  ...trackedResponse.notes,
                ]),
              ],
            },
            moreOptionsError: undefined,
          }
        }),
      )
    } catch (error) {
      updateTurns((current) =>
        current.map((item) =>
          item.id === turnId
            ? { ...item, moreOptionsError: getUserFacingError(error) }
            : item,
        ),
      )
    } finally {
      busyRef.current = false
      setBusyAction(null)
      setBusyTurnId(null)
    }
  }

  function startNewChat(): void {
    if (busyRef.current) return
    conversationContext.current = null
    displayedProductIds.current = []
    latestShoppingTurnId.current = null
    nextId.current = 0
    updateTurns(() => [])
  }

  return {
    turns,
    busyAction,
    busyTurnId,
    persistenceNotice,
    sendMessage,
    retryMessage,
    showMoreOptions,
    startNewChat,
  }
}
