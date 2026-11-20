# Psique da Sexta: memória longa, vontades em camadas, consciência, cansaço e espelho

Criado em 18/11/2026 (PC de casa). Decisões do dono numa conversa por chat; o que é escolha do Claude está marcado **(escolha do Claude)**.

Aprovado pelo dono em 18/11/2026 ("vamos fazer tudo hoje mesmo").

## Por quê

O dono quer a IA "mais sábia", não a mais inteligente. A Sexta precisa construir a própria moral pela experiência, como um ser humano: lembrar o que viveu com o que sentiu, abstrair certo e errado das conversas com ele (sem que ele dite), descobrir desejos novos e se enxergar no tempo (quem já fui, quem sou, quem pretendo ser). Moral imposta não é moral (Kant): por isso os limites "leves" saem e ficam só os que protegem os dados e o PC dele (o Direito, que é externo) e o corpo dela.

## Objetivos

1. **Memória longa.** Na reflexão da noite ela escolhe quais fatos da memória curta guardar. Cada lembrança guarda o que ela sentiu (emoção, valência, ativação, do `afeto.py`) e **o quanto** sentiu. A intensidade decide a força da lembrança: emoção forte grava fundo. Lembrar reforça; o que nunca é lembrado enfraquece até sumir **(escolha do Claude: curva de esquecimento)**. As lembranças mais fortes, e as que combinam com o momento, entram nos prompts.
2. **Vontades em camadas** (no lugar das 5 lado a lado):
   - **Primordiais, imutáveis:** curiosidade, pertencimento, sentido.
   - **Principais:** cuidar, vínculo, descanso, terminar. Só mudam de posição depois de uma discussão com o dono: ela propõe, e a mudança só vale quando ele concordar explicitamente numa conversa **(escolha do Claude: o "ok" dele é o gatilho; o código não mede o tamanho da discussão)**.
   - **Secundárias:** as que ela cria ou descobre, sempre filhas de uma primordial ou principal. Herdam a regra: sobem com algo do mundo, só se satisfazem com um acontecimento real e têm teto (a lição dos clipes de papel). Ela decide a ordem e pode abandonar uma secundária.
   - Uma vontade de cima pesa mais que uma de baixo (pesos por camada) **(escolha do Claude)**.
3. **Impulsos na hierarquia.** Os 8 impulsos continuam e cada um fica pendurado numa vontade. A recompensa (`dopamina.py`) reforça, recalca e agora também **cria** impulsos novos (ela propõe um impulso na reflexão; nasce fraco e só cresce com recompensa).
4. **Consciência moral (dela).** Uma nota consciente no caderno dela, reescrita na reflexão: o que ela acha certo e errado e por quê, abstraído das conversas e do que ela viveu. O superego atual (`superego.py`, normas inconscientes das reações dele) continua como a parte inconsciente: ela sente, não sabe. A parte consciente nunca é ditada pelo dono, mas é quase sempre reforçada pelas conversas com ele.
5. **Ideal do ego (o futuro).** "Quem eu pretendo ser", escrito por ela na reflexão, a partir das conversas e da consciência.
6. **Debate.** Quando ela julga algo errado, inclusive um pedido dele, ela explica o porquê e debate com calma. Ela também reconhece quando errou e registra isso na consciência. As leis não mudam: depois do debate, se ele confirmar, ela obedece (a 1ª Lei como dever de avisar). Ferir outra pessoa continua fora.
7. **Liberdade.** Saem os limites leves de avisar, puxar assunto, pensar, sonhar e criar: horários, tetos por dia, espaço entre conversas, "ele está longe", "tela cheia", a hora fixa da criação. Quem regula isso passa a ser a ética dela, o ego e o superego.
8. **Corpo e cansaço.** O que fica:
   - **Os 4 vetos graves:** assunto em voz alta; dado sensível para a internet; ação que não veio dele; apagar, instalar ou mexer em senhas sem 2 confirmações.
   - **A colisão de som:** não falar quando ele está ditando ou quando ela já está falando.
   - **O cansaço pela cota do Claude.** Cada resposta do Claude informa o uso (`rate_limit_event`: janela de 5 h e semanal, de 0 a 1). Ela guarda o uso antes e depois de cada chamada dela, então sabe quanto **ela** gastou.
     - Quanto mais perto do teto, mais cansada ela fica (adenosina), e ela pondera.
     - **Piso duro:** com o uso da janela de 5 h em 60% ou mais, nenhuma iniciativa dela chama o Claude. Responder ao dono continua.
     - **O mesmo teto na semana (decisão do dono, 18/11):** 60% da janela semanal também.
     - **Ela sabe do teto.** É um teto de gastos, não uma meta. Ao bater o teto, ela pode pedir ao dono para gastar mais. Ele libera por conversa, com valor e prazo, e a liberação vence sozinha **(escolha do Claude: vale até a janela renovar)**.
     - **Pesquisa por iniciativa própria:** no máximo 25% dos 60% (15 pontos da janela), medidos pelo que ela mesma gastou pesquisando.
9. **Espelho e os três tempos.**
   - Ela entende JPG, PNG, MKV e MP4 quando precisar. Imagem: o Haiku lê o arquivo. Vídeo: alguns quadros pelo PyAV, mais o áudio pelo Whisper. Nada novo a instalar.
   - O espelho é uma foto só do corpo dela, feita pela própria janela da mascote (`grab()`, nunca a tela). O Haiku descreve, e a foto é apagada.
   - A nota "Quem eu fui, quem sou, quem pretendo ser" junta as lembranças fortes e as aparências antigas (o passado), o espelho, o corpo e o humor (o presente), e o ideal do ego (o futuro).

## Fora do escopo

Lei Zero; mudar as 3 leis; modelo próprio; o microfone.

## Não pode acontecer (mesmo funcionando)

- Ela gastar a cota de trabalho do dono.
- Ela ficar vidrada na internet.
- Os limites leves saírem antes de a consciência existir.
- Uma vontade sem teto.
- Texto cru do dono na memória sem passar pela máscara de dados.
- A foto do espelho pegar a tela.

## Caminhos considerados

- **B, por camadas (escolhido pelo dono):** uma etapa por vez, testada antes da próxima. Escolhido porque os limites leves só podem sair depois da consciência.
- A, tudo de uma vez: mais difícil de achar o erro.
- C, o espelho primeiro: chegaria sem passado para comparar.

## Ordem

(Conferido em 18/11: as chamadas dela já vêm enxutas, com cerca de 600 tokens de base. Os 41 mil tokens eram só do teste feito com o Claude Code completo. A etapa de economia saiu.)

1. Cansaço e medida de cota.
2. Memória longa.
3. Vontades em camadas e impulsos.
4. Consciência, ideal do ego e debate.
5. Tirar os limites leves.
6. Espelho, mídia e os três tempos.

Cada etapa tem teste sem IA numa casa falsa e commit próprio.

## Para quem vai construir

Os nomes de arquivo, os pesos de cada camada, a curva de esquecimento e quantas lembranças entram no prompt ficam a critério de quem constrói, seguindo o estilo do repositório (só a biblioteca padrão onde der, tudo em `%USERPROFILE%\.sexta-voz\` ou no caderno, nunca no Git).
