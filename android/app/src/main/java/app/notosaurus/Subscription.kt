package app.notosaurus

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume

/** The subscription as Google Play offers it: its price a month, its free trial (days; 0: none). */
data class Offer(val price: String, val trialDays: Int)

/** Google Play's subscription (a fake in the tests). The relay checks every purchase
 * (/v1/subscribe): the app only buys and lists them. */
interface SubscriptionStore {
    /** The subscription offered; null without Google Play, or before it is on sale. */
    suspend fun offer(): Offer?

    /** Google Play's purchase screen; the purchase's token, or null when given up. */
    suspend fun subscribe(): String?

    /** The tokens of the subscriptions this Google account has (a new phone, the app
     * reinstalled: restored with them). */
    suspend fun owned(): List<String>

    /** Google Play's page of the subscription: cancel it, change the card. */
    fun manage()
}

/**
 * Google Play Billing: the monthly subscription (its free trial first, when this Google
 * account may have it: Google Play only offers it once). `activity`: the one showing the
 * purchase screen.
 */
class PlayStore(private val context: Context, private val activity: () -> Activity?) : SubscriptionStore {
    private var bought: CompletableDeferred<String?>? = null
    private val client = BillingClient.newBuilder(context)
        .setListener { result, purchases ->
            val token = purchases?.firstOrNull { it.purchaseState == Purchase.PurchaseState.PURCHASED }?.purchaseToken
            bought?.complete(if (result.responseCode == BillingClient.BillingResponseCode.OK) token else null)
        }
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .enableAutoServiceReconnection()
        .build()
    private val connecting = Mutex()

    override suspend fun offer(): Offer? {
        val product = details() ?: return null
        val offers = product.subscriptionOfferDetails.orEmpty()
        val base = offers.firstOrNull { it.offerId == null } ?: return null
        val price = base.pricingPhases.pricingPhaseList.lastOrNull()?.formattedPrice ?: return null
        // A free first phase: the trial this account may still have
        val trial = offers.firstNotNullOfOrNull { offer ->
            offer.pricingPhases.pricingPhaseList.firstOrNull()?.takeIf { it.priceAmountMicros == 0L }?.billingPeriod
        }
        return Offer(price, trial?.let(::days) ?: 0)
    }

    override suspend fun subscribe(): String? {
        val product = details() ?: return null
        val offers = product.subscriptionOfferDetails.orEmpty()
        // The trial when offered (Google Play lists only the offers this account may have)
        val offer = offers.firstOrNull { o -> o.pricingPhases.pricingPhaseList.firstOrNull()?.priceAmountMicros == 0L }
            ?: offers.firstOrNull { it.offerId == null } ?: return null
        val params = BillingFlowParams.newBuilder().setProductDetailsParamsList(
            listOf(BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(product).setOfferToken(offer.offerToken).build()),
        ).build()
        val answer = CompletableDeferred<String?>().also { bought = it }
        val shown = withContext(Dispatchers.Main) {
            val on = activity() ?: return@withContext null
            client.launchBillingFlow(on, params)
        }
        if (shown?.responseCode != BillingClient.BillingResponseCode.OK) return null
        return answer.await()
    }

    override suspend fun owned(): List<String> {
        if (!connected()) return emptyList()
        val params = QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.SUBS).build()
        return suspendCancellableCoroutine { done ->
            client.queryPurchasesAsync(params) { result, purchases ->
                val ok = result.responseCode == BillingClient.BillingResponseCode.OK
                done.resume(if (ok) purchases.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }.map { it.purchaseToken } else emptyList())
            }
        }
    }

    override fun manage() {
        val page = Uri.parse("https://play.google.com/store/account/subscriptions?sku=$PRODUCT&package=${context.packageName}")
        runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, page).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }

    private suspend fun details(): ProductDetails? {
        if (!connected()) return null
        val product = QueryProductDetailsParams.Product.newBuilder().setProductId(PRODUCT).setProductType(BillingClient.ProductType.SUBS).build()
        val params = QueryProductDetailsParams.newBuilder().setProductList(listOf(product)).build()
        return suspendCancellableCoroutine { done ->
            client.queryProductDetailsAsync(params) { result, found ->
                done.resume(found.productDetailsList.firstOrNull().takeIf { result.responseCode == BillingClient.BillingResponseCode.OK })
            }
        }
    }

    /** Connected to Google Play (once; false without it, e.g. an emulator without the store). */
    private suspend fun connected(): Boolean = connecting.withLock {
        if (client.isReady) return@withLock true
        suspendCancellableCoroutine { done ->
            client.startConnection(object : BillingClientStateListener {
                override fun onBillingSetupFinished(result: BillingResult) {
                    if (done.isActive) done.resume(result.responseCode == BillingClient.BillingResponseCode.OK)
                }

                override fun onBillingServiceDisconnected() {
                    if (done.isActive) done.resume(false)
                }
            })
        }
    }

    companion object {
        const val PRODUCT = "notosaurus_monthly" // the relay's RELAY_PLAY_PRODUCT

        /** "P7D", "P1W", "P1M"… as days. */
        fun days(period: String): Int {
            val match = Regex("""^P(\d+)([DWM])$""").find(period) ?: return 0
            val (n, unit) = match.destructured
            return n.toInt() * when (unit) { "W" -> 7; "M" -> 30; else -> 1 }
        }
    }
}
