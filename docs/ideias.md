# Ideias e pendências

## Não testado ao vivo (precisa de microfone e da mascote aberta)

- Comemoração ao marcar `[x]`; "Sexta-Feira, prepara" depois de um aviso; um aviso de verdade passando pelo juiz.
- A Sexta falando das próprias sensações; a mascote mudando com as vontades (os pesos foram chutados).
- Tela cheia voltando com F8; fala preservada quando a resposta chega no meio do ditado.
- Tela de descanso e central de comando ao vivo; clique no reator do peito.

## Problemas abertos

- **Voz lenta:** a 1ª frase leva 4 a 12 s no uso real, contra ~1 s isolada. Suspeitas: concorrência com o Obsidian ou o Whisper na hora da fala, ou rede. Saídas: tocar o áudio enquanto chega (streaming) ou voz local.
- **Ditado caindo** com erros de placa de vídeo (`out of memory`, `invalid device ordinal`): investigar o que consome a placa se voltar.
- A Sexta rápida às vezes reescreve o pedido em terceira pessoa ao passar para o chat: deve usar as palavras da pessoa.

## Sem internet, hoje

- **Funciona:** ouvido e palavra de ativação, repertório e ações com frase clara, leis, vontades, diário, mascote e avisos (frases já gravadas).
- **Não funciona:** a voz (Thalita é pela internet), a conversa (o Haiku é Claude) e o chat.

## Próximas ideias (em ordem sugerida)

1. **Voz de reserva local:** Microsoft Maria (já vem no Windows, robótica) quando a Thalita falhar.
2. **Voz local melhor:** Kokoro ou Piper (grátis, no processador). Testar a qualidade antes de trocar.
3. **Cérebro plugável:** com internet, o Haiku; sem internet, um modelo local pequeno (Ollama + Qwen 2.5 3B, por exemplo). O repertório continua vindo antes de qualquer cérebro. Ollama fica em segundo plano: pede o ok do dono.
4. **Repertório que aprende:** quando a porta de ajuda resolve algo novo no Windows, o comando vira **proposta** de nova ação; o dono aprova e, da próxima vez, ela faz sozinha.
5. **Ações com risco e confirmação falada:** fechar programa, desligar o PC (ela repete o que entendeu e espera o "sim").
6. **Ego completo:** pesar vontade contra vontade e contra o momento.
7. **Memória das conversas da Sexta rápida** e **puxar conversa sozinha** (sempre pelo juiz, com limite). Decisão do dono.
8. **Vídeo → nota:** Whisper local transcreve, um cérebro resume, vai para o cofre.
9. **Andar em cima das janelas** e profundidade extrema rara (cliques passando através dela; nunca com jogo ou vídeo em tela cheia).
10. **Sexta no celular:** app próprio (PWA) falando com a API (paga e separada da assinatura) ou com o PC de casa.

## Pesquisa: o que torna uma voz agradável

Prosódia (o tom acompanha o sentido), pausas no lugar certo, ritmo variável, hesitações com moderação, respiração só se bem colocada, encaixe na conversa acima de velocidade, variedade de frases e timbre. As alavancas baratas estão em como o roteiro é escrito (`INSTRUCAO`) e no `rate`/`pitch` por frase.
