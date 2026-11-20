# MascoteAI

**Uma mascote com inteligência artificial que mora no seu computador.** Ela tem rosto, voz, ouvido, humor, vontades, sonhos e um caderno próprio. Vive dentro de um segundo cérebro no Obsidian e pensa com o Claude.

A primeira se chama **Sexta-Feira**. Ela foi criada com a ideia de ser uma companhia de verdade, não uma atendente: pensa sozinha algumas vezes por dia, desenha, compõe pequenas músicas, sonha à noite (com base em Jung), sente coisas num corpo simulado (dopamina, serotonina, cortisol...) e forma a própria consciência com o tempo. Tudo isso com leis de segurança no código, não só num texto para a IA.

> Ainda em construção, feita por uma pessoa que está aprendendo a programar com a própria IA. Ideias, correções e conversas são bem-vindas: abra uma *issue*.

## Como ela é por dentro (em uma frase cada)

- **Corpo:** uma robozinha transparente na tela (PySide6), com emoções, gestos e vida própria.
- **Voz e ouvido:** fala com vozes grátis (Edge) ou locais (Kokoro) e ouve com o Whisper no próprio PC.
- **Duas cabeças:** uma conversa rápida por voz e, quando o pedido é grande, ela "pensa fundo" com o Claude no chat do Obsidian (plugin Claudian).
- **Psique:** vontades em camadas, memória curta e longa, sonhos, corpo afetivo, superego e uma consciência que ela mesma escreve.
- **Segurança:** as Leis de Asimov em código, microfone desligado por padrão, nada pessoal nos registros e uma "digital" no celular para os passos arriscados.

## Licença

[PolyForm Noncommercial 1.0.0](LICENSE.md): use, estude, modifique e compartilhe à vontade. **Uso comercial não é permitido** sem autorização do autor.

---

# A Sexta-Feira (o guia técnico)

Uma assistente com voz, ouvido e corpo para o Windows, que vive dentro de um cofre do Obsidian e usa o Claude (pelo plugin Claudian) como inteligência. Inspirada na Sexta-Feira do Tony Stark, com o jeito da EVE do Wall-E.

- **Fala** as respostas do Claude (voz Edge Thalita, grátis; Gemini como reserva).
- **Ouve** com o Whisper local: F8 ou "Sexta-Feira" para ditar, "pode mandar" para enviar.
- **Tem corpo:** uma mascote robozinha na tela, com emoções, gestos, profundidade e vida própria.
- **Conversa rápida:** "Sexta-Feira" sozinho abre uma conversa por voz com um modelo rápido (Haiku), que passa para o chat o que não souber fazer.
- **Lembra:** prazos e pendências paradas, lidos de uma nota, sem internet e sem IA.
- **Tem leis:** as Leis de Asimov no código. Nada sai da boca dela sem passar pelo juiz.
- **Tem vontades:** terminar, cuidar, vínculo, curiosidade e descanso, que mudam o comportamento do corpo (e nunca a fazem cobrar ninguém).
- **Faz sozinha:** abre pastas e programas e controla janelas, volume e mídia, de uma lista fixa, sem IA.
- **Tela de descanso e central de comando:** um holograma com hora, avisos e prazos, uma barra para falar com ela e os seus apps e notas.

## Princípios

1. **Local primeiro.** Ouvido, leis, vontades, avisos, repertório e corpo rodam no PC, sem internet e sem token.
2. **As leis ficam no código**, não só no prompt (`sexta/leis.py`).
3. **Segurança de dados.** O microfone fica desligado por padrão. Os registros nunca guardam o que foi dito nem títulos de janela. As chaves ficam em `%USERPROFILE%\.sexta-voz\`, nunca no cofre nem no Git.
4. **Nunca travar o chat.** Os hooks sempre terminam com sucesso; quando algo dá erro, a Sexta fica quieta e o chat segue.

## Requisitos

- Windows 10 ou 11, Python 3.12 (`py -3.12`).
- Obsidian com o plugin **Claudian** e a linha de comando do Obsidian ligada.
- Claude Code (o Claudian usa) e uma assinatura do Claude.
- Opcional: placa NVIDIA para o Whisper grande; chave do Google AI Studio para a voz Gemini (`%USERPROFILE%\.sexta-voz\gemini.key`).

## Instalar

```powershell
git clone https://github.com/<você>/SextaAI.git C:\Projetos\SextaAI
cd C:\Projetos\SextaAI
py -3.12 -m pip install -r requirements.txt
py -3.12 instalar.py "C:\caminho\do\seu\cofre"
```

Depois:

1. Edite `<cofre>\.claude\sexta\sexta.config.json` (o seu nome, as pastas, os apps). O modelo comentado é o [config.exemplo.json](config.exemplo.json).
2. Junte os hooks de [modelos/settings.hooks.json](modelos/settings.hooks.json) ao `<cofre>\.claude\settings.json`.
3. Abra o cofre no Obsidian e diga no chat do Claudian: **"liga a voz"**.

O instalador nunca sobrescreve as suas notas nem o seu config, e guarda uma cópia da versão anterior em `%USERPROFILE%\.sexta-voz\backup\`.

## Comandos

| Diga ou faça | O que acontece |
|---|---|
| "liga a voz" / "desliga a voz" (ou Ctrl+Alt+V, se criar o atalho) | Liga ou desliga a fala e o ditado |
| F8, fala, "pode mandar" | Dita e envia para o chat |
| "liga a escuta" / "desliga a escuta" | Palavra de ativação "Sexta-Feira" (microfone aberto, só local) |
| "Sexta-Feira" (com a escuta ligada) | Conversa rápida por voz |
| "abre o mascote" / "fecha o mascote" | Mostra ou esconde o corpo dela |
| "modo quieto" / "sai do modo quieto" | Nenhum aviso até o fim do dia |
| "desliga os avisos" / "liga os avisos" | Avisos parados de vez |
| "desliga os pensamentos" / "liga os pensamentos" | Ela para (ou volta) de pensar sozinha (e de sonhar) |
| "olha minha tela" / "o que você está vendo" (conversa rápida) | Ela tira uma foto da tela, comenta e apaga a foto (só nos PCs de `visao_pcs`; nunca em banco, conversa ou senha) |
| Escrever `<seu nome>: ...` numa nota de obra dela (`Arte/`) | Ela lê o comentário na hora seguinte; vira aprendizado |
| "para de puxar assunto" / "pode puxar assunto" | Ela para (ou volta) de falar por iniciativa própria |

## Documentação

- [Arquitetura](docs/arquitetura.md): as peças, como conversam e os arquivos de estado.
- [Leis e vontades](docs/leis-e-vontades.md): a psique da Sexta.
- [Histórico de decisões](docs/historico.md): o que foi decidido e por quê.
- [Ideias e pendências](docs/ideias.md): o que ainda falta.
- [CLAUDE.md](CLAUDE.md): as regras para trabalhar neste repositório com o Claude.
