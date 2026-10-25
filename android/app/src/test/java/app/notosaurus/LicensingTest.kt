package app.notosaurus

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LicensingTest {
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
}
