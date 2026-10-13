# Investigação da API — 2026-10-13

## Resumo

A descoberta LAN identificou um candidato 0xAC / V3. A investigação abaixo explica
a falha inicial da conta compartilhada: **SmartHome respondeu 3201:
`You have no permissions.`** ao getToken, mesmo com login válido.

**Atualização:** o usuário conectou o app com uma conta privada de e-mail/senha e
executou bootstrap com sucesso. O agente confirmou leitura LAN, com aparelho
desligado e capacidades recebidas. As chaves permanecem locais. O impedimento de
autenticação foi resolvido por esse caminho; não foram testados comandos de controle.

NetHome Plus respondeu 9999 no teste anterior. Há relatos upstream de que esse
endpoint falha inclusive para contas proprietárias. Trocar entre contas públicas
ou tentar mais regiões não é, neste momento, um caminho justificado.

A recomendação inicial de conta compartilhada foi baseada no README da biblioteca.
Os relatos recentes e a resposta observada mostram que esse caminho não funciona
nas condições testadas. Não há evidência de que criar outra conta ou resetar o
aparelho seja necessário.

## Evidência observada no aparelho do usuário

Foi realizada uma verificação limitada com a conta SmartHome compartilhada:

| Request | HTTP | Código da aplicação | Resultado |
|---|---:|---:|---|
| /v1/user/login/id/get | 200 | 0 | Identificação de login aceita |
| /mj/user/login | 200 | 0 | Login aceito |
| /v1/iot/secure/getToken | 200 | 3201 | `You have no permissions.` |

HTTP 200 **não** implica sucesso da operação: o erro está no JSON da aplicação.
O erro genérico foi divulgado somente após rejeitar strings com dígitos, e-mails,
identificadores, credenciais conhecidas ou sequências longas. Headers, assinaturas,
corpos brutos, sessões, tokens e chaves não foram registrados nem publicados.

Campos do getToken, apenas nomes:

```text
appId, applianceCodes, clientType, deviceId, format, language,
reqId, src, stamp, udpid
```

- `applianceCodes` estava presente e não vazio.
- `udpid` era hexadecimal de 32 caracteres, derivado do ID LAN.
- O campo ausente corrigido pelo PR #288 **não** explica o erro deste pedido.
- A resposta confirma uma recusa de autorização para a combinação de conta/ID
  enviada. Sozinha, não separa propriedade da conta de eventual discrepância de IDs.
- Nenhuma chave foi recebida ou salva. Não houve autenticação LAN, leitura de estado
  autenticada, controle, pareamento, compartilhamento de aparelho ou reset.

## Evidência externa e sua força

### NetHome Plus: getToken com problema conhecido

O issue #290 está aberto na consulta realizada. Um relato de 2026-09-07 diz que
login e listagem funcionam, mas getToken retorna 9999 em contas proprietárias,
com diferentes regiões, app IDs e variações dos parâmetros. É evidência de outros
usuários, não um comunicado oficial Midea sobre indisponibilidade global.

Fonte:
https://github.com/mill1000/midea-msmart/issues/290
https://github.com/mill1000/midea-msmart/issues/290#issuecomment-5570188094

### SmartHome: conta precisa possuir o aparelho

No PR #288, o autor relata:
- Conta proprietária recebe as chaves.
- Conta válida que não possui o aparelho não recebe as chaves.
- Compartilhar o aparelho entre contas não resolveu o cenário medido.
- Contas públicas embutidas não possuem os aparelhos dos usuários.

Isso é compatível com a recusa 3201 observada, mas não auditamos a política de
permissões completa da API. Não testar vinculação à conta pública para contornar
esse requisito; isso alteraria o pareamento e não foi autorizado.

Fonte:
https://github.com/mill1000/midea-msmart/pull/288#issuecomment-5361402410

### ID da nuvem pode diferir do ID LAN

Outro usuário relatou que o catálogo `/v1/appliance/user/list/get` devolvia um
ID diferente daquele descoberto na LAN. A combinação que funcionou foi:

```text
udpid          <- derivado do ID LAN
applianceCodes <- ID cloud do aparelho na conta proprietária
```

Um segundo usuário tinha IDs iguais, portanto a discrepância não é universal.
O projeto não conhece o ID cloud do aparelho atual: a conta proprietária ainda
não foi autenticada. Não adivinhar IDs nem enumerar aparelhos alheios.

Fontes:
https://github.com/mill1000/midea-msmart/pull/288#issuecomment-5432410040
https://github.com/mill1000/midea-msmart/pull/288#issuecomment-5457742525

### Correção já presente na dependência

O commit `d7db53bc470d` adicionou applianceCodes. Está na dependência instalada
msmart-ng 2026.9.0, e o nosso adaptador já envia esse campo. Atualizar apenas para
obter essa correção não muda a autorização da conta compartilhada.

Fonte:
https://github.com/mill1000/midea-msmart/commit/d7db53bc470d

## Ajustes no projeto

- Erro 3201 agora explica necessidade da conta proprietária / ID cloud correto.
- Após 3201, bootstrap para imediatamente: mudar endianness não altera a conta
  nem o ID enviado em applianceCodes. Não há repetição inútil dessa recusa.
- `bootstrap --cloud-id ID` permite separar cloud ID do LAN ID, quando obtido
  legitimamente no catálogo da conta proprietária. O padrão ainda é LAN ID,
  porque pode coincidir; não existe listagem automática do catálogo nesta etapa.
- `udpid`, autenticação LAN e configuração local continuam usando o LAN ID.
- ID cloud, applianceCodes e udpid são tratados como identificadores para
  anonimização do diário.
- Testes offline cobrem IDs distintos, interrupção por permissão, mensagens
  sanitizadas e ausência de controle durante bootstrap.

## Caminho que falta validar

Durante a investigação, era necessário obter uma autenticação **da conta que
possui o aparelho**, não necessariamente criar uma conta nova. Posteriormente,
o usuário escolheu a conta privada de e-mail/senha e conectou o aparelho nela;
a autenticação e a leitura LAN funcionaram.

O projeto aceita senha Midea, mas não implementa Google OAuth. Não foi demonstrado
que a versão do aplicativo do usuário permita definir uma senha na conta existente.
Também não foi identificado/implementado o fluxo OAuth específico usado pelo app.

Opções a investigar com o usuário:
1. Se o app permite definir/vincular uma senha própria na mesma conta, mantendo
   aparelho e login Google. Não usar a senha Google no projeto.
2. Se não permite, mapear o fluxo de sessão OAuth autorizado da conta existente.
   Isso exige saber Android/iOS e a versão do app; não adivinhar endpoints nem
   copiar sessões de outra conta. Qualquer material sensível deve permanecer local.
3. Uma nova conta e novo pareamento são uma alternativa separada, somente após
   consentimento explícito e consulta ao procedimento correto do aparelho.

Não desabilitamos TLS, não interceptamos o celular, não coletamos senhas/cookies
pessoais e não abrimos portas externas. Autenticação e leitura LAN estão validadas;
comandos que alteram o aparelho ainda não foram testados.
