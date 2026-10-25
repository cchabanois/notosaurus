package app.notosaurus

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonPrimitive
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

/** The licence and how the app gets one (Licensing), on its own: the relay a fake server,
 * Google Play a fake store. */
class LicensingTest {
    private val relay = MockWebServer()
    private val asked = mutableListOf<String>() // the relay's routes asked, in order

    /** Google Play: the purchases this account owns, counted as they are asked for. */
    private class FakeStore : SubscriptionStore {
        val ownedAsked = AtomicInteger()
        var owned = listOf<String>()
        override suspend fun offers() = emptyList<Offer>()
        override suspend fun subscribe(plan: String): Bought = Bought.GivenUp
        override suspend fun owned() = owned.also { ownedAsked.incrementAndGet() }
        override fun manage() {}
        override fun device() = "ab".repeat(32)
        override suspend fun integrity(device: String) = "integrity-1"
    }

    @Before fun start() {
        relay.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                synchronized(asked) { asked += request.url.encodedPath }
                Thread.sleep(50) // the relay takes a moment: the calls overlap
                return MockResponse.Builder().body("""{"key": "nts_k", "account": {"plan": "free_trial", "credits_left": 300, "daily_left": 150}}""").build()
            }
        }
        relay.start()
    }

    @After fun stop() = relay.close()

    @Test
    fun fiveAiCallsAtOnceStartOneTrial() = runBlocking {
        val licensing = Licensing(MemoryPreferences(), { relay.url("/").toString() }, FakeStore())
        val keys = (1..5).map { async(Dispatchers.IO) { licensing.trialKey() } }.awaitAll()
        assertEquals(List(5) { "nts_k" }, keys)
        assertEquals(listOf("/v1/trial"), asked) // once, however many at the same time
        assertEquals(300, licensing.takeTrialStarted()!!["credits_left"]!!.jsonPrimitive.int)
        assertEquals(null, licensing.takeTrialStarted()) // told once
    }

    @Test
    fun theSubscriptionCheckedAgainOncePerPeriod() {
        var clock = 0L
        val store = FakeStore()
        val licensing = Licensing(MemoryPreferences(), { relay.url("/").toString() }, store, now = { clock })
        repeat(3) { licensing.recheckSoon() } // the relay saying it lapsed, call after call
        waitFor { store.ownedAsked.get() == 1 }
        Thread.sleep(200)
        assertEquals(1, store.ownedAsked.get())
        clock += 601L * 1_000_000_000L // past the period
        licensing.recheckSoon()
        waitFor { store.ownedAsked.get() == 2 }
        licensing.stop()
    }

    @Test
    fun aPendingPurchaseLookedForAWeekAtMost() {
        val prefs = MemoryPreferences()
        val licensing = Licensing(prefs, { "https://relay" }, null)
        assertFalse(licensing.purchasePending)
        licensing.purchasePending = true
        assertTrue(licensing.purchasePending)
        // Never paid: Google Play cancelled it; no more asked at each opening of the settings
        prefs["purchase_pending"] = (System.currentTimeMillis() - 8 * 86_400_000L).toString()
        assertFalse(licensing.purchasePending)
        licensing.purchasePending = true
        licensing.purchasePending = false
        assertFalse(licensing.purchasePending)
    }

    private fun waitFor(condition: () -> Boolean) {
        val deadline = System.currentTimeMillis() + 5_000
        while (!condition()) {
            if (System.currentTimeMillis() > deadline) throw AssertionError("not in time")
            Thread.sleep(20)
        }
    }
}
