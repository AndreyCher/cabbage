export type JsonObject = Record<string, unknown>

export type ProxyConfig = {
  id: string
  name: string
  scheme: 'http' | 'https'
  host: string
  port: number
  username?: string | null
  has_password: boolean
  bypass?: string | null
  geoip: { enabled: boolean; validate_identity: boolean; fail_on_mismatch: boolean }
  verify_ssl: boolean
  enabled: boolean
  country_code?: string | null
  country_name?: string | null
  exit_ip?: string | null
  timezone?: string | null
  last_checked_at?: string | null
  last_used_at?: string | null
}

export type Identity = {
  identity: string
  config: JsonObject
  revision: number
  created_at: string
  updated_at: string
  in_use: boolean
  pending_operation?: string | null
  proxy_country_code?: string | null
}

export type Scenario = {
  id: string
  name: string
  version: number
  definition: JsonObject
  active: boolean
  deleted: boolean
  created_at: string
  run_count: number
}
