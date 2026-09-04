package com.phygital.bot

import okhttp3.Dns
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.dnsoverhttps.DnsOverHttps
import java.net.InetAddress
import java.util.concurrent.TimeUnit

object NetworkClient {
    private const val BASE_URL = "https://whatsapp-bot-backend-142e.onrender.com"
    private val jsonType = "application/json; charset=utf-8".toMediaType()

    private val bootstrapClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }

    private val doh: Dns by lazy {
        DnsOverHttps.Builder()
            .client(bootstrapClient)
            .url("https://dns.google/dns-query".toHttpUrl())
            .bootstrapDnsHosts(
                InetAddress.getByName("8.8.8.8"),
                InetAddress.getByName("8.8.4.4")
            )
            .resolvePrivateAddresses(false)
            .resolvePublicAddresses(true)
            .build()
    }

    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .dns(doh)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(45, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .followRedirects(true)
            .followSslRedirects(true)
            .build()
    }

    fun request(method: String, path: String, body: String?, bearer: String?): String {
        val url = BASE_URL + path
        val requestBody = body?.toRequestBody(jsonType)
        val builder = Request.Builder()
            .url(url)
            .header("Accept", "application/json")
            .header("Cache-Control", "no-cache")
            .header("Pragma", "no-cache")
            .header("User-Agent", "Phygital-Bot-Android/${BuildConfig.VERSION_NAME}")
            .header("X-Phygital-App-Version", BuildConfig.VERSION_NAME)

        if (!bearer.isNullOrBlank()) builder.header("Authorization", "Bearer $bearer")

        when (method.uppercase()) {
            "GET" -> builder.get()
            "POST" -> builder.post(requestBody ?: ByteArray(0).toRequestBody(jsonType))
            "PUT" -> builder.put(requestBody ?: ByteArray(0).toRequestBody(jsonType))
            "DELETE" -> if (requestBody != null) builder.delete(requestBody) else builder.delete()
            else -> builder.method(method.uppercase(), requestBody)
        }

        client.newCall(builder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val compact = text.replace("\n", " ").replace("\r", " ").take(500)
                throw IllegalStateException(
                    "HTTP ${response.code} | URL=${response.request.url} | respuesta=$compact"
                )
            }
            return text
        }
    }

    fun uploadFile(
        path: String,
        bearer: String?,
        bytes: ByteArray,
        filename: String,
        contentType: String,
        fields: Map<String, String> = emptyMap(),
    ): String {
        val multipart = MultipartBody.Builder().setType(MultipartBody.FORM)
        fields.forEach { (key, value) -> multipart.addFormDataPart(key, value) }
        val mediaType = runCatching { contentType.toMediaType() }.getOrElse { "application/octet-stream".toMediaType() }
        multipart.addFormDataPart("file", filename, bytes.toRequestBody(mediaType))

        val builder = Request.Builder()
            .url(BASE_URL + path)
            .header("Accept", "application/json")
            .header("Cache-Control", "no-cache")
            .header("User-Agent", "Phygital-Bot-Android/${BuildConfig.VERSION_NAME}")
            .header("X-Phygital-App-Version", BuildConfig.VERSION_NAME)
            .post(multipart.build())
        if (!bearer.isNullOrBlank()) builder.header("Authorization", "Bearer $bearer")

        client.newCall(builder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val compact = text.replace("\n", " ").replace("\r", " ").take(500)
                throw IllegalStateException(
                    "HTTP ${response.code} | URL=${response.request.url} | respuesta=$compact"
                )
            }
            return text
        }
    }
}
