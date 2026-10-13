# Midea Desktop

<!-- impeccable:product-schema 1 -->

## Platform

Linux desktop: Omarchy / Hyprland / Quickshell.

## Stack

Python 3.13 / msmart-ng no backend já implementado. A superfície escolhida pelo
usuário é um plugin da barra Omarchy, cujo sistema existente usa QML/Quickshell.

## Users

O proprietário do ar quer consultar e controlar o aparelho pelo desktop, sem
abrir o SmartHome no iPhone ou usar o controle remoto.

## Product Purpose

Controle acessível pela barra: estado, liga/desliga, temperatura, modo e
IA de economia energética (iECO/ECOMaster), visor LED e Swing vertical, solicitados
pelo usuário. Swing usa ícone com cinco linhas e ciclo de sete estados.

## Operating Context

Aparelho similar ao 38EZVCA12M5 / 42EZVCA12M5, descoberto como 0xAC / V3.
Conta privada SmartHome de e-mail/senha e chaves locais já configuradas pelo
usuário. Autenticação e leitura LAN validadas. Desktop com dois monitores.

## Capabilities and Constraints

- O usuário escolheu integração à barra Omarchy.
- Backend local, sem login cloud durante consultas ou controle.
- Não colocar chaves, senha ou identificadores na configuração da barra.
- Não ligar/desligar automaticamente ao abrir, carregar ou instalar o widget.
- Estado confirmado; nenhum sucesso otimista.
- O usuário relatou testar o widget básico, aparentemente funcionando.
- O agente não enviou comandos de controle reais; IA ainda aguarda teste manual.
- iECO tipo 8 (ECOMaster) e leitura da propriedade foram confirmados pela LAN.
- Nenhuma alteração em fontes empacotadas do Omarchy.

## Product Principles

- Usar a integração existente da barra, preservando tema e configuração.
- Ações de controle são explícitas, serializadas e confirmadas pelo aparelho.
- Falha de confirmação exige verificar o estado, não repetir automaticamente.
- Compartilhar consultas entre monitores e evitar polling agressivo.
