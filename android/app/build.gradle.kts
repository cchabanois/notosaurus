import org.gradle.api.file.FileSystemOperations
import javax.inject.Inject

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.serialization)
}

/** The Notosaurus web page (the repository's static/), shipped in the app's
 * assets under web/: the app shows the same page as the computer. */
abstract class CopyWebPage : DefaultTask() {
    @get:InputDirectory abstract val source: DirectoryProperty
    @get:OutputDirectory abstract val outputDir: DirectoryProperty
    @get:Inject abstract val files: FileSystemOperations

    @TaskAction
    fun copy() {
        files.sync {
            from(source)
            into(outputDir.dir("web"))
        }
    }
}

// Notosaurus's version, the same everywhere: the root pyproject.toml's (the only place
// to change it), e.g. 1.1.0 → versionName "1.1.0", versionCode 10100 (Google Play's
// number, which must grow: major × 10000 + minor × 100 + patch)
val notosaurusVersion: String = Regex("""(?m)^version\s*=\s*"([^"]+)"""")
    // read through Gradle, so that a change is always seen (configuration cache included)
    .find(providers.fileContents(rootProject.layout.projectDirectory.file("../pyproject.toml")).asText.get())!!
    .groupValues[1]
val notosaurusVersionCode: Int = Regex("""^(\d+)\.(\d+)\.(\d+)""").find(notosaurusVersion)!!.destructured
    .let { (major, minor, patch) -> major.toInt() * 10000 + minor.toInt() * 100 + patch.toInt() }

// The same revision's: android/app → ../../static (another with -Pnotosaurus.web=<path>)
val webPage = providers.gradleProperty("notosaurus.web").orElse("../../static")
val copyWebPage = tasks.register<CopyWebPage>("copyWebPage") {
    source.set(layout.projectDirectory.dir(webPage))
}

android {
    namespace = "app.notosaurus"
    compileSdk = 37

    defaultConfig {
        applicationId = "app.notosaurus"
        minSdk = 28 // ImageDecoder: photos upright and resized in one step
        targetSdk = 36
        versionCode = notosaurusVersionCode
        versionName = notosaurusVersion
        // On a device (androidTest): AnkiDroid's real API, the whole app (see README, "Tests on a device")
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    testOptions {
        unitTests.all {
            // The page's files for LocalServer's tests (the same as in the app's assets)
            it.systemProperty("notosaurus.web", layout.projectDirectory.dir(webPage).get().asFile.absolutePath)
        }
    }
    packaging {
        resources.excludes += setOf("META-INF/INDEX.LIST", "META-INF/io.netty.versions.properties")
    }
    buildFeatures { buildConfig = true } // BuildConfig.VERSION_NAME, for the relay
    lint {
        // AnkiDroid's own rule (its API brings its lint checks): its code takes the time from
        // its collection, ours has none
        disable += "DirectSystemCurrentTimeMillisUsage"
    }
    // The relay a fresh install calls (changed in the settings, "Advanced"): the test
    // instance while developing (its own licences, notosaurus-cloud's README), the real
    // one in a release, so that no release ever calls the test instance
    buildTypes {
        debug { buildConfigField("String", "DEFAULT_RELAY", "\"https://notosaurus-relay-dev-773198805942.europe-west1.run.app\"") }
        release { buildConfigField("String", "DEFAULT_RELAY", "\"https://notosaurus-relay-773198805942.europe-west1.run.app\"") }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(copyWebPage, CopyWebPage::outputDir)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    // Not used directly: the version the ActivityResult APIs need (an older one comes with the libraries)
    implementation(libs.androidx.fragment)
    implementation(libs.androidx.activity)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.ankidroid.api)
    implementation(libs.ktor.server.core)
    implementation(libs.ktor.server.cio)
    implementation(libs.code.scanner)
    implementation(libs.kotlinx.coroutines.play.services)
    testImplementation(libs.junit)
    testImplementation(libs.ktor.server.test.host)
    testImplementation(libs.mockwebserver)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.rules)
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.mockwebserver)
}
