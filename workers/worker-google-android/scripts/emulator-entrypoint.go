// Materializes emulator start options from an autonomous worker profile.
package main

import (
    "encoding/json"
    "fmt"
    "net/url"
    "os"
    "path/filepath"
    "strings"
    "syscall"
)

type systemConfig struct { Paths struct {
    GlobalDefaultConfig string `json:"global_default_config"`
    LocalDefaultConfig string `json:"local_default_config"`
    ProfilesDir string `json:"profiles_dir"`
} `json:"paths"` }
type profileConfig struct { Proxy struct {
    Enabled bool `json:"enabled"`; Server string `json:"server"`; Username string `json:"username"`; Password *string `json:"password"`
} `json:"proxy"` }

func readJSON(path string, target any) error { data, err := os.ReadFile(path); if err != nil { return err }; return json.Unmarshal(data, target) }

func mergeConfig(dst, src map[string]any) {
    for key, value := range src {
        srcMap, srcOK := value.(map[string]any)
        dstMap, dstOK := dst[key].(map[string]any)
        if srcOK && dstOK { mergeConfig(dstMap, srcMap); continue }
        dst[key] = value
    }
}

func readConfigMap(path string, required bool) (map[string]any, error) {
    result := map[string]any{}
    err := readJSON(path, &result)
    if err != nil && !required && os.IsNotExist(err) { return map[string]any{}, nil }
    return result, err
}

func configuredProxy() string {
    if override := strings.TrimSpace(os.Getenv("GOOGLE_ANDROID_EMULATOR_PROXY")); override != "" { return override }
    profile := os.Getenv("WORKER_PROFILE"); if profile == "" { return "" }
    systemPath := os.Getenv("WORKER_SYSTEM_CONFIG"); if systemPath == "" { systemPath = "/config/config.json" }
    var system systemConfig
    if err := readJSON(systemPath, &system); err != nil { fmt.Printf("[worker-google-android] proxy configuration ignored: %v\n", err); return "" }
    merged := map[string]any{}
    for _, item := range []struct { path string; required bool }{
        {system.Paths.GlobalDefaultConfig, false},
        {system.Paths.LocalDefaultConfig, false},
        {filepath.Join(system.Paths.ProfilesDir, profile+".json"), true},
    } {
        if item.path == "" { continue }
        data, err := readConfigMap(item.path, item.required)
        if err != nil { fmt.Printf("[worker-google-android] proxy configuration ignored: %v\n", err); return "" }
        mergeConfig(merged, data)
    }
    encoded, err := json.Marshal(merged)
    if err != nil { return "" }
    var profileData profileConfig
    if err := json.Unmarshal(encoded, &profileData); err != nil { fmt.Printf("[worker-google-android] proxy configuration ignored: %v\n", err); return "" }
    proxy := profileData.Proxy
    if !proxy.Enabled || proxy.Server == "" { return "" }
    raw := proxy.Server; if !strings.Contains(raw, "://") { raw = "http://" + raw }
    parsed, err := url.Parse(raw); if err != nil || parsed.Hostname() == "" { return "" }
    if proxy.Username != "" { if proxy.Password == nil { parsed.User = url.User(proxy.Username) } else { parsed.User = url.UserPassword(proxy.Username, *proxy.Password) } }
    parsed.Path, parsed.RawQuery, parsed.Fragment = "", "", ""
    return parsed.String()
}

func main() {
    params := os.Getenv("EMULATOR_PARAMS"); if params == "" { params = "-no-audio" }
    if proxy := configuredProxy(); proxy != "" && !strings.Contains(params, "-http-proxy") { params += " -http-proxy " + proxy; fmt.Println("[worker-google-android] emulator proxy: configured") }
    _ = os.Setenv("EMULATOR_PARAMS", params)
    if err := syscall.Exec("/android/sdk/launch-emulator.sh", []string{"/android/sdk/launch-emulator.sh"}, os.Environ()); err != nil { panic(err) }
}
