package app.notosaurus

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.core.content.edit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { MaterialTheme { Prototype() } }
    }
}

private class Photo(val jpeg: ByteArray, val thumbnail: Bitmap)

/**
 * The prototype's one screen: the relay and the licence, the photos, the prompt,
 * the cards, then AnkiDroid.
 */
@Composable
private fun Prototype() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("settings", Context.MODE_PRIVATE) }
    val scope = rememberCoroutineScope()
    val anki = remember { Anki(context) }

    var relayUrl by remember { mutableStateOf(prefs.getString("relay", "http://192.168.1.10:8080")!!) }
    var key by remember { mutableStateOf(prefs.getString("key", "nts_dev")!!) }
    var prompt by remember { mutableStateOf(context.getString(R.string.default_prompt)) }
    val photos = remember { mutableStateListOf<Photo>() }
    var busy by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<ExtractResponse?>(null) }

    fun relay(): Relay {
        prefs.edit { putString("relay", relayUrl.trim()).putString("key", key.trim()) }
        return Relay(relayUrl.trim(), key.trim())
    }

    fun work(block: suspend () -> String) {
        busy = true
        status = ""
        scope.launch {
            status = try {
                block()
            } catch (e: RelayException) {
                context.getString(R.string.relay_error, e.message)
            } catch (e: Exception) {
                context.getString(R.string.error, e.toString())
            }
            busy = false
        }
    }

    fun addPhoto(uri: Uri) = work {
        val jpeg = withContext(Dispatchers.Default) { Photos.prepare(context, uri) }
        val options = BitmapFactory.Options().apply { inSampleSize = 8 }
        photos += Photo(jpeg, BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size, options))
        context.getString(R.string.photo_added, jpeg.size / 1024)
    }

    var pending by remember { mutableStateOf<Uri?>(null) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { taken ->
        pending?.let { if (taken) addPhoto(it) }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(10)) { uris ->
        uris.forEach { addPhoto(it) }
    }

    fun send() = work {
        val sent = withContext(Dispatchers.IO) { anki.send(result!!.deck) }
        context.getString(R.string.sent, sent.added, sent.deck, sent.duplicates, sent.skipped)
    }

    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) send() else status = context.getString(R.string.anki_permission_refused)
    }

    Column(
        Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(stringResource(R.string.app_name), style = MaterialTheme.typography.headlineMedium)

        OutlinedTextField(
            relayUrl, { relayUrl = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.relay)) },
        )
        OutlinedTextField(
            key, { key = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.licence)) },
        )
        OutlinedButton(enabled = !busy, onClick = {
            work {
                val account = relay().account()
                context.getString(R.string.account, account.plan, account.creditsLeft, account.dailyLeft)
            }
        }) { Text(stringResource(R.string.test)) }

        HorizontalDivider()

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(enabled = !busy && photos.size < 10, onClick = {
                val file = File(context.cacheDir, "photos/photo-${System.currentTimeMillis()}.jpg")
                file.parentFile!!.mkdirs()
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.photos", file)
                pending = uri
                camera.launch(uri)
            }) { Text(stringResource(R.string.take_photo)) }
            OutlinedButton(enabled = !busy, onClick = {
                picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
            }) { Text(stringResource(R.string.choose_photos)) }
        }
        if (photos.isNotEmpty()) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                photos.forEach { Image(it.thumbnail.asImageBitmap(), null, Modifier.size(72.dp)) }
            }
            OutlinedButton(enabled = !busy, onClick = {
                photos.clear()
                result = null
            }) { Text(stringResource(R.string.clear_photos)) }
        }

        OutlinedTextField(
            prompt, { prompt = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.prompt)) },
        )
        Button(enabled = !busy && prompt.isNotBlank(), onClick = {
            work {
                val answer = relay().extract(ExtractRequest(prompt = prompt), photos.map { it.jpeg })
                result = answer
                context.getString(
                    R.string.extracted, answer.deck.cards.size, answer.usage.credits, answer.usage.creditsLeft,
                )
            }
        }) { Text(stringResource(R.string.make_cards)) }

        if (busy) CircularProgressIndicator()
        if (status.isNotEmpty()) Text(status)

        result?.let { answer ->
            HorizontalDivider()
            Text(answer.deck.deck, style = MaterialTheme.typography.titleMedium)
            answer.deck.cards.forEach { card ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(card.front, style = MaterialTheme.typography.bodyLarge)
                        Text(card.back, style = MaterialTheme.typography.bodyMedium)
                        if (card.info.isNotBlank()) Text(card.info, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            Button(enabled = !busy, onClick = {
                when {
                    !anki.installed() -> status = context.getString(R.string.anki_missing)
                    anki.permitted() -> send()
                    else -> permission.launch(Anki.PERMISSION)
                }
            }) { Text(stringResource(R.string.send_to_anki)) }
        }
    }
}
