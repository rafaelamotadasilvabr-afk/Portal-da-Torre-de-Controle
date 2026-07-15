
# Portal de Gestão da Torre de Controle — V3

## Escopo atual

A V0 cruza três fontes:

1. AWBStatus Last Mile
   - considera somente `OPSStation = CDSP2`
2. Eu Entrego
   - usa `Pedido` como AWB
3. Planilha da Torre
   - usa `PENDENCIAS`
   - `PENDENCIA CORP`
   - `FINALIZADAS`
   - ignora `Página81`

Também existe um campo para colar códigos ou mensagens de retorno físico do WhatsApp.

Regra do código de retorno:

`577 + AWB de 8 dígitos + 4 dígitos finais`

Exemplo:

`577352504600001` → AWB `35250460`

## Como rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Como usar

1. Abra o Portal.
2. Faça upload do AWBStatus do Last Mile.
3. Faça upload do Eu Entrego.
4. Faça upload da Planilha da Torre.
5. Defina a data operacional de análise.
6. Cole os retornos físicos do WhatsApp, quando houver.
7. Confira:
   - Pendente de Entrega Real
   - Pendência Torre
   - Reentrega aguardando rota
   - Retorno pendente
   - Fila de ação
8. Exporte o resultado em Excel para validação.

## Observação

Esta é uma V0 de validação do motor de regras.  
O objetivo é confirmar a lógica operacional antes de incorporar First Mile, DGR, Avarias, Acareação e Indenizações.


## Correção V0.1

- Normalização correta dos códigos:
  - `577 + AWB + 4 dígitos`
  - `577 + AWB`
  - AWB pura
- Correção do cruzamento da Planilha da Torre.
- `Retorno Pendente` restrito a cargas ainda em `Pendente Entrega`.
- Cargas `Baixado`, `Missing Cargo`, `Discrepância Criada`, `Pendente Embarque` e `Pendente Desembarque` não são tratadas como retorno pendente.
- Tela de conciliação dos retornos colados.
