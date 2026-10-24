package app.notosaurus

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import android.util.Log
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import com.google.android.play.core.integrity.IntegrityManagerFactory
import com.google.android.play.core.integrity.StandardIntegrityManager.PrepareIntegrityTokenRequest
import com.google.android.play.core.integrity.StandardIntegrityManager.StandardIntegrityTokenRequest
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import java.security.MessageDigest
import kotlin.coroutines.resume

/** A base plan as Google Play offers it ("monthly" or "yearly"): its price a period, its
 * free trial (days; 0: none). */
data class Offer(val plan: String, val price: String, val trialDays: Int)

/** What Google Play's purchase screen ended with. */
sealed interface Bought {
    data class Paid(val token: String) : Bought

    /** A payment made later (some ways to pay, cash or a bank transfer): the subscription
     * restored once Google Play has it. */
    data object Pending : Bought

    data object GivenUp : Bought
}

/** Google Play's subscription (a fake in the tests). The relay checks every purchase
 * (/v1/subscribe): the app only buys and lists them. */
interface SubscriptionStore {
    /** The base plans offered, a month's first; none without Google Play, or before it is on sale. */
    suspend fun offers(): List<Offer>

    /** Google Play's purchase screen for a base plan: paid (its token), pending, or given up. */
    suspend fun subscribe(plan: String): Bought

    /** The tokens of the subscriptions this Google account has (a new phone, the app
     * reinstalled: restored with them). */
    suspend fun owned(): List<String>

    /** Google Play's page of the subscription: cancel it, change the card. */
    fun manage()

    /** This phone, for the free trial (once per phone): a SHA-256 in hex, the same as long
     * as the app is on it (reinstalled too), never the same in another app. */
    fun device(): String

    /** Play Integrity's token for the free trial, bound to `device`; null without Google Play. */
    suspend fun integrity(device: String): String?
}

/**
 * Google Play Billing: the subscription, a month or a year (its free trial first, when this
 * Google account may have it: Google Play only offers it once). `activity`: the one showing
 * the purchase screen.
 */
class PlayStore(private val context: Context, private val activity: () -> Activity?) : SubscriptionStore {
    private var bought: CompletableDeferred<Bought>? = null
    private val client = BillingClient.newBuilder(context)
        .setListener { result, purchases ->
            val ok = result.responseCode == BillingClient.BillingResponseCode.OK
            val paid = purchases?.firstOrNull { it.purchaseState == Purchase.PurchaseState.PURCHASED }?.purchaseToken
            val pending = purchases?.any { it.purchaseState == Purchase.PurchaseState.PENDING } == true
            bought?.complete(
                when {
                    ok && paid != null -> Bought.Paid(paid)
                    ok && pending -> Bought.Pending
                    else -> Bought.GivenUp
                },
            )
        }
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .enableAutoServiceReconnection()
        .build()
    private val connecting = Mutex()

    override suspend fun offers(): List<Offer> {
        val product = details() ?: return emptyList()
        return PLANS.mapNotNull { plan ->
            val offers = product.subscriptionOfferDetails.orEmpty().filter { it.basePlanId == plan }
            val base = offers.firstOrNull { it.offerId == null } ?: return@mapNotNull null
            val price = base.pricingPhases.pricingPhaseList.lastOrNull()?.formattedPrice ?: return@mapNotNull null
            // A free first phase: the trial this account may still have
            val trial = offers.firstNotNullOfOrNull { offer ->
                offer.pricingPhases.pricingPhaseList.firstOrNull()?.takeIf { it.priceAmountMicros == 0L }?.billingPeriod
            }
            Offer(plan, price, trial?.let(::days) ?: 0)
        }
    }

    override suspend fun subscribe(plan: String): Bought {
        val product = details() ?: return Bought.GivenUp
        val offers = product.subscriptionOfferDetails.orEmpty().filter { it.basePlanId == plan }
        // The trial when offered (Google Play lists only the offers this account may have)
        val offer = offers.firstOrNull { o -> o.pricingPhases.pricingPhaseList.firstOrNull()?.priceAmountMicros == 0L }
            ?: offers.firstOrNull { it.offerId == null } ?: return Bought.GivenUp
        val params = BillingFlowParams.newBuilder().setProductDetailsParamsList(
            listOf(BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(product).setOfferToken(offer.offerToken).build()),
        ).build()
        val answer = CompletableDeferred<Bought>().also { bought = it }
        val shown = withContext(Dispatchers.Main) {
            val on = activity() ?: return@withContext null
            client.launchBillingFlow(on, params)
        }
        if (shown?.responseCode != BillingClient.BillingResponseCode.OK) return Bought.GivenUp
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

    override fun device(): String {
        @SuppressLint("HardwareIds") // the free trial's, once per phone: what ANDROID_ID is for
        val id = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID).orEmpty()
        val digest = MessageDigest.getInstance("SHA-256").digest("${context.packageName}:$id".toByteArray())
        return digest.joinToString("") { "%02x".format(it) }
    }

    override suspend fun integrity(device: String): String? = runCatching {
        val manager = IntegrityManagerFactory.createStandard(context)
        val provider = manager.prepareIntegrityToken(
            PrepareIntegrityTokenRequest.builder().setCloudProjectNumber(CLOUD_PROJECT).build(),
        ).await()
        provider.request(StandardIntegrityTokenRequest.builder().setRequestHash(device).build()).await().token()
    }.getOrNull()

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
                val details = found.productDetailsList.firstOrNull().takeIf { result.responseCode == BillingClient.BillingResponseCode.OK }
                // Not on sale (the product or its base plans not active, this account or build not a tester's): why
                if (details == null) {
                    val missing = found.unfetchedProductList.joinToString { "${it.productId}: ${it.statusCode}" }
                    Log.w(TAG, "subscription $PRODUCT not offered: ${result.responseCode} ${result.debugMessage} [$missing]")
                }
                done.resume(details)
            }
        }
    }

    /** Connected to Google Play (once; false without it, e.g. an emulator without the store). */
    private suspend fun connected(): Boolean = connecting.withLock {
        if (client.isReady) return@withLock true
        suspendCancellableCoroutine { done ->
            client.startConnection(object : BillingClientStateListener {
                override fun onBillingSetupFinished(result: BillingResult) {
                    if (result.responseCode != BillingClient.BillingResponseCode.OK) {
                        Log.w(TAG, "Google Play Billing unavailable: ${result.responseCode} ${result.debugMessage}")
                    }
                    if (done.isActive) done.resume(result.responseCode == BillingClient.BillingResponseCode.OK)
                }

                override fun onBillingServiceDisconnected() {
                    if (done.isActive) done.resume(false)
                }
            })
        }
    }

    companion object {
        const val PRODUCT = "notosaurus" // the relay's RELAY_PLAY_PRODUCT
        private const val TAG = "Notosaurus"

        /** The Google Cloud project linked to the app in Play Console: the relay's, which
         * decodes Play Integrity's tokens. */
        const val CLOUD_PROJECT = 773198805942L

        /** Its base plans in Play Console, as offered: a month, a year (a month's credits each month). */
        val PLANS = listOf("monthly", "yearly")

        /** "P7D", "P1W", "P1M"… as days. */
        fun days(period: String): Int {
            val match = Regex("""^P(\d+)([DWM])$""").find(period) ?: return 0
            val (n, unit) = match.destructured
            return n.toInt() * when (unit) { "W" -> 7; "M" -> 30; else -> 1 }
        }
    }
}
