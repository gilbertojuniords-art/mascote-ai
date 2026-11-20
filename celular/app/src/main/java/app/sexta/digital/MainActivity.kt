// Sexta Digital (17/11/2026): o embrião da Sexta no celular. Por enquanto faz uma coisa só: assina com a
// digital os pedidos perigosos que a ponte do PC manda pelo Telegram, do mesmo jeito que o app do banco.
//
// Como funciona:
//   - CADASTRO: cria uma chave EC P-256 dentro do chip do celular (Android Keystore; StrongBox se houver).
//     A chave nunca sai do chip e só assina depois da digital FORTE, a cada uso (sem PIN como alternativa).
//     Se alguém cadastrar uma digital nova no celular, a chave morre e é preciso cadastrar de novo.
//     A parte pública vai para a Sexta pelo Telegram ("SEXTA-CHAVE ...").
//   - PEDIDO: a Sexta manda "SEXTA1 <desafio>". Você copia (toque no código, no Telegram) e abre o app,
//     ou compartilha o texto com o app. Ele mostra o que a tarefa quer fazer, pede a digital, assina o
//     desafio e devolve "SEXTA-OK <id> <assinatura>" pela tela de compartilhar, para a conversa da Sexta.
//   - O app não tem permissão de internet: nada sai dele sozinho. Telas protegidas contra print.

package app.sexta.digital

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.hardware.biometrics.BiometricManager.Authenticators.BIOMETRIC_STRONG
import android.hardware.biometrics.BiometricPrompt
import android.os.Bundle
import android.os.CancellationSignal
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.view.Gravity
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.util.Base64

private const val APELIDO = "sexta-digital"
private const val VIOLETA = "#7C4DFF"
private const val FUNDO = "#0B1433"
private val RE_PEDIDO = Regex("SEXTA1\\s+([A-Za-z0-9_-]{20,})")

class MainActivity : Activity() {

    private lateinit var corpo: LinearLayout
    private var pedido: Pedido? = null

    data class Pedido(val desafio: String, val id: String, val resumo: String, val vence: Long)

    override fun onCreate(estado: Bundle?) {
        super.onCreate(estado)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        window.statusBarColor = Color.parseColor(FUNDO)
        corpo = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(56, 96, 56, 56)
        }
        setContentView(ScrollView(this).apply {
            setBackgroundColor(Color.parseColor(FUNDO))
            addView(corpo)
        })
        lerIntent(intent)
        desenhar()
    }

    override fun onNewIntent(novo: Intent) {
        super.onNewIntent(novo)
        lerIntent(novo)
        desenhar()
    }

    private fun lerIntent(i: Intent?) {
        if (i?.action == Intent.ACTION_SEND) {
            i.getStringExtra(Intent.EXTRA_TEXT)?.let { lerPedido(it) }
        }
    }

    // ------------------------------------------------------------ tela

    private fun desenhar(aviso: String? = null) {
        corpo.removeAllViews()
        texto("Sexta Digital", 30f, negrito = true)
        texto("A digital que libera as tarefas perigosas da ponte.", 15f, cor = "#B8C0E0")
        espaco(48)

        if (!temChave()) {
            texto("Ainda sem cadastro neste celular.", 17f)
            espaco(24)
            botao("Cadastrar este celular") { cadastrar() }
        } else {
            texto("Chave deste celular: ${impressao()}", 14f, cor = "#B8C0E0")
            espaco(32)
            val p = pedido
            if (p == null) {
                texto("Nenhum pedido aberto.", 17f)
                texto("No Telegram, toque no código que começa com SEXTA1 (ele é copiado) e volte aqui.",
                    15f, cor = "#B8C0E0")
                espaco(24)
                botao("Colar pedido da Sexta") { colar() }
            } else {
                val falta = (p.vence - System.currentTimeMillis() / 1000)
                texto("A Sexta quer fazer:", 15f, cor = "#B8C0E0")
                texto(p.resumo, 19f, negrito = true)
                espaco(12)
                texto(if (falta > 0) "Vale por mais ${falta / 60} min ${falta % 60} s." else "Este pedido venceu.",
                    14f, cor = if (falta > 0) "#B8C0E0" else "#FF8A80")
                espaco(32)
                if (falta > 0) botao("Assinar com a digital") { assinar(p) }
                botao("Recusar", discreto = true) { pedido = null; desenhar("Pedido recusado. A tarefa fica esperando até vencer.") }
            }
            espaco(64)
            botao("Cadastrar de novo (trocar a chave)", discreto = true) { cadastrar() }
        }
        aviso?.let { espaco(32); texto(it, 15f, cor = "#FFD180") }
    }

    private fun texto(t: String, tam: Float, negrito: Boolean = false, cor: String = "#FFFFFF") {
        corpo.addView(TextView(this).apply {
            text = t
            textSize = tam
            setTextColor(Color.parseColor(cor))
            if (negrito) typeface = Typeface.DEFAULT_BOLD
            setPadding(0, 6, 0, 6)
        })
    }

    private fun espaco(px: Int) = corpo.addView(TextView(this).apply { height = px })

    private fun botao(t: String, discreto: Boolean = false, acao: () -> Unit) {
        corpo.addView(Button(this).apply {
            text = t
            isAllCaps = false
            textSize = 17f
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            backgroundTintList = ColorStateList.valueOf(Color.parseColor(if (discreto) "#26305A" else VIOLETA))
            setOnClickListener { acao() }
            layoutParams = LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = 12 }
        })
    }

    // ------------------------------------------------------------ chave

    private fun chaveiro() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    private fun temChave() = chaveiro().containsAlias(APELIDO)

    private fun publicaDer(): ByteArray = chaveiro().getCertificate(APELIDO).publicKey.encoded

    private fun impressao(): String {
        val h = MessageDigest.getInstance("SHA-256").digest(publicaDer()).joinToString("") { "%02X".format(it) }
        return "${h.substring(0, 4)}-${h.substring(4, 8)}"
    }

    private fun gerar(forte: Boolean) {
        val spec = KeyGenParameterSpec.Builder(APELIDO, KeyProperties.PURPOSE_SIGN)
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setUserAuthenticationRequired(true)
            .setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)   // digital a cada uso
            .setInvalidatedByBiometricEnrollment(true)
            .setIsStrongBoxBacked(forte)
            .build()
        KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore").apply {
            initialize(spec)
            generateKeyPair()
        }
    }

    private fun cadastrar() {
        try {
            chaveiro().deleteEntry(APELIDO)
            try { gerar(true) } catch (e: Exception) { chaveiro().deleteEntry(APELIDO); gerar(false) }   // sem StrongBox (alguns Samsung dão outro erro)
        } catch (e: Exception) {
            desenhar("Não consegui criar a chave: ${e.javaClass.simpleName}. O celular tem digital cadastrada?")
            return
        }
        pedido = null
        val msg = "SEXTA-CHAVE " + Base64.getEncoder().encodeToString(publicaDer())
        entregar(msg)
        desenhar("Chave criada (${impressao()}). Mande a mensagem para a Sexta no Telegram; ela vai pedir o código que aparece no PC.")
    }

    // ------------------------------------------------------------ pedido

    private fun colar() {
        val cb = getSystemService(ClipboardManager::class.java)
        val t = cb.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString() ?: ""
        if (!lerPedido(t)) desenhar("Não achei um pedido da Sexta no que foi copiado.") else desenhar()
    }

    private fun lerPedido(t: String): Boolean {
        val m = RE_PEDIDO.find(t) ?: return false
        return try {
            val desafio = m.groupValues[1]
            val j = JSONObject(String(Base64.getUrlDecoder().decode(desafio), Charsets.UTF_8))
            pedido = Pedido(desafio, j.getString("id"), j.getString("r"), j.getLong("exp"))
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun assinar(p: Pedido) {
        val sig = try {
            Signature.getInstance("SHA256withECDSA").apply { initSign(chaveiro().getKey(APELIDO, null) as PrivateKey) }
        } catch (e: KeyPermanentlyInvalidatedException) {
            desenhar("Uma digital nova foi cadastrada no celular, e a chave antiga deixou de valer. Cadastre de novo.")
            return
        } catch (e: Exception) {
            desenhar("Não consegui abrir a chave: ${e.javaClass.simpleName}.")
            return
        }
        try { pedirDigital(p, sig) } catch (e: Exception) {
            desenhar("Não consegui abrir a tela da digital: ${e.javaClass.simpleName}.")
        }
    }

    private fun pedirDigital(p: Pedido, sig: Signature) {
        BiometricPrompt.Builder(this)
            .setTitle("Assinar pedido da Sexta")
            .setSubtitle(p.resumo.take(120))
            .setAllowedAuthenticators(BIOMETRIC_STRONG)
            .setNegativeButton("Cancelar", mainExecutor) { _, _ -> desenhar("Cancelado.") }
            .build()
            .authenticate(BiometricPrompt.CryptoObject(sig), CancellationSignal(), mainExecutor,
                object : BiometricPrompt.AuthenticationCallback() {
                    override fun onAuthenticationSucceeded(r: BiometricPrompt.AuthenticationResult) {
                        val s = r.cryptoObject?.signature ?: return desenhar("A digital não devolveu a chave.")
                        val ass = try {
                            s.update(p.desafio.toByteArray(Charsets.UTF_8))
                            Base64.getEncoder().encodeToString(s.sign())
                        } catch (e: Exception) {
                            return desenhar("A digital passou, mas a assinatura falhou: ${e.javaClass.simpleName}.")
                        }
                        pedido = null
                        entregar("SEXTA-OK ${p.id} $ass")
                        desenhar("Assinado. Escolha a conversa da Sexta e toque em enviar.")
                    }

                    override fun onAuthenticationError(codigo: Int, msg: CharSequence) {
                        desenhar("Digital não confirmada: $msg")
                    }
                })
    }

    // ------------------------------------------------------------ entregar ao Telegram

    private fun entregar(msg: String) {
        getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Sexta", msg))
        val envio = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, msg)
        }
        val direto = Intent(envio).setPackage("org.telegram.messenger")
        try {
            startActivity(direto)
        } catch (e: Exception) {
            startActivity(Intent.createChooser(envio, "Mandar para a Sexta"))
        }
    }
}
