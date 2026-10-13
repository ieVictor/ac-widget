# Widget Omarchy

## Instalação e operação

O plugin usa a API local do Omarchy/Quickshell desta instalação. Não altera
/usr/share/omarchy e não cria um servidor de controle.

```bash
cd ~/development/midea-desktop
uv sync --dev
./scripts/install-omarchy.sh             # Instalar
./scripts/install-omarchy.sh --replace   # Atualizar, preservando backup
omarchy restart shell                   # Se o singleton Backend.qml mudou
omarchy plugin disable victor.midea     # Desabilitar, sem apagar as chaves
```

Os backups ficam em `~/.local/state/midea-desktop/backups/`. A cópia inicial de
shell.json permite recuperar a configuração anterior. O instalador grava o
caminho absoluto do executável .venv no manifesto instalado, nunca credenciais.

O indicador mostra desligado, alvo de temperatura ou ausência de estado recente.
Clique abre o painel; clique do meio só consulta. Ligar/desligar é imediato e
explícito. Temperatura/modo exigem Aplicar ajustes e não ligam o aparelho.
Escape fecha. Atualizar só lê. Leituras periódicas não descartam um rascunho
editado; a confirmação de uma ação própria sincroniza os rascunhos.

## Segurança e comportamento degradado

- Não há login cloud na operação do widget.
- JSON e estado QML são listas permitidas, sem IDs, IP, serial, token ou key.
- stderr da biblioteca não é encaminhado ao log compartilhado do shell.
- Um singleton compartilha fila/estado/polling entre monitores.
- Falha, estado antigo ou capacidades ausentes bloqueiam controles.
- Erro de uma escrita mantém o último estado confirmado e orienta conferir o
  aparelho antes de repetir. A próxima consulta é somente leitura.
- Nenhuma escrita automática, inclusive na instalação e ao reiniciar o shell.
- A biblioteca ainda pode fazer retransmissões internas do protocolo.
- Modos são os anunciados pelo módulo. HEAT não prova aquecimento físico.
- Não controlar simultaneamente por outro processo CLI/app: não há lock global.

Diagnóstico seguro da instância real:

```bash
omarchy-shell midea-widget status
omarchy-shell midea-widget refresh
```

O shell só procura plugins panel nas chamadas `shell call`; este plugin é
bar-widget. Por isso o diagnóstico tem um alvo IPC próprio, com apenas leitura.

## Autoridade visual

A interface estende o shell existente, sem nova identidade visual.
Cores vêm de Color.popups/Color.accent; fontes, escala e espaçamento de Style.
Panel, KeyboardPanel, WidgetButton, Button e Dropdown são os componentes nativos.
O painel é ajustado aos limites do monitor e tem rolagem caso o conteúdo não caiba.
Não há fontes, sombras ou animações decorativas próprias. A única cor semântica
adicional é o verde do AI solicitado pelo usuário, escolhido com contraste sobre
Color.popups.background.

## IA / economia inteligente

O aparelho anunciou IECO e número 8: ECOMaster, distinto do ECO convencional.
O botão AI alterna essa propriedade, sem enviar um SetState de temperatura/modo
ou ligar o aparelho. O comando de propriedades também inclui buzzer, como exigido
pela biblioteca. Ativação limitada a ar ligado em Refrigerar; desativação de uma
IA ativa permanece disponível.

A consulta precisa receber IECO numa PropertiesResponse nova. Ausência vira
estado desconhecido, nunca o default false. A confirmação após escrever exige
outra consulta nova dessa propriedade e correspondência do valor. Escritas não
são repetidas automaticamente. iECO de outros tipos é rotulado iECO, não ECOMaster.

O usuário relatou que o widget básico funcionou. Ativação real da IA ainda não
foi feita pelo agente; testes de escrita usam exclusivamente a fixture isolada.

## Visor LED

A linha Visor LED mostra o estado reportado pelo módulo. O quadrado LED alterna
ligar/desligar; segue o padrão do AI, com título/estado à direita. O nome acessível
continua explicitando Ligar/Desligar visor LED. Esse é o sinal de habilitação do visor, não um sensor de luminosidade:
o aparelho pode estar desligado mesmo que o visor esteja configurado como ativado.

A API recebe um estado desejado. Consulta antes e não envia nada se esse estado
já estiver satisfeito. Caso contrário, usa ToggleDisplayCommand com apenas uma
tentativa LAN (retries=1), sem SetState e sem retransmissão automática. Ignora
timeout de ACK apenas para consultar e verificar o resultado; cancelamento não
prossegue. Exige nova resposta de estado com display_on booleano e correspondente.

Sem capacidades confirmadas ou leitura nova do visor, o botão fica desabilitado.
Falha depois do envio não garante ausência de mudança: confira antes de repetir.
O visor pode ter restrições do firmware quando o aparelho está desligado.
Alternar LED preserva rascunhos. O agente validou somente leitura real e escritas
simuladas; não ligou/desligou o LED no aparelho real.

## Swing vertical (cima/baixo)

O módulo anunciou SWING_VERTICAL_ANGLE e modos OFF/VERTICAL. A propriedade de
ângulo respondeu 0 numa consulta real. O protocolo mapeia OFF=0 e POS_1..5 como
1,25,50,75,100 (não graus). AUTO vem do modo de oscilação VERTICAL/BOTH.

Cada clique solicita next: o Controller relê o aparelho e calcula a próxima
etapa a partir dessa leitura, não de uma seleção local antiga. O ícone é geometria
QML: retângulo vertical e cinco linhas. Posição fixa mostra uma; AUTO mostra
cinco; OFF mostra nenhuma. Estado desconhecido desabilita o botão e é indicado
textualmente. Não foi necessário usar um seletor.

Exige ar ligado. Posições/OFF precisam de uma resposta nova de ângulo e modo;
AUTO exige o modo novo, sem precisar de ângulo absoluto durante a oscilação.
Modos/ângulos desconhecidos não viram OFF por fallback.

Posições usam a propriedade SWING_UD_ANGLE. Mudar oscilação usa SetState, após
leitura dos parâmetros, além da propriedade: AUTO limpa a posição antes de
iniciar oscilação; fixas/OFF param só o eixo vertical antes de ajustar a posição.
Oscilação horizontal existente é preservada. Confirma posição, modo de Swing e
manutenção de energia, modo de operação, alvo, IA/LED quando conhecidos.
Escritas não são repetidas automaticamente pelo adaptador; retransmissões internas
da biblioteca ainda existem, como nos demais comandos idempotentes.

Rascunhos são independentes. Capacidades e leitura não comprovam movimentação
física de todas as posições; o agente não enviou controles de Swing reais.

## Validação reproduzível

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qmltestrunner -input tests/qml
uv run python scripts/test-widget-backend.py
```

Use os executáveis Qt 6 em /usr/lib/qt6/bin; os homônimos em /usr/bin nesta máquina
não são a mesma versão. Para formatar QML:

```bash
/usr/lib/qt6/bin/qmlformat -i omarchy/victor.midea/Backend.qml omarchy/victor.midea/Widget.qml
```

A integração cria um shell Quickshell isolado e temporário, copia Backend/Model e
usa tests/fixtures/fake_widget_backend.py. Essa fixture **não importa msmart-ng,
não abre sockets e só altera um JSON temporário**. Testa consulta, liga/desliga
simulados, ajustes, falha, bloqueio de repetição e recuperação. Nunca aponta para
o executável real de controle.

Capturas locais revisadas, ignoradas pelo Git:
captures/widget/final-main.png e final-portrait.png. Renderização e leitura real
validadas; nenhum controle real enviado pelo agente.
