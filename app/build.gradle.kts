import org.gradle.api.file.FileSystemOperations
import javax.inject.Inject

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.serialization)
}

/** The Notosaurus web page (the public repository's static/), shipped in the app's
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

// The public repository checked out next to this one (prototype; later: a pinned version)
val webPage = providers.gradleProperty("notosaurus.web").orElse("../../notosaurus/static")
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
        versionCode = 1
        versionName = "0.1.0"
    }
    packaging {
        resources.excludes += setOf("META-INF/INDEX.LIST", "META-INF/io.netty.versions.properties")
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
    implementation(libs.androidx.activity)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.ankidroid.api)
    implementation(libs.ktor.server.core)
    implementation(libs.ktor.server.cio)
}
