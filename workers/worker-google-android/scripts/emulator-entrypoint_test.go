package main

import (
    "os"
    "path/filepath"
    "testing"
)

func TestConfiguredProxyOverride(t *testing.T) {
	t.Setenv("GOOGLE_ANDROID_EMULATOR_PROXY", "http://proxy.example:8080")
	if got := configuredProxy(); got != "http://proxy.example:8080" {
		t.Fatalf("configuredProxy() = %q", got)
	}
}

func writeTestJSON(t *testing.T, path, value string) {
    t.Helper()
    if err := os.WriteFile(path, []byte(value), 0o600); err != nil { t.Fatal(err) }
}

func TestConfiguredProxyDisabled(t *testing.T) {
    t.Setenv("GOOGLE_ANDROID_EMULATOR_PROXY", "")
    t.Setenv("WORKER_PROFILE", "plain")
    dir := t.TempDir()
    writeTestJSON(t, filepath.Join(dir, "system.json"), `{"paths":{"profiles_dir":"`+dir+`"}}`)
    writeTestJSON(t, filepath.Join(dir, "plain.json"), `{"proxy":{"enabled":false,"server":"proxy.example:80"}}`)
    t.Setenv("WORKER_SYSTEM_CONFIG", filepath.Join(dir, "system.json"))
    if got := configuredProxy(); got != "" { t.Fatalf("configuredProxy() = %q", got) }
}

func TestConfiguredProxyProfileWithEscapedCredentials(t *testing.T) {
    t.Setenv("GOOGLE_ANDROID_EMULATOR_PROXY", "")
    t.Setenv("WORKER_PROFILE", "proxied")
    dir := t.TempDir()
    writeTestJSON(t, filepath.Join(dir, "system.json"), `{"paths":{"profiles_dir":"`+dir+`"}}`)
    writeTestJSON(t, filepath.Join(dir, "proxied.json"), `{"proxy":{"enabled":true,"server":"proxy.example:8080/path","username":"a@b","password":"p:/x"}}`)
    t.Setenv("WORKER_SYSTEM_CONFIG", filepath.Join(dir, "system.json"))
    if got := configuredProxy(); got != "http://a%40b:p%3A%2Fx@proxy.example:8080" { t.Fatalf("configuredProxy() = %q", got) }
}

func TestConfiguredProxyMergesDefaultsAndProfile(t *testing.T) {
    t.Setenv("GOOGLE_ANDROID_EMULATOR_PROXY", "")
    t.Setenv("WORKER_PROFILE", "merged")
    dir := t.TempDir()
    global := filepath.Join(dir, "global.json")
    local := filepath.Join(dir, "local.json")
    writeTestJSON(t, global, `{"proxy":{"enabled":true,"server":"global.example:3128","username":"global"}}`)
    writeTestJSON(t, local, `{"proxy":{"server":"local.example:8080"}}`)
    writeTestJSON(t, filepath.Join(dir, "merged.json"), `{"proxy":{"username":"profile","password":"secret"}}`)
    writeTestJSON(t, filepath.Join(dir, "system.json"), `{"paths":{"global_default_config":"`+global+`","local_default_config":"`+local+`","profiles_dir":"`+dir+`"}}`)
    t.Setenv("WORKER_SYSTEM_CONFIG", filepath.Join(dir, "system.json"))
    if got := configuredProxy(); got != "http://profile:secret@local.example:8080" { t.Fatalf("configuredProxy() = %q", got) }
}
