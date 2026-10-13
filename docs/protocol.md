# Mapa inicial do protocolo

## Evidência e limites

Fonte: código e README de **msmart-ng 2026.9.0**, dependência fixada no projeto.
Não houve captura do aplicativo SmartHome nem validação contra o modelo citado.
A identificação comercial de um modelo similar não determina o módulo Wi-Fi.

Referências:
- https://github.com/mill1000/midea-msmart
- https://github.com/mill1000/midea-msmart/blob/master/msmart/discover.py
- https://github.com/mill1000/midea-msmart/blob/master/msmart/lan.py
- https://github.com/mill1000/midea-msmart/blob/master/msmart/cloud.py
- https://github.com/mill1000/midea-msmart/blob/master/msmart/device/AC/command.py

Os links para master podem mudar. Para reproduzir a análise, use os arquivos
instalados pela versão fixada em `.venv/lib/python3.13/site-packages/msmart/`.

## Operações do adaptador

| Ação | API Python | Transporte | Efeito |
|---|---|---|---|
| Descoberta | Discover.discover(auto_connect=False) | UDP 6445 e 20086 | Identificação, sem login/controle |
| Obter chaves V3 | cloud.login(), cloud.get_token() | HTTPS | Autenticação cloud e token/key |
| Autenticar V3 | AC.authenticate(token, key) | TCP, porta anunciada | Sessão LAN |
| Capacidades | AC.get_capabilities() | LAN | Consulta recursos |
| Estado | AC.refresh() | LAN | Consulta parâmetros |
| Ligar/desligar | power_state = bool; AC.apply() | LAN | Envia estado |
| Temperatura | target_temperature = float; AC.apply() | LAN | Envia estado |
| Modo | operational_mode = enum; AC.apply() | LAN | Envia estado |

A porta de controle costuma ser **6444**, mas priorizamos a porta anunciada.
`Discover.discover()` sem `auto_connect=False` pode autenticar automaticamente
usando nuvem NetHome Plus. Por isso este projeto desativa essa opção e separa
o bootstrap explícito.

## Nuvem — obtenção inicial, não controle diário

SmartHome:
- Base global: `https://mp-prod.appsmb.com`.
- Envelope de proxy: `/mas/v5/app/proxy?alias=<endpoint>`.
- Identificação de login: `/v1/user/login/id/get`.
- Login: `/mj/user/login`.
- Chaves: `/v1/iot/secure/getToken`.

NetHome Plus:
- Base: `https://mapp.appsmb.com`.
- Usa endpoints e envelope próprios implementados por NetHomePlusCloud.
- Não é intercambiável automaticamente com SmartHome.

O getToken recebe um `udpid` derivado do **ID LAN**; SmartHome também exige
o **ID cloud** em `applianceCodes`. Há relatos de que esses IDs podem diferir.
`bootstrap --cloud-id ID` permite fornecer o ID cloud legítimo sem mudar o LAN ID.
A biblioteca tenta representações little/big endian ao autenticar; após recusa
3201 de permissão, nosso adaptador encerra em vez de repetir com outra ordem.
Não copiamos segredos fixos da biblioteca, senhas nem respostas de sessão para
a documentação. Veja [a investigação da API](api-investigation.md): no aparelho
atual, getToken negou permissão à conta compartilhada, mesmo com applianceCodes.

## Camadas LAN

1. Frame AC: cabeçalho iniciado em **0xAA**, tipo de aparelho **0xAC**, tipo
   de frame, payload, ID de mensagem, CRC8 e checksum.
2. Envelope V2: início **0x5A5A**, cabeçalho com ID do aparelho, payload
   criptografado e assinatura. A biblioteca usa AES-ECB no payload e MD5
   para integridade desse envelope.
3. V3: camada externa **0x8370**, autenticação com token/key e chave de
   sessão; AES-CBC e SHA-256 segundo a implementação da biblioteca.

Não se trata de uma API REST do aparelho. Uma captura TCP cifrada não exibe
diretamente temperatura e power sem analisar essas camadas.

## Campos úteis do frame AC

Índices abaixo são relativos ao **payload do comando**, antes de ID/CRC/checksum:

| Comando | Campo | Valor / interpretação |
|---|---|---|
| GetCapabilities | payload[0] | 0xB5 |
| GetState | payload[0] | 0x41 |
| SetState | payload[0] | 0x40 |
| SetState | payload[1], bit 0 | power |
| SetState | payload[2], bits 5–7 | modo |
| SetState | payload[2], bits 0–4 | temperatura principal e meio grau |
| SetState | payload[3] | ventilação |
| SetState | payload[7] | swing |
| SetState | payload[18] | temperatura alternativa fora da faixa principal |

Para a codificação principal 17–30 °C, a parte inteira é relativa a 16;
há bit de meio grau. Outras temperaturas usam uma representação alternativa.
Não faça edição isolada de um byte sem recalcular CRC/checksum, preservar os
demais campos e considerar a cifragem LAN.

Modos da biblioteca: AUTO=1, COOL=2, DRY=3, HEAT=4, FAN_ONLY=5, SMART_DRY=6.
Isso **não implica** suporte a aquecimento no aparelho real.

## O que ainda precisa de evidência

- Versão LAN e tipo retornados pelo módulo Wi-Fi real.
- Se a conta SmartHome permite getToken na região do usuário.
- Se capacidades são retornadas ou a biblioteca permanece em defaults.
- Limites e resolução reais da temperatura e recursos de ventilação.
- Correspondência entre confirmação LAN, visor e estado no aplicativo.
- Comportamento após mudança de DHCP, reboot do módulo ou troca de chaves.

A biblioteca pode registrar uma falha de capacidades sem levantar exceção.
A saída status inclui `capabilities_from_device`: false significa que nenhuma
resposta de capacidades foi processada nesta instância e os valores podem ser
defaults. Mesmo com true, a biblioteca pode preencher campos ausentes com defaults.
O estado online/supported também pode persistir: por isso VerifiedAC observa
os hooks internos `_update_state` / `_update_capabilities` da versão fixada e
exige que refresh processe uma nova StateResponse antes de confirmar controle.
Esses hooks e seus testes devem ser revistos ao atualizar a dependência.
