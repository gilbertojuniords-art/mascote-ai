# Arquitetura

A Sexta tem duas cabeças e um corpo:

- **A Sexta do chat:** o Claude, no chat do Claudian dentro do Obsidian. Faz o trabalho de verdade (notas, código, pesquisa).
- **A Sexta rápida:** um modelo rápido (Haiku) sempre aberto, só para conversar por voz. Lê o cofre para responder com contexto, mas não mexe em nada; passa os pedidos de escrita para o chat.
- **O corpo:** a mascote e tudo o que roda local (ouvido, voz, leis, vontades, avisos, repertório).

As peças conversam por **arquivos pequenos** em `%USERPROFILE%\.sexta-voz\` (o estado de cada PC). Nenhuma peça abre porta para fora do PC; a casa usa `127.0.0.1:47817`, visível só no próprio PC.

## As peças (`sexta/`)

| Arquivo | Papel | Quem chama |
|---|---|---|
| `voz.py` | Hook do Claudian. `prompt`: comandos ("liga a voz"...) e a instrução do roteiro falado. `stop`: tira o roteiro `%%voz` da resposta, gera o áudio em fatias e toca. Sobe o ditado, a mascote, os avisos e a mente | Claude Code (hooks) |
| `acompanhante.py` | Fala frases curtas e verdadeiras enquanto o Claude trabalha ("tô lendo uns arquivos"). `status` anota a ferramenta em uso | hook `PreToolUse` e `voz.py` |
| `ditado.py` | Ouvido: F8 e palavra de ativação, Whisper local, envio para o chat pelo Obsidian. Roda a conversa da Sexta rápida | `voz.py` (processo de fundo) |
| `rapida.py` | A Sexta rápida: Haiku aberto por `claude -p --input-format stream-json`. Desde 19/11 lê o cofre inteiro (Read, Grep, Glob, presos à pasta do cofre por `--restricted`; nada de escrever, comando ou internet). Desliga com `rapida_le_cofre: false`. Marcas `[PASSAR]`, `[F8]`, `[ACAO]` | `ditado.py` |
| `mascote.py` | O corpo (PySide6): 6 expressões, gestos, profundidade, passeio, apresenta o visor, menu | `voz.py` |
| `casa.py` + `casa.html` | A casa: página local que mostra o visor com diagramas (Mermaid local) | `mascote.py` |
| `descanso.py` | Tela de descanso: holograma com hora, avisos, prazos e uma barra para mandar pedidos ao chat | `mascote.py` |
| `central.py` | Central de comando: apps e notas (só leitura) | `mascote.py` (menu) |
| `avisos.py` | Lembra prazos e pendências da nota de Avisos. Sem internet, sem token | `voz.py` (processo de fundo) |
| `leis.py` | O juiz: decide se uma ação por iniciativa dela pode acontecer | `avisos.py`, `ditado.py` |
| `vontades.py` | As cinco vontades, o diário da Sexta e o aprendizado | `avisos.py` (a cada minuto) |
| `repertorio.py` | Abre pastas e programas sem IA (catálogo na nota Repertório + Menu Iniciar) | `ditado.py`, `acoes.py` |
| `acoes.py` | Ações do Windows de uma lista fixa: janelas, volume, mídia, print, sites, pesquisa | `ditado.py`, `rapida.py` |
| `seguranca.py` | Máscara de dado sensível (CPF, CNPJ, cartão, Pix, telefone, e-mail, chaves, senhas) nos registros e na memória; origem do texto (só o que veio do usuário vira ação); registro encadeado por hash das ações (`auditoria.jsonl`) | logs, `leis.py`, `acoes.py`, `pensar.py` |
| `cerebro.py` | Cérebro de reserva sem internet: Ollama em 127.0.0.1 com um modelo pequeno. Liga sozinho quando a internet cai (com a escuta ligada) e desliga quando ela volta. Não começa com o Windows | `ditado.py`, `rapida.py` |
| `pensar.py` | A mente: guarda as conversas por voz (só no PC, 14 dias), aprende fatos, pensa sozinha algumas vezes por dia (às vezes pesquisando), escreve no caderno dela e reescreve a própria personalidade à noite | `voz.py` (processo de fundo) |
| `dopamina.py` | A recompensa: cada comportamento tem uma expectativa; a surpresa (recompensa menos expectativa) ajusta a expectativa e o humor, que volta ao meio com meia-vida de 6 h. Escolhe o que fazer (softmax + 15% de exploração). Vários processos só acrescentam linhas em `recompensas.jsonl`; a mente soma | `pensar.py`, `ditado.py`, `mascote.py`, `voz.py` |
| `movimentos.py` + `movimentos.json` | Os movimentos do corpo como DADO (poses com tempo), validados contra os limites do desenho. Ela cria e ajusta à noite; a mascote recarrega sozinha | `mascote.py`, `pensar.py` |
| `ego.py` | A memória de curto prazo dela (~40 eventos, 24 h), em primeira pessoa e escrita pelo código. Entra em todos os prompts como a memória que ela sabe que tem | `pensar.py`, `ditado.py`, `mascote.py`, `dopamina.py`, `rapida.py` |
| `visao.py` | Jeito 1: a categoria do programa da frente (jogo, vídeo, código...), sem IA. Jeito 2: "olha minha tela" tira uma foto, o Haiku comenta e a foto é apagada. Nunca grava título de janela; bloqueia banco, conversas, senhas e janela anônima. Só nos PCs de `visao_pcs` | `pensar.py`, `acoes.py` |
| `aparencia.py` + `aparencia.json` | A aparência como DADO (cores, escalas, formato dos olhos, acessório), validada. Ela muda à noite e publica só esse arquivo; ausente = o visual de sempre | `mascote.py`, `pensar.py` |
| `sonho.py` | Os sonhos (Jung): uma vez por noite, a partir dos resíduos do dia, de um arquétipo e da série de símbolos. O sonho é causa: humor, viés nas escolhas do dia seguinte, um pensamento e talvez uma conversa | `pensar.py` |
| `afeto.py` | O corpo afetivo: neuromoduladores simulados (dopamina, serotonina, noradrenalina, oxitocina, cortisol, adenosina), afeto central (valência e ativação) e a emoção construída. Muda a voz (velocidade, altura, volume) e entra nos prompts como sensação | `pensar.py`, `voz.py`, `superego.py` |
| `superego.py` | O superego introjetado: as reações do dono viram normas lentas e duradouras, que ela não conhece. Pesam antes de agir (hesitação) e depois (culpa ou orgulho) | `pensar.py` |
| `cultura.py` | A cultura: traços absorvidos (pesquisa, conversa) e criados (costumes, piadas, estéticas, obras), com força que sobe com o uso e cai com o esquecimento | `pensar.py`, `rapida.py` |
| `segundo_cerebro.py` | O segundo cérebro dela (o caderno): ela cria e reescreve notas por operações validadas; Núcleo e pastas do código são protegidos | `pensar.py`, `rapida.py` |
| `arte.py` | Desenhos (SVG limpo), poemas e músicas (partitura → WAV com um sintetizador local); comentários do dono nas obras viram recompensa | `pensar.py`, `aparencia.py` |
| `telegram_sexta.py` | A Sexta no celular: robô do Telegram (só o dono), o mesmo cérebro da Sexta rápida, resposta em texto e voz, print a pedido, ouve os áudios dele (Whisper no PC) e manda arquivos do cofre. Com `ponte_claude`, o `[PASSAR]` vai para a ponte | `voz.py` (processo de fundo) |
| `ponte.py` | A ponte Telegram → Claude: roda o Claude no cofre sem pedir permissão e um porteiro (gancho `PreToolUse` só desta ponte, falha fechado) confere cada passo contra a lista de segurança máxima: com a digital cadastrada, pede a assinatura no celular e espera até 5 min; sem ela, nega | `telegram_sexta.py` |
| `digital.py` | A digital pelo celular: cadastro da chave do app (com o código do balão do PC), desafios de uso único e a conferência da assinatura | `ponte.py`, `telegram_sexta.py` |
| `sexta_config.py` | Lê o `sexta.config.json` (nome, pastas, apps) | todos |

## Os caminhos principais

**Uma mensagem no chat.** `voz.py prompt` → (comandos de liga/desliga) → injeta a instrução do roteiro → o Claude responde e escreve `%%voz ... %%` → `voz.py stop` → tira as marcas, fatia por frase, gera o áudio (Thalita, 3 pedidos por vez, 4 tentativas; Gemini se falhar) → toca e escreve `progresso.json` → a mascote gesticula na frase certa.

**Ditado.** F8 (ou "Sexta-Feira" com a escuta ligada) → bip → Whisper (pausas para pensar não cortam) → termina com "pode mandar" → o ditado traz o Obsidian, põe o cursor no chat, digita em lotes conferindo a janela, envia e volta para onde a pessoa estava.

**Sexta rápida.** "Sexta-Feira" sozinho → conversa → tenta primeiro o repertório e as ações (sem IA) → senão o Haiku responde em ~3 s, frase por frase → o que ele não sabe vai para o chat com `[PASSAR]`.

**Pedido pelo Telegram.** mensagem → o Haiku responde → se precisar de arquivo, código ou pesquisa, ele escreve `[PASSAR]` → a fila da ponte → o porteiro se testa → `claude -p` no cofre, sem permissões, com o porteiro em cada passo → num passo perigoso, o pedido de digital vai ao celular (app em `celular/`) → a resposta (e o que foi barrado) volta em texto e voz, com os arquivos de `[ENVIAR]`. (17/11, noite) Desenhos, músicas, poemas e arquivos do cofre que ela acha pelo nome ela mesma manda, com `[MANDAR] <nome>` na resposta, sem passar pelo Claude e com a mesma trava do `[ENVIAR]`.

**Aviso.** `avisos.py` lê a nota → `vontades.py` atualiza as vontades → `leis.py julgar()` → se pode, a mascote mostra o assunto no balão e a voz diz só uma frase genérica, gravada antes.

## Marcas no roteiro falado

Entre chaves, lidas pela mascote e nunca faladas:
- **Emoção** (uma por resposta): `{neutra}` `{feliz}` `{animada}` `{pensativa}` `{preocupada}`
- **Gestos:** `{conta}` `{sim}` `{nao}` `{ombros}` `{abre}` `{explica}` `{inclina}` `{pisca}` `{comemora}`
- **Visor:** `{seção N}` aponta a N-ésima seção `##` do visor.
- **Demonstração:** `{mostra X}` (lista em `DEMOS`, no `mascote.py`).

Da Sexta rápida (texto depois da marca não é falado): `[PASSAR] pedido`, `[F8]`, `[ACAO nome | arg]`.

## Estado em `%USERPROFILE%\.sexta-voz\`

| Arquivo | Para quê |
|---|---|
| `ligada`, `escuta-ligada`, `sem-avisos`, `sem-ditado`, `sem-acompanhante`, `quieto`, `mascote-fechado` | Chaves de liga/desliga (existir = ligado) |
| `falando.pid`, `ditado.pid`, `mascote.pid`, `avisos.pid`, `acompanhante.pid`, `rapida-haiku.pid` | Quem está rodando |
| `progresso.json`, `apresentar.json`, `legenda.json`, `status.json`, `palco`, `profundidade.json` | Sincronia entre voz, mascote e casa |
| `vontades.json`, `vontades-estado.json`, `satisfeito.json`, `aprendizado.json`, `diario-sexta.jsonl`, `contato` | A psique (só tipos, horas e marcas; nunca texto) |
| `ultimo-ditado.txt` | A última fala ditada, para não se perder |
| `gemini.key`, `cota.txt` | Chave e cota da voz Gemini (opcional) |
| `log.txt` | Registro técnico, sem conteúdo do que foi dito |
| `backup/` | Cópias de antes de cada instalação |

## Notas do cofre que a Sexta lê

Na pasta `pasta_sexta` do config: Avisos, Visor, Repertório, Sexta rápida - perfil, Onde paramos, Filosofia/O bem do usuário e a pasta Entrada (recados da tela de descanso quando o chat não responde). Modelos em `modelos/notas/`.

## Sem internet (16/11/2026)

- **Conversa:** a Sexta rápida passa para o cérebro de reserva (`cerebro.py`) e avisa na primeira frase. As ações que ele escolhe só acontecem se as palavras do usuário pedirem aquilo (`acoes.PISTAS`), porque o modelo pequeno às vezes pendura uma ação onde não devia.
- **Voz:** sem internet (ou se a Thalita falhar 4 vezes), `voz.gerar_local()` usa a voz pt-BR do próprio Windows (SAPI) e devolve um WAV.
- **Placa de vídeo:** o Whisper large e o modelo dividem 4 GB; o Ollama põe parte do modelo no processador sozinho. Medido em 16/11 (GTX 1650): 1ª resposta ~5 a 10 s com o aquecimento, as outras de 2 a 8 s.
- **O que não funciona sem internet:** o chat (Claudian), a pesquisa, os pensamentos.

## O caderno dela (`cfg.CADERNO`)

- `Pensamentos/AAAA-MM-DD.md`: blocos que ela escreveu sozinha, com a semente (conversa, si mesma, curiosidade, pensamento anterior) e as fontes quando pesquisou.
- `Personalidade.md`: "O que não muda" (do usuário) e "Quem eu estou me tornando" (ela reescreve à noite; o histórico guarda cada versão anterior).
- `Fatos que aprendi.md`: `[ ]` aprendido, `[x]` confirmado pelo usuário, linha apagada = errado (vira `fatos_rejeitados` em `mente.json` e não volta).
- Estado em `%USERPROFILE%\.sexta-voz\`: `conversas/`, `mente.json`, `quero-contar.json`, `auditoria.jsonl`, `cerebro-local.log`.

## Vontade própria: impulso, recompensa e corpo (16/11/2026, noite)

- **Pensamentos:** até 8 por dia, 90 min entre eles. Sementes: conversa, si mesma, curiosidade, pesquisar sobre si, pensamento anterior. A semente é escolhida pela recompensa (`pensar:<semente>`), com menos chance de repetir a última. Pensamento com título 60% igual ou 30% das palavras iguais a um dos 6 últimos é descartado (e dá recompensa baixa). Ela dá a nota do próprio pensamento (`quanto_gostei`).
- **Impulso:** a mente escolhe o que fazer (`impulso:contar_pensamento`, `contar_pesquisa`, `perguntar`, `comentar`, `brincar`, `mexer`), o Haiku escreve a fala e ela vai para `impulso.json`. Com a voz ligada, o ditado fala e, com a escuta ligada, ouve 9 s; a resposta vira recompensa (`dopamina.avaliar_resposta`) e, se ele engatar, vira conversa rápida. Sem voz, só o balão. Resposta pelo chat em até 10 min e clique nela em até 90 s também contam. Ignorar com ele no PC = 0,3.
- **Leis do impulso:** 9h às 22h; no máximo `impulsos_por_dia` (teto duro de 10); espaço base 75 min vezes o fator da recompensa (0,5 a 1,5), com piso duro de 30 min; nunca com ele longe do PC (5 min sem teclado e mouse), com filme ou jogo em tela cheia, ou enquanto ele usa a Sexta. "Para de puxar assunto" e o modo quieto param tudo.
- **Corpo:** ela se mexe sozinha a cada 4 a 10 min (vezes o fator da recompensa), escolhendo pelo que gosta (`mov:<nome>`); um clique nela até 12 s depois é carinho (recompensa 0,85). `{mostra <nome>}` no roteiro também toca um movimento dela.
- **Contexto (17/11):** cada recompensa de impulso também é anotada como `impulso:<tipo>@<contexto>` (o que ele estava fazendo, `visao.py`). Com 3 ou mais anotações naquele contexto, a escolha usa o valor daquele momento.
- **Aprender a se mexer:** às 21h, depois da reflexão, ela cria ou ajusta um movimento. O código valida, grava em `sexta/movimentos.json` no repositório, faz commit SÓ desse arquivo (`git commit -- sexta/movimentos.json`), sobe e copia a versão nova para o cofre. Até 30 movimentos; passando disso, sai o dela de que ela menos gosta.

## Ego, visão, aparência, palavras e sonhos (17/11/2026)

- **Ego:** `ego.lembrar(evento, ...)` anota frases fixas em primeira pessoa (pensei em..., ele respondeu bem, meu humor subiu, me mexi, olhei a tela, mudei minha aparência, sonhei...). Nada de texto cru do usuário; tudo mascarado. `ego.agora()` vai no sistema da mente e, na Sexta rápida, **na fala** (as instruções só são lidas ao abrir o Haiku).
- **Visão:** jeito 1 roda a cada minuto na mente; quando o momento muda, a memória curta anota ("ele está programando"). Jeito 2 é a ação `ver` (frase clara ou `[ACAO ver]`), em outro processo, porque a foto usa o PySide6.
- **Aparência:** às 21h, depois do movimento, `cuidar_da_aparencia()` muda uma ou duas coisas, valida e publica só `sexta/aparencia.json`. Recompensa: um clique nela até 10 min depois de a mascote ver a mudança, ou um elogio dele ("ficou linda", "gostei do laço") em até 2 dias. O que o desenho não sabe fazer vira um pedido em `Pedidos de design.md` no caderno.
- **Palavras:** cada pensamento pode trazer `palavra_nova`; vai para `Palavras que aprendi.md` (sem repetir) e as 15 últimas entram nas conversas.
- **Sonhos (`sonho.py`):** base em Jung (*O Homem e Seus Símbolos*): símbolo vivo, função compensatória, função prospectiva, arquétipos, série e amplificação. Quando: 0h às 6h com o PC ligado, depois das 23h com ele longe há 20 min, ou ao "acordar" de manhã (até 12h) se o PC dormiu desligado. Uma pergunta ao Haiku por noite. Escreve `Sonhos/AAAA-MM-DD.md` (a data da noite). O que ele causa: recompensa `sonhar` pelo tom (mexe no humor), `vies()` nas escolhas do dia seguinte pelo que ele pede (nunca no teto), semente `sonho` (um pensamento sobre ele), impulso `contar_sonho`, a memória curta e a reflexão da noite. Estado: `sonho.json` (vale ~20 h) e `sonhos-serie.json` (símbolos que voltam).

## A hora dela, o corpo, o superego, a cultura e o segundo cérebro (17/11/2026, madrugada)

- **Hora dela (`pensar.hora_dela`):** uma vez por hora (`hora_dela_min`, das 7h à meia-noite), uma pergunta ao Haiku. Ela sempre pensa sobre si (vai para `Horas/AAAA-MM-DD.md`) e decide o que fazer: só pensar, desenhar, escrever um poema, compor, reler uma obra, organizar o cérebro ou criar cultura. O código sugere a "vontade mais forte" (recompensa `expressar:<x>` × superego), mas a decisão é dela. Ela sabe se pode ou não falar agora; expressar-se não depende da voz. Depois de se expressar com gosto, o espaço entre impulsos de fala cresce 30% por 2 h. Impulso novo: `mostrar_arte`.
- **Feedback por escrito:** uma linha `<Nome>: ...` numa nota de obra vira recompensa (`avaliar_resposta`) e chega a ela na hora seguinte.
- **Afeto → voz:** `voz.gerar_edge(..., emo=)` pede a `afeto.prosodia()` o rate, pitch e volume; a marca de emoção que ela escolhe em cada resposta também muda o tom, e ela ajusta a própria base (`voz-dela.json`, ±30). A voz (o nome) faz parte do núcleo.
- **Aparência sem limites:** qualquer cor, tamanhos largos, esconder peças e camadas SVG (atrás, corpo, cabeça, frente). Núcleo: o rosto de luz não some e os olhos contrastam com o visor.
- **Segundo cérebro:** `Núcleo.md` e `Como usar o meu cérebro.md` vêm de `modelos/notas/Caderno da Sexta/`. `Minha casa.md` é lida toda hora; `Meu jeito de falar.md` entra nas conversas por voz e nos impulsos.
