export type HealthResponse = {
  status: 'ok' | 'degraded'
  app: string
  environment: string
  database: 'connected' | 'unavailable'
  version: string
}
