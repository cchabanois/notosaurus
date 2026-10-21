import org.gradle.api.file.FileSystemOperations
import javax.inject.Inject

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.licensee)
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
    // one in a release, so that no release ever calls the test instance. A debug build
    // switches between the two in one tap (the settings' licence); a release can't.
    val realRelay = "\"https://notosaurus-relay-773198805942.europe-west1.run.app\""
    val testRelay = "\"https://notosaurus-relay-dev-773198805942.europe-west1.run.app\""
    buildTypes {
        debug {
            // The unit tests' coverage (JaCoCo): createDebugUnitTestCoverageReport
            enableUnitTestCoverage = true
            buildConfigField("String", "DEFAULT_RELAY", testRelay)
            buildConfigField("String", "REAL_RELAY", realRelay)
            buildConfigField("String", "TEST_RELAY", testRelay)
        }
        release {
            buildConfigField("String", "DEFAULT_RELAY", realRelay)
            buildConfigField("String", "REAL_RELAY", realRelay)
            buildConfigField("String", "TEST_RELAY", "\"\"")
        }
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
    implementation(libs.play.billing) // the subscription (Google Play Billing)
    implementation(libs.play.integrity) // the free trial: the app from Google Play on a real phone
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

// The libraries' licences: only those allowed here (a new one fails the build until it is
// read and added), their list shipped with the page (web/licences-android.json, "About")
licensee {
    allow("Apache-2.0")
    allow("MIT")
    allowUrl("https://opensource.org/license/mit") { because("MIT (slf4j)") }
    allowUrl("https://api.github.com/licenses/gpl-3.0") {
        because("AnkiDroid's API: GPL-3.0, which Notosaurus's AGPL-3.0 may be combined with (AGPL §13)")
    }
    allowUrl("https://developer.android.com/studio/terms.html") {
        because("Google Play services and Play Billing: not open source, theirs to ship in an app")
    }
    allowUrl("https://developer.android.com/google/play/integrity/overview#tos") {
        because("Play Integrity (the free trial): not open source, its terms let an app ship it")
    }
    allowUrl("https://developer.android.com/guide/playcore/license") {
        because("Play Core's common part, which Play Integrity brings: Google's terms, as Play Integrity's")
    }
    allowUrl("https://developers.google.com/ml-kit/terms") {
        because("ML Kit (the QR code scanner): not open source, its terms let an app ship it")
    }
    bundleAndroidAsset.set(true)
    androidAssetReportPath.set("web/licences-android.json")
}
