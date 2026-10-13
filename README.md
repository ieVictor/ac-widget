# ac-widget

Widget Omarchy e CLI `midea-desktop` para controle LAN.

Projeto experimental para controlar um ar-condicionado Midea pelo Linux, sem abrir
o celular. O ponto de partida é um modelo **similar** ao
38EZVCA12M5 / 42EZVCA12M5, associado ao aplicativo **SmartHome**.

**Etapa entregue: backend LAN e widget integrado à barra do Omarchy.**
Autenticação, leitura e interface foram validadas no aparelho/desktop reais com
uma conta privada do usuário. Comandos de controle passaram em simulação, mas
**ainda não foram testados no aparelho real pelo agente**.
Não é software oficial Midea.

## Por que não interceptar o aplicativo primeiro?

A [msmart-ng](https://github.com/mill1000/midea-msmart) já documenta e implementa
parte do protocolo LAN. Reaproveitamos essa engenharia reversa, mantendo um
adaptador próprio para a CLI e o widget. Não afirmamos ter capturado chamadas do
seu celular ou confirmado o seu modelo.

- **V2:** controle local sem token/key.
- **V3:** token/key para autenticação LAN; obtenção inicial pode exigir a nuvem.
- **Depois de salvar as chaves:** status e controle não usam a nuvem.
- **V1, tipos diferentes de 0xAC e recursos não reconhecidos:** fora deste adaptador
  inicial, mesmo que a biblioteca suporte outros tipos.

## Começar

Requisitos: Linux, [uv](https://docs.astral.sh/uv/) e aparelho na mesma rede IPv4.
O projeto usa Python 3.13 isolado em `.venv`; não altera o Python do sistema.

```bash
mkdir -p ~/development
git clone https://github.com/ieVictor/ac-widget.git ~/development/midea-desktop
cd ~/development/midea-desktop
uv sync --dev
uv run midea-desktop --help

# Somente descoberta UDP. Sem login cloud e sem ligar/desligar.
uv run midea-desktop discover

# Se o broadcast não encontrar o aparelho, use o IP obtido no roteador.
uv run midea-desktop discover --host 192.168.1.50
```

A saída informa IP, ID, porta, versão e um candidato de compatibilidade.
`compatibility_candidate: true` identifica a classe 0xAC, **não** comprova que
todas as funcionalidades funcionam. Uma lista vazia também não comprova
incompatibilidade: verifique Wi-Fi, VLAN, firewall e isolamento de clientes.

### Autenticação inicial V3

```bash
# Comando explícito que usa a nuvem. Conta e senha são solicitadas no terminal.
uv run midea-desktop --timeout 90 bootstrap --host 192.168.1.50
```

O provedor padrão é **SmartHome**. O comando faz descoberta local, login com
**sua própria conta**, obtém as chaves, autentica e consulta o estado do aparelho.
Só salva após uma leitura reconhecida; não envia comandos de controle.
Por padrão exige sua própria conta e não salva a senha. Não aceita Google OAuth:
**nunca forneça sua senha do Google** nesse prompt.

#### Conta compartilhada — autorização explícita

**Situação investigada:** SmartHome recusou a conta compartilhada por permissão
(3201); NetHome Plus tem relatos de falha no getToken, inclusive com contas
proprietárias. Não recomendamos insistir nesse caminho ou reemparelhar com uma
conta pública. Veja [a investigação da API](docs/api-investigation.md).

O projeto mantém uma opção explícita de conta compartilhada para diagnóstico,
sem criar conta pessoal nem repetir pareamento:

```bash
uv run midea-desktop --timeout 90 bootstrap --host 192.168.1.50 --shared-account
```

Esse flag autoriza o uso das contas embutidas da msmart-ng para obter as chaves.
Não solicita credenciais pessoais, não faz vínculo/pareamento nem envia controle.
A documentação upstream diz que os aparelhos não são vinculados a essas contas;
isso não constitui auditoria de segurança nem garantia de suporte ao seu modelo.
Só salva chaves depois de autenticação e uma nova resposta LAN de estado válida.

O serviço Midea recebe o identificador do aparelho e vê o IP público da conexão.
Contas compartilhadas podem ser bloqueadas, alteradas ou sofrer limites de uso.
Não há fallback silencioso para elas: o flag é obrigatório a cada bootstrap.
Depois de salvar as chaves, `status` e controle utilizam apenas LAN.

Na investigação sanitizada descrita em [docs/api-investigation.md](docs/api-investigation.md),
os logins compartilhados funcionaram, mas getToken foi recusado (SmartHome 3201 / NetHome
Plus 9999), nas duas ordens de bytes. Nenhuma chave foi salva ou comando de
controle enviado. Isso não comprova a causa da recusa nem exige reset/pareamento.

`--provider nethome` é uma alternativa para quem tem conta **NetHome Plus**.
Não pressuponha que a conta SmartHome funcione nesse provedor. `--region` é
repassado à biblioteca; o padrão US não é uma afirmação de suporte regional ao
seu modelo brasileiro. Login social, MFA ou restrições da API podem impedir o
bootstrap. Nesse caso, use chaves obtidas legitimamente em outra integração.

O ID cloud pode ser diferente do ID LAN. Se você já obteve o ID correto do catálogo
da **conta proprietária**, `bootstrap --cloud-id ID` o usa em `applianceCodes`,
mantendo o ID LAN para derivar `udpid` e autenticar no aparelho. Não adivinhe esse
ID: a listagem automática do catálogo e Google OAuth ainda não estão implementados.
Após erro 3201, o bootstrap encerra sem tentar outra ordem de bytes.

### Configuração manual / V2

```bash
uv run midea-desktop configure --host 192.168.1.50 --id 123456789 --version 2

# V3 solicita token/key por entrada oculta, sem argumentos no histórico do shell.
uv run midea-desktop configure --host 192.168.1.50 --id 123456789 --version 3
```

Use somente o IP, ID, versão e porta **reais** da descoberta. Os valores acima são
exemplos. A configuração manual não testa a conexão. Para substituir uma
configuração existente é necessário acrescentar `--replace`.

### Controle local — somente depois de validar o estado

```bash
uv run midea-desktop status

# Estes comandos alteram o aparelho real:
uv run midea-desktop on
uv run midea-desktop off
uv run midea-desktop set --temperature 24 --mode cool
uv run midea-desktop set --power on --temperature 23.5 --mode cool
```

`set` sem `--power` não liga o aparelho automaticamente. Antes de cada alteração,
o adaptador consulta o estado para preservar os parâmetros conhecidos, pois
`apply()` envia um conjunto de propriedades, e não apenas o campo modificado.
Valida temperatura em passos de 0,5 °C e os modos informados pela biblioteca.

Após enviar, exige uma nova resposta de estado válida e verifica os campos
solicitados; flags online/supported ou estado em cache não bastam. Timeout,
resposta não reconhecida ou estado divergente **não** são tratados como sucesso. Um erro
após o envio não garante que nada mudou: confira o aparelho antes de repetir.
A biblioteca tem retransmissões internas; o nosso adaptador não acrescenta
repetição automática de comandos de controle. Leituras concorrentes no mesmo
Controller são serializadas; processos CLI distintos não compartilham esse lock.

## Widget da barra Omarchy

Requer o shell Quickshell com suporte a plugins locais.

```bash
uv sync --dev
./scripts/install-omarchy.sh
# Para atualizar uma instalação existente, com backup:
./scripts/install-omarchy.sh --replace
```

O plugin `victor.midea` fica em `~/.config/omarchy/plugins/` e é habilitado na
seção direita. O instalador preserva o shell e o plugin anterior em
`~/.local/state/midea-desktop/backups/`; nunca modifica fontes empacotadas ou
chaves do aparelho. Se alterar o singleton `Backend.qml`, execute
`omarchy restart shell` para carregar sua nova versão; o instalador não reinicia
a barra automaticamente.

- Clique no indicador **Desl.** / temperatura para abrir o painel.
- **Ligar ar / Desligar** envia uma ação real e explícita.
- **− / +** e **Modo** editam um rascunho. Só **Aplicar ajustes** envia os ajustes,
  sem alterar liga/desliga.
- **AI** verde alterna a economia inteligente iECO/ECOMaster separadamente dos
  ajustes. Para ativar, o ar deve estar ligado em Refrigerar; não liga sozinho.
  Exige uma resposta nova da propriedade iECO, não apenas o estado geral.
- O quadrado **LED**, ao lado de Visor LED e seu estado, liga/desliga somente
  o visor, preservando os ajustes pendentes. Consulta antes/depois e não retransmite o comando de alternância.
- O ícone **Swing vertical** avança uma etapa por clique: desativado → posições
  1–5 → oscilando → desativado. Uma linha indica a posição; cinco, oscilação;
  nenhuma, desativado. Exige ar ligado e confirmação, sem alterar os rascunhos.
- **Atualizar** ou clique do meio no indicador consulta o estado.
- Escape fecha o painel; os controles oferecem navegação por teclado.
- Consultas compartilhadas entre monitores a cada 60 segundos; nenhuma escrita
  automática ao abrir, carregar, instalar ou atualizar.
- Sem confirmação ou capacidades recebidas do aparelho, o controle fica bloqueado.
  Falha depois de enviar pode significar alteração parcial: confira antes de repetir.

Diagnóstico somente leitura, sem identificadores ou chaves:

```bash
omarchy-shell midea-widget status
omarchy-shell midea-widget refresh
omarchy plugin disable victor.midea  # Retirar da barra
```

Detalhes: [widget e testes de integração](docs/omarchy-widget.md).

## Mapear chamadas

```bash
# Offline: exemplos de frames AC, sem abrir sockets.
uv run midea-desktop frames

# Diário semântico opcional, sem chaves, senha, serial, IP ou ID.
uv run midea-desktop --journal ./captures/calls.jsonl status

# Controle explícito com registro antes/depois.
uv run midea-desktop --journal ./captures/calls.jsonl set --temperature 24
```

O diário registra operações do adaptador e estados sanitizados. **Não é uma
captura de pacotes nem reproduz os requests do aplicativo.** Os frames offline
são exemplos da biblioteca e também não foram capturados do seu aparelho.

Leia [o mapa inicial do protocolo](docs/protocol.md) e
[o roteiro de investigação](docs/reverse-engineering.md).

## Segurança e dados locais

- Configuração: `${XDG_CONFIG_HOME:-~/.config}/midea-desktop/device.json`,
  arquivo **0600**. `--config CAMINHO` permite um arquivo alternativo.
- Token/key ficam em texto claro nesse arquivo privado. Não há integração com
  keyring nesta etapa. Proteja backups: essas chaves permitem controle LAN.
- JSON de saída omite chaves e serial; descoberta/status incluem identificadores
  locais necessários ao uso. Não publique essas saídas sem revisar.
- Diário opcional tem permissão 0600 e remove também identificadores locais.
  Não habilitamos logs DEBUG da biblioteca, que podem expor segredos.
- Configuração, diários, capturas, backups e o registro local de investigação
  são ignorados pelo Git. Isso não substitui uma revisão antes de compartilhar
  arquivos. Os valores de autenticação dos testes são sintéticos, nunca chaves reais.
- Não abrimos portas TCP/HTTP nem instalamos um daemon Python ou autostart próprio.
  O plugin usa o shell existente e seu IPC local; somente sua instalação altera
  a lista de plugins da barra, com backup. Não alteramos a configuração Hyprland.
- Reservar o IP do aparelho no DHCP ajuda a manter o controle funcionando.

## Desenvolvimento

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
QT_QPA_PLATFORM=offscreen /usr/lib/qt6/bin/qmltestrunner -input tests/qml
# Integração Quickshell isolada, com backend falso e sem acesso ao ar:
uv run python scripts/test-widget-backend.py
```

Testes usam objetos simulados: **não acionam o ar nem fazem login**.

```text
src/midea_desktop/
  config.py       Configuração privada e validação
  controller.py   Descoberta, bootstrap e controle assíncrono reutilizável
  transport.py    Verificação de resposta nova versus estado em cache
  journal.py      Redação de segredos e diário semântico
  cli.py          Comandos JSON para diagnóstico e controle
  presentation.py JSON mínimo e sem identificadores para o widget
omarchy/victor.midea/  Plugin QML, modelo e backend compartilhado
scripts/          Instalação e integração simulada
tests/            Testes Python/QML offline e fixtures simuladas
docs/             Protocolo, investigação, widget e próximos passos
```

## Próximos passos

1. Testar liga/desliga no aparelho com autorização explícita.
2. Comparar temperatura, modos e resposta com o SmartHome.
3. Avaliar o widget no uso diário e eventual integração com keyring.
   Veja [arquitetura e pendências](docs/architecture.md).
