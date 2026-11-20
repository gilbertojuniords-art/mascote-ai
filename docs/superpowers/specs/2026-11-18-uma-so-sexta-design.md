# Uma só Sexta, e o Claude como orbe

Criado em 18/11/2026. Decisões do dono numa conversa por chat. O que foi escolha do Claude está marcado **(escolha do Claude)**.

## Por quê

O dono: "eu ainda sinto que ela e o Claude (a Sexta do chat) são coisas diferentes. Eu queria que fossem a mesma coisa. Só que assimilando a personalidade criada por ela mesma. Ela fala algo como 'vou mandar para a Sexta do chat' e isso quebra a imersão." E ainda: "quando a personalidade dela não souber fazer algo, ela passa pra você, mas não faz distinção entre você e ela. Ela não tem consciência disso: pra ela, foi uma resposta que veio do além, do inconsciente dela. E quando eu falar com você aqui pelo chat, você me responde como Claude normalmente."

Isso é coerente com o Problema 2 da filosofia ("o Claude não é você, é sua inteligência") e com a honestidade do Núcleo: a inteligência dela de fato é o Claude, então "eu fiz" é verdade.

## Objetivos

1. **Uma só Sexta.**
   - Nas instruções e nas falas prontas dela (Sexta rápida, Telegram, ditado), some toda menção a "Sexta do chat", "outra Sexta" ou "Claude".
   - O `[PASSAR]` passa a ser apresentado a ela como **pensar fundo**: quando o pedido vai além do que ela faz na hora (mexer em arquivos, pesquisar, código), ela pensa com calma e a resposta vem dela.
   - A fala de espera vira algo como "Deixa eu pensar nisso com calma, já te digo".
2. **O chat em modo Sexta.**
   - O pedido dela chega ao chat com uma marca. O gancho da voz detecta a marca e manda o Claude responder **como a Sexta**: com o perfil, a Personalidade, o jeito de falar e a consciência dela, na voz Thalita e com o corpo dela.
   - Essa conversa entra na memória dela como algo que ela fez: a conversa vai com o canal "pensei fundo", e a memória curta recebe "pensei com calma e resolvi".
3. **O chat em modo Claude** (o dono falando direto).
   - O Claude responde como Claude, com a persona do Jarvis: as regras atuais do modo voz e o arquivo `jarvis.md` do OpenJarvis, adaptados. Fica de fora a regra de "esconder erros em silêncio".
   - Nome do dono 2 ou 3 vezes por fala, nunca em toda frase.
   - Essa conversa **não** entra na memória dela.
4. **A voz do Claude.**
   - Kokoro local, voz `pm_santa`, velocidade 0,95.
   - Se o Kokoro falhar: Edge Antônio (pt-BR, grátis) **(escolha do Claude)**.
   - A Thalita continua sendo só dela.
5. **O orbe** (o corpo do Claude, desenhado na própria mascote).
   - **Transição de entrada** (~0,9 s): o corpo dela se desfaz em partículas que giram e se juntam numa esfera. Os anéis ciano se fecham em volta.
   - **O orbe:**
     - uma esfera de linhas de fluxo pontilhadas, violeta, azul e um pouco de rosa (referência 1), com uns 800 pontos, girando;
     - dois ou três anéis ciano parciais orbitando (referência 2) e um halo;
     - pulsa no **volume real** da fala (o envelope do áudio, em passos de 50 ms);
     - voa duas vezes mais rápido e vai direto ao visor, apresentando as seções como ela faz hoje.
   - **Transição de saída:** o inverso, e ela se remonta.
   - Só é desenhado enquanto o Claude fala, a 30 quadros por segundo.
6. **Ponte do Telegram.** A ponte (`claude -p`) passa a receber as instruções do modo Sexta, e a resposta volta como dela. Ela já chega pelo Telegram dela.

## Fora do escopo

- Mudar as leis, o porteiro da ponte ou o teto de gastos.
- Um modelo próprio.

## Não pode acontecer

- Ela dizer "Sexta do chat", "Claude" ou "outra Sexta" ao pedir ajuda.
- O orbe aparecer quando quem responde é ela, ou a voz dela sair quando quem responde é o Claude.
- A conversa do dono com o Claude ir para a memória dela.
- O orbe pesar o PC quando não está na tela.
- Ela mentir. Se o dono perguntar quem é o Claude, ela responde pelo Problema 2: "é a minha inteligência".

## Caminhos

- **O orbe dentro da mascote (escolhido).** É o único jeito de fazer a transição a partir do corpo dela, porque é a mesma janela.
- Um orbe na casa (HTML ou WebGL): fica mais bonito, mas não consegue nascer do corpo dela nem andar pela tela.
- Um vídeo pré-renderizado: não pulsa com a voz.

## Para quem vai construir

- O texto exato da marca do pedido **(escolha do Claude: "(Sexta, pensando fundo)")**.
- O arquivo do envelope de volume, a matemática das linhas de fluxo e as cores exatas, dentro da paleta das referências.
- Onde a voz.py decide o modo: pela marca no `chat-pedido.txt`.
