package app.notosaurus

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

/**
 * The app kept running while the AI works for it (a lesson made, a picture drawn, Relay.Busy).
 * Left in the background, Android soon caches the app and, since Android 15, cuts its network:
 * its call to the relay with it (INT-01: home or the screen off a minute during a careful lesson,
 * no card and "can't reach the Notosaurus service"). A short foreground service while at least
 * one call runs keeps the network: Android 14+ (no permission asked; about 3 minutes at most,
 * a lesson takes one or two). Its notification shows only where notifications are allowed.
 */
class Working(private val context: Context, private val text: (String) -> String) : Relay.Busy {
    private var calls = 0
    private var service: WorkingService? = null
    private var starting = false

    override fun begin() = synchronized(this) {
        calls++
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE || service != null || starting) return@synchronized
        try {
            context.startForegroundService(Intent(context, WorkingService::class.java))
            starting = true
        } catch (e: IllegalStateException) {
            // Begun in the background (ForegroundServiceStartNotAllowedException): not kept
        }
    }

    override fun end() = synchronized(this) {
        calls--
        if (calls == 0) service?.let { stopping(it) }
    }

    /** The service started (it is in the foreground now): false when no call runs any more. */
    internal fun started(started: WorkingService): Boolean = synchronized(this) {
        starting = false
        if (calls == 0) return@synchronized false
        service = started
        true
    }

    /** Ended by Android (its time is up): the calls still running go on unkept. */
    internal fun stopping(stopped: WorkingService) = synchronized(this) {
        if (service === stopped) service = null
        stopped.stop()
    }

    internal fun notification(): Notification {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, text("channel"), NotificationManager.IMPORTANCE_LOW))
        return Notification.Builder(context, CHANNEL)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(text("title"))
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val CHANNEL = "working"
        @SuppressLint("StaticFieldLeak") // the application's context, not an activity's
        internal var current: Working? = null // the app's, for its service
    }
}

/** Working's foreground service: nothing but being there (started on Android 14+ only). */
class WorkingService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val working = Working.current
        if (working == null) {
            stopSelf()
            return START_NOT_STICKY
        }
        // In the foreground first, always: a service started so and stopped before, Android kills the app
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(ID, working.notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_SHORT_SERVICE)
        } else {
            startForeground(ID, working.notification())
        }
        if (!working.started(this)) stop()
        return START_NOT_STICKY
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        Working.current?.stopping(this) ?: stop()
    }

    @Suppress("OVERRIDE_DEPRECATION")
    override fun onTimeout(startId: Int) {
        Working.current?.stopping(this) ?: stop()
    }

    internal fun stop() {
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    companion object {
        private const val ID = 1
    }
}
