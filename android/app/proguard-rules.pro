# R8's rules for the release (build.gradle.kts). The libraries bring their own (OkHttp,
# kotlinx.serialization, coroutines, Play Billing and Integrity); Android's default keeps
# the manifest's components and the WebView's @JavascriptInterface methods (PageDownloads).

# Ktor's debugger detection (IntellijIdeaDebugDetector) reads the JVM's management API,
# which Android doesn't have: never called there
-dontwarn java.lang.management.ManagementFactory
-dontwarn java.lang.management.RuntimeMXBean
