# Roteiro de investigação no seu aparelho

Investigue apenas aparelhos, contas e redes que você possui ou tem autorização.
Não compartilhe token, key, senha, cookies, sessão, serial ou captura bruta.

## 1. Inventário

Anote localmente:
- Código exato da etiqueta e identificação do módulo Wi-Fi, se disponível.
- Versão do app SmartHome e sistema do celular.
- IP do aparelho no roteador, SSID, VLAN e subnet do computador.
- Existência de rede guest / client isolation.
- Resultado de discover (tipo e versão, sem publicar os identificadores).

Não é necessário redefinir o aparelho, reemparelhar ou colocá-lo em modo AP.
Se o broadcast não funcionar, consulte o DHCP e tente descoberta direcionada.

## 2. Primeiro caminho: LAN existente

1. Execute `discover` ou `discover --host IP`.
2. Se for V3, faça `bootstrap` explicitamente com sua conta ou configure chaves
   existentes obtidas de uma integração autorizada.
3. Consulte `status`, sem alterar parâmetros.
4. Compare a temperatura/modo com o aplicativo e o visor.
5. Só depois execute um comando de controle escolhido por você.

Se a biblioteca não reconhecer o aparelho, preserve o resultado e investigue
o protocolo antes de ampliar o adaptador. Não marque como compatível só por
ter nome Midea.

## 3. Matriz de experimentos

Execute uma alteração de cada vez, com intervalo e observação física.
Evite ciclos rápidos de liga/desliga do compressor.

| Experimento | Registrar antes | Alteração | Registrar depois |
|---|---|---|---|
| Leitura | App/visor e horário | status | Estado LAN |
| Power | Ligado/desligado | on ou off | LAN + observação |
| Temperatura | Valor atual | Meio grau/grau válido | LAN + visor/app |
| Modo | Modo atual | Modo suportado | LAN + app |
| Controle pelo celular | Estado LAN | Uma ação no SmartHome | Nova consulta LAN |
| Controle sem internet | Chaves já salvas | Bloqueio WAN autorizado do aparelho | LAN funciona? |

Não desligue a internet de toda a casa nem altere firewall sem entender os
efeitos. O último experimento é opcional e deve ser controlado pelo usuário.

Registre operações com:
```bash
uv run midea-desktop --journal ./captures/calls.jsonl status
```

O diário mede chamadas semânticas. Pacotes, retransmissões e endpoints HTTP
exatos exigem captura/análise separada.

## 4. Captura LAN opcional

Escolha a interface real com `ip -br addr`. O exemplo abaixo exige privilégio
e deve ser executado conscientemente em um terminal; **não foi executado pelo
agente**.

```bash
mkdir -m 700 -p captures
# Troque wlan0 e o IP pelos valores reais:
sudo tcpdump -i wlan0 -nn -s0 \
  'host 192.168.1.50 and (tcp port 6444 or udp port 6445 or udp port 20086)' \
  -w captures/midea-lan.pcap
# Ctrl+C encerra. Use a porta TCP real se a descoberta anunciar outra.
```

Revise proprietário e permissões antes de abrir/compartilhar o arquivo.
PCAP pode conter material de autenticação. Não faça commit.

Limite importante: um computador conectado ao Wi-Fi normalmente não observa
o tráfego unicast entre celular e aparelho. Para mapear o app, seria necessário
um ponto de captura autorizado (roteador/AP, espelhamento de porta ou captura no
próprio celular). A captura acima observa principalmente a sessão deste projeto.

## 5. HTTPS do SmartHome — apenas se LAN não resolver

Comece por documentação e código da biblioteca. Anote hosts, caminhos,
ordem dos requests, versão do app e códigos de erro, sem copiar credenciais.

Se optar por proxy de diagnóstico no próprio celular, use um ambiente de teste
autorizado, consentimento explícito e certificados apenas nesse ambiente.
TLS e certificate pinning podem impedir a inspeção; não conte com mitmproxy como
solução universal. Não remova verificações TLS no projeto nem distribua APKs
modificados ou certificados privados.

Não implementamos proxy, bypass de pinning nem armazenamento de credenciais
cloud. O bootstrap é uma chamada documentada da biblioteca, não uma captura
do app.

## 6. Produzir uma hipótese verificável

Para cada campo/endpoint, separe:
- **Observado:** request/response sanitizado e condição do teste.
- **Inferido:** hipótese e experimento que pode refutá-la.
- **Reutilizado:** comportamento vindo da biblioteca, ainda não validado no modelo.

Promova recursos ao widget somente após confirmar autenticação, leitura,
controle, timeout e falha de confirmação no aparelho real.
