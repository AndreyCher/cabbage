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
}

export type Identity = {
  identity: string
  config: JsonObject
  revision: number
  created_at: string
  updated_at: string
  in_use: boolean
  pending_operation?: string | null
  default_proxy_config_id?: string | null
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
