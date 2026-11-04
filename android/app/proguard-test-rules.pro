# R8's rules for the device tests' APK when they run on the minified build
# (-Pnotosaurus.minified, build.gradle.kts): it is minified too, with the app's mapping.
# The tests and their runner kept whole, their annotations with them: the instrumentation
# finds them by name and @Test (without the annotations, no test runs at all).
-keepattributes *Annotation*, Signature, InnerClasses, EnclosingMethod
-keep class app.notosaurus.** { *; }
-keep class androidx.test.** { *; }
-keep class org.junit.** { *; }
-keep class junit.** { *; }
-keep class org.hamcrest.** { *; }
-keep class mockwebserver3.** { *; }

# Error Prone's annotations (Guava's, in the tests' libraries) name the compiler's API
-dontwarn javax.lang.model.element.Modifier
