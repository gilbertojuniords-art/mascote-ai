# Sexta Digital (app do celular)

O embrião da Sexta no celular. Por enquanto faz uma coisa só: **assina com a digital** os passos perigosos que a ponte do PC quer fazer, do mesmo jeito que o app do banco. A conferência fica em `../sexta/digital.py`.

- Android 11 ou mais novo, com digital cadastrada no celular.
- **Sem permissão de internet** e sem nenhuma biblioteca extra. Nada sai do app sozinho: ele entrega a assinatura pela tela de compartilhar.
- A chave é EC P-256, criada dentro do chip do celular (StrongBox quando houver). Ela nunca sai de lá e só assina depois da digital forte, a cada uso. Cadastrou uma digital nova no celular? A chave deixa de valer e é preciso cadastrar de novo.

## Como usar

1. **Cadastro (uma vez):** abra o app, toque em "Cadastrar este celular" e mande a mensagem `SEXTA-CHAVE ...` para a Sexta no Telegram. O PC mostra um código no balão da mascote; mande esse código no Telegram. Só quem está na frente do PC vê o código.
2. **A cada pedido:** a Sexta manda o que a tarefa quer fazer e um código `SEXTA1 ...`. Toque no código (o Telegram copia), abra o app, toque em "Colar pedido da Sexta", confira e ponha a digital. O app abre o Telegram com a resposta `SEXTA-OK ...`: escolha a conversa da Sexta e envie. O pedido vale 5 minutos e só uma vez.

## Compilar

Precisa do JDK 17 e do Android SDK (plataforma 35). Sem o Android Studio:

```
set JAVA_HOME=<pasta do JDK 17>
set ANDROID_HOME=<pasta do Android SDK>
gradlew.bat assembleDebug
```

O APK sai em `app/build/outputs/apk/debug/app-debug.apk`. Para instalar, mande o arquivo para o celular e permita "instalar apps desconhecidos" só para o app que abrir o arquivo.

Se o antivírus inspecionar as conexões seguras (o Java não confia no certificado dele e o download falha com `PKIX path building failed`), use os certificados do Windows: `set JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStoreType=Windows-ROOT`.

**Atualizar o app:** a versão nova precisa ser assinada pela mesma chave de compilação (no modo debug, a do PC que compilou, em `~/.android/debug.keystore`). Compilou em outro PC? Desinstale a antiga e cadastre de novo.
