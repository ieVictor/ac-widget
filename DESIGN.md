---
name: Midea Desktop / Omarchy
description: Extensão nativa do shell existente, sem identidade visual independente.
---

# Design System: Midea Desktop / Omarchy

## Overview

O widget pertence à barra existente, não a um aplicativo web novo.
A autoridade visual é o shell instalado: componentes de /usr/share/omarchy/shell/Ui,
Color e Style. Nenhuma alteração no tema global é necessária.

## Colors

Color.popups.text e Color.popups.background definem o painel.
Color.accent destaca o indicador quando ligado; desligado usa o foreground da barra.
Valores são resolvidos pelo tema atual, não fixados ou duplicados neste projeto.
Texto de erro permanece legível e acompanha orientação de recuperação.
Exceção solicitada pelo usuário: marca textual AI em verde. Model.aiColor escolhe
um verde com contraste mínimo 4,5:1 sobre a superfície atual; demais controles
continuam usando o tema. A indicação de estado também é textual, não só cromática.

## Typography

Style.font.family, body, bodySmall, heading e displayLarge.
A escala maior serve ao dado de temperatura, não a uma voz de marca.
Não instalar fontes adicionais ou substituir a fonte escolhida pelo usuário.

## Layout

Painel ancorado no indicador. Cabeçalho/energia, alvo e ambiente, modo,
aplicação explícita, erro quando necessário, leitura e atualização.
Largura via Style.space(360), ajustada pelo painel aos limites do monitor.
Espaçamentos via Style.space; rolagem se a altura disponível for insuficiente.

## Elevation & Depth

Panel/KeyboardPanel fornecem superfície, borda, posicionamento e transição.
Não acrescentar sombras, halos ou blur decorativo.

## Shapes

Preservar a geometria dos componentes nativos. Nenhuma regra de radius própria.

## Components

- WidgetButton: indicador, clique para abrir e clique do meio somente leitura.
- Button: energia explícita, passos de meio grau, aplicação e atualização.
- AI: alternância independente da economia inteligente, nome acessível e estado
  checked confirmado. Não descarta rascunhos de temperatura/modo.
- Dropdown: modos anunciados; o valor selecionado é rascunho, não estado confirmado.
- LED: quadrado com marca textual LED à esquerda e título/estado à direita,
  nas mesmas dimensões e alinhamento do AI. Nome acessível Ligar/Desligar visor LED
  e checked confirmado, sem interferir em energia, IA ou rascunhos.
- Swing: mesmo botão quadrado, com retângulo vertical desenhado em QML.
  Cinco traços internos: só o correspondente à posição fixa, todos na oscilação,
  nenhum desativado. Texto/tooltip e nome acessível esclarecem estado e ação;
  o ícone só muda após confirmação. Sem fontes de ícones adicionais.
- KeyboardPanel: popout ajustado ao monitor, Escape e navegação por teclado.

Controles ficam desabilitados durante operação, erro, estado antigo ou capacidades
ausentes. Apenas confirmação do backend atualiza o estado exibido. O horário da
última leitura e a distinção entre alvo e ambiente devem permanecer visíveis.

## Do's and Don'ts

- Usar Color/Style e componentes nativos; não copiar a paleta como valores fixos.
- Preservar agrupamento e nomes de ação em português.
- Não simular sucesso nem exibir um rascunho como estado confirmado.
- Não descartar rascunhos durante polling de leitura.
- Não usar animação decorativa, cards adicionais ou uma marca independente.
- Não tratar capacidades anunciadas como comprovação de comportamento físico.
