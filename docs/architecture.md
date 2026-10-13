# Arquitetura e próximos passos

## Estado atual

```text
Barra Omarchy / Widget.qml
  → Backend.qml (singleton compartilhado entre monitores)
  → Quickshell Process assíncrono
  → midea-desktop widget status|on|off|set
  → Controller → msmart-ng → módulo Wi-Fi pela LAN

bootstrap → SmartHomeCloud/NetHomePlusCloud → token/key → autenticação LAN
```

Configuração privada e diário são componentes separados. A conta cloud não é
persistida. Não existe servidor HTTP, daemon Python ou autostart próprio: o
plugin usa o shell já instalado.

## Interface entregue

Superfície escolhida pelo usuário: plugin local da barra Omarchy.

- Indicador e painel usando os componentes, tema e tipografia do shell.
- Liga/desliga explícito e ajustes de temperatura/modo em rascunho.
- Consulta inicial, ao abrir e periódica; mínimo 30 segundos, padrão 60.
- Um processo por vez e estado compartilhado entre monitores.
- Watchdog de 40 segundos; timeout CLI de 30 segundos.
- Sem sucesso otimista ou repetição automática de escritas.
- Controles exigem estado recente, capacidades recebidas e nenhuma operação ativa.
- Model.js valida e filtra o JSON novamente antes de guardá-lo na interface.
- Presentation.py omite identificadores, chaves e recursos desnecessários.
- IPC local do widget oferece apenas diagnóstico/atualização, não controle remoto.
- Instalador com backup, sem editar fontes empacotadas do Omarchy.

Veja [operação e testes](omarchy-widget.md).

## Validação e pendências

Autenticação, respostas novas de estado/capacidades e renderização nos dois
monitores foram verificadas. Controle e falhas foram exercitados com backend
simulado isolado; isso **não valida comandos no aparelho real**.

Próximo passo: testar liga/desliga e depois temperatura/modo com autorização
explícita. HEAT anunciado pelo módulo não comprova aquecimento físico.

## Limitações deliberadas do MVP

- Apenas um aparelho/configuração.
- IPv4 e controle LAN; sem alternativa cloud para controle remoto.
- Sem keyring: token/key em arquivo 0600.
- Sem garantia de preservação de recursos desconhecidos pela biblioteca.
- Bloqueio de concorrência no Controller e no widget, não entre processos CLI
  independentes; evite controles simultâneos pela CLI, app e widget.
- Adaptador sobre biblioteca fixada, não protocolo reimplementado do zero.
- Caminho do executável apontando para a .venv do projeto; mantê-la disponível.
- Atualizar um singleton QML já carregado exige reiniciar o processo da barra.
