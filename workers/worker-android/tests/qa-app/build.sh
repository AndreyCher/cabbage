#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
build_dir=$(mktemp -d)
sdk=/opt/android
build_tools="$sdk/build-tools/36.0.0"
android_jar="$sdk/platforms/android-34/android.jar"
mkdir -p "$build_dir/classes" "$build_dir/dex"
javac -source 8 -target 8 -classpath "$android_jar" -d "$build_dir/classes" MainActivity.java
"$build_tools/d8" --lib "$android_jar" --output "$build_dir/dex" "$build_dir/classes/org/example/telephonyqa/MainActivity.class"
"$build_tools/aapt" package -f -M AndroidManifest.xml -I "$android_jar" -F "$build_dir/unsigned.apk"
cd "$build_dir/dex"
"$build_tools/aapt" add "$build_dir/unsigned.apk" classes.dex
keytool -genkeypair -keystore "$build_dir/test.jks" -storepass android -keypass android -alias qa -keyalg RSA -validity 1 -dname 'CN=QA' >/dev/null 2>&1
"$build_tools/zipalign" -f 4 "$build_dir/unsigned.apk" "$build_dir/aligned.apk"
"$build_tools/apksigner" sign --ks "$build_dir/test.jks" --ks-pass pass:android --out "$build_dir/test.apk" "$build_dir/aligned.apk"
adb install -r "$build_dir/test.apk"
