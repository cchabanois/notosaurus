package app.notosaurus

/** A test needing the app freshly installed (never granted AnkiDroid's permission: revoking it
 * would kill the tests' process): left out of a run, run on its own with -Pnotosaurus.freshInstall
 * (Gradle installs the app again). */
@Target(AnnotationTarget.CLASS)
@Retention(AnnotationRetention.RUNTIME)
annotation class FreshInstall
