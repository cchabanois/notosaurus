# The minified build the device tests run on only (-Pnotosaurus.minified): the libraries the
# tests' APK shares with the app are in the app's APK only, so kept there though the app
# itself doesn't use them (R8 removed them from it: the test runner then fails to start).
# The app's own code kept too: the tests reach into it (LocalServer's json, Lessons…), which
# R8 would otherwise remove or inline where the app doesn't call it. What R8 shrinks and
# obfuscates here, as in the release, is the libraries' the tests don't share: Ktor, Play
# Billing and Integrity, the QR code scanner. Never in the release.
-keep class app.notosaurus.** { *; }
-keep class androidx.tracing.** { *; }
-keep class kotlin.** { *; }
-keep class kotlinx.coroutines.** { *; }
-keep class okhttp3.** { *; }
-keep class okio.** { *; }
-keep class androidx.** { *; }
-keep class kotlinx.serialization.** { *; }
-keep class com.ichi2.anki.api.** { *; }
