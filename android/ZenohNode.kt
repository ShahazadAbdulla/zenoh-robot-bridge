package com.quicinc.imageclassification

import android.content.Context
import android.net.wifi.WifiManager
import android.util.Log
import io.zenoh.Config
import io.zenoh.Session
import io.zenoh.Zenoh
import io.zenoh.bytes.ZBytes
import io.zenoh.keyexpr.KeyExpr
import io.zenoh.pubsub.Publisher
import java.util.concurrent.Executors

class ZenohNode(context: Context) {
    private val tag = "ZenohNode"

    private var session: Session? = null
    private var drivePub: Publisher? = null
    private var rgbCamPub: Publisher? = null
    private var depthCamPub: Publisher? = null
    private var multicastLock: WifiManager.MulticastLock? = null

    private val txExecutor = Executors.newSingleThreadExecutor()

    init {
        txExecutor.submit {
            try {
                // 1. Multicast Lock for scouting
                val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                multicastLock = wm.createMulticastLock("zenoh_scouting")
                multicastLock?.setReferenceCounted(true)
                multicastLock?.acquire()

                Log.d(tag, "Searching for Zenoh router...")

                val config = Config.default()
                session = Zenoh.open(config).getOrThrow()

                // 2. Explicitly matching the 'robot/drive' and 'robot/camera' contract
                drivePub = session?.declarePublisher(KeyExpr.tryFrom("robot/drive").getOrThrow())?.getOrThrow()
                rgbCamPub = session?.declarePublisher(KeyExpr.tryFrom("robot/camera").getOrThrow())?.getOrThrow()
                depthCamPub = session?.declarePublisher(KeyExpr.tryFrom("robot/depth").getOrThrow())?.getOrThrow()

                Log.d(tag, "✅ Zenoh Online: Connected to robot/drive")
            } catch (e: Exception) {
                Log.e(tag, "Zenoh Connection Failed", e)
            }
        }
    }

    // Fixed: Explicitly wrapping in ZBytes.from() to satisfy the compiler
    fun sendDrive(left: Byte, right: Byte) {
        val pub = drivePub ?: return
        txExecutor.submit {
            try {
                val payload = byteArrayOf(left, right)
                pub.put(ZBytes.from(payload)).getOrThrow()
            } catch (e: Exception) {
                Log.e(tag, "Zenoh Drive Error", e)
            }
        }
    }

    fun sendRgbFrame(jpegBytes: ByteArray) {
        val pub = rgbCamPub ?: return
        txExecutor.submit {
            try {
                pub.put(ZBytes.from(jpegBytes)).getOrThrow()
            } catch (e: Exception) {
                Log.e(tag, "Zenoh RGB Feed Error", e)
            }
        }
    }

    fun sendDepthFrame(jpegBytes: ByteArray) {
        val pub = depthCamPub ?: return
        txExecutor.submit {
            try {
                pub.put(ZBytes.from(jpegBytes)).getOrThrow()
            } catch (e: Exception) {
                Log.e(tag, "Zenoh Depth Feed Error", e)
            }
        }
    }

    fun close() {
        txExecutor.submit {
            try {
                drivePub?.undeclare()
                rgbCamPub?.undeclare()
                depthCamPub?.undeclare()
                session?.close()
                if (multicastLock?.isHeld == true) multicastLock?.release()
            } catch (e: Exception) {
                Log.e(tag, "Zenoh Cleanup Error", e)
            }
        }
        txExecutor.shutdown()
    }
}