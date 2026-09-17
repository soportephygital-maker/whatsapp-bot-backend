package com.phygital.bot

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import java.io.ByteArrayOutputStream

object WhatsAppMediaStoreFallback {
    data class CapturedImage(
        val bytes: ByteArray,
        val filename: String,
        val contentType: String,
        val source: String = "whatsapp_media_store",
    )

    private const val MAX_BYTES = 15 * 1024 * 1024
    private const val WINDOW_MS = 180_000L
    private const val RETRIES = 8
    private const val RETRY_DELAY_MS = 1_250L

    fun captureRecentIncomingImage(context: Context, notificationTime: Long): CapturedImage? {
        if (!hasImagePermission(context)) return null
        repeat(RETRIES) { attempt ->
            queryRecentIncomingImage(context, notificationTime)?.let { return it }
            if (attempt < RETRIES - 1) {
                try { Thread.sleep(RETRY_DELAY_MS) } catch (_: InterruptedException) { return null }
            }
        }
        return null
    }

    private fun queryRecentIncomingImage(context: Context, notificationTime: Long): CapturedImage? {
        val resolver = context.contentResolver
        val collection = MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        val projection = mutableListOf(
            MediaStore.Images.Media._ID,
            MediaStore.Images.Media.DISPLAY_NAME,
            MediaStore.Images.Media.MIME_TYPE,
            MediaStore.Images.Media.DATE_ADDED,
            MediaStore.Images.Media.DATE_MODIFIED,
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) projection.add(MediaStore.Images.Media.RELATIVE_PATH)

        val fromSeconds = ((notificationTime - WINDOW_MS).coerceAtLeast(0L)) / 1000L
        val nowSeconds = (System.currentTimeMillis() + WINDOW_MS) / 1000L
        val selection = "(${MediaStore.Images.Media.DATE_ADDED} BETWEEN ? AND ?) OR (${MediaStore.Images.Media.DATE_MODIFIED} BETWEEN ? AND ?)"
        val args = arrayOf(fromSeconds.toString(), nowSeconds.toString(), fromSeconds.toString(), nowSeconds.toString())
        val sort = "${MediaStore.Images.Media.DATE_ADDED} DESC, ${MediaStore.Images.Media.DATE_MODIFIED} DESC"

        return try {
            resolver.query(collection, projection.toTypedArray(), selection, args, sort)?.use { cursor ->
                val idIx = cursor.getColumnIndex(MediaStore.Images.Media._ID)
                val nameIx = cursor.getColumnIndex(MediaStore.Images.Media.DISPLAY_NAME)
                val mimeIx = cursor.getColumnIndex(MediaStore.Images.Media.MIME_TYPE)
                val pathIx = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) cursor.getColumnIndex(MediaStore.Images.Media.RELATIVE_PATH) else -1
                while (cursor.moveToNext()) {
                    val id = if (idIx >= 0) cursor.getLong(idIx) else continue
                    val name = if (nameIx >= 0) cursor.getString(nameIx).orEmpty() else "whatsapp-image.jpg"
                    val mime = if (mimeIx >= 0) cursor.getString(mimeIx).orEmpty() else "image/jpeg"
                    val relative = if (pathIx >= 0) cursor.getString(pathIx).orEmpty() else ""
                    if (!looksLikeWhatsAppImage(relative, name)) continue
                    val uri = Uri.withAppendedPath(collection, id.toString())
                    val bytes = readBytes(context, uri) ?: continue
                    return CapturedImage(bytes, name.ifBlank { "whatsapp-image.jpg" }, mime.ifBlank { "image/jpeg" })
                }
                null
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun looksLikeWhatsAppImage(relativePath: String, filename: String): Boolean {
        val path = relativePath.lowercase()
        val name = filename.lowercase()
        if (path.contains("whatsapp images") || path.contains("whatsapp/media") || path.contains("com.whatsapp") || path.contains("com.whatsapp.w4b")) return true
        return name.startsWith("img-") && name.contains("wa")
    }

    private fun readBytes(context: Context, uri: Uri): ByteArray? {
        return try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                val out = ByteArrayOutputStream()
                val buffer = ByteArray(32 * 1024)
                var total = 0
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) break
                    total += read
                    if (total > MAX_BYTES) return null
                    out.write(buffer, 0, read)
                }
                out.toByteArray().takeIf { it.isNotEmpty() }
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun hasImagePermission(context: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= 33) {
            context.checkSelfPermission(Manifest.permission.READ_MEDIA_IMAGES) == PackageManager.PERMISSION_GRANTED
        } else {
            context.checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED
        }
    }
}
