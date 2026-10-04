# Pitch técnico (≈ 7 minutos)

Roteiro slide a slide com o que mostrar e o que falar. Ajuste os nomes do time.

---

### 1. Abertura (30 s)
**Slide:** "Lia — a SDR que não dorme" + logo fictício da Aurora Imóveis.
**Fala:** "Quanto mais um lead imobiliário espera por resposta, mais ele esfria. Hoje, imobiliárias perdem leads por demora, falta de acompanhamento e corretores sobrecarregados. Construímos a Lia, uma SDR com IA generativa que atende, qualifica, agenda e passa o lead pronto para o corretor."

### 2. O problema (40 s)
**Slide:** as 5 dores da proposta (tempo de resposta, falta de acompanhamento, atendimento manual, priorização, sobrecarga).
**Fala:** ligar cada dor a uma funcionalidade da Lia (tabela "Problema e solução" do README).

### 3. Demo ao vivo ou vídeo (2 min 30 s)
Siga o [roteiro de demonstração](roteiro_demo.md), cenas 1, 2 e 4 (compra, investimento e painel). Se o tempo permitir, mostre o follow-up (cena 3).

### 4. Arquitetura (1 min)
**Slide:** diagrama de componentes do README.
**Fala:**
- "Canais independentes (chat web com voz, WhatsApp, API) chamam o mesmo serviço."
- "O cérebro é um grafo LangGraph com 5 agentes especializados; as decisões de fluxo são código, não adivinhação do modelo."
- "Todo o estado fica no banco, então a aplicação escala horizontalmente; o follow-up roda como um worker separado."

### 5. A IA por dentro (1 min)
**Slide:** diagrama do grafo.
**Fala:**
- "Cada mensagem passa por um guardrail, depois por uma **extração estruturada** com Pydantic, que transforma a conversa em dados: intenção, região, orçamento, urgência."
- "Esses dados alimentam o **score explicável**, a **busca RAG** de imóveis e a **agenda**."
- "O agente só cita imóveis recuperados da base, então não inventa preço nem endereço."
- "Temperatura 0 para extrair, 0,6 para conversar: precisão onde importa e naturalidade na fala."

### 6. Diferenciais (40 s)
**Slide:** checklist com os 9 diferenciais da proposta, todos marcados.
**Fala:** destacar RAG híbrido, memória persistente, multiagentes, voz, WhatsApp com validação de assinatura, CRM com exportação, observabilidade (latência por agente e LangSmith), segurança (prompt injection e LGPD) e Docker.

### 7. Qualidade e próximos passos (30 s)
**Slide:** "28 testes automatizados" + roadmap.
**Fala:** "Os três cenários da proposta são testados de ponta a ponta sem custo de API. Próximos passos: PostgreSQL, Google Calendar, integração com o CRM real e um score aprendido com o histórico de conversões."

### 8. Fechamento (10 s)
**Fala:** "A Lia atende em segundos, nunca esquece um lead e entrega ao corretor só o que importa: clientes prontos para visitar. Obrigado!"

---

## Perguntas prováveis da banca

| Pergunta | Resposta curta |
|---|---|
| Por que LangGraph e não um agente com tools livre? | Fluxo previsível e testável; o LLM decide a linguagem, o código decide o processo. Menos alucinação e custo menor. |
| Como evitam que a IA invente imóveis? | RAG: só os imóveis recuperados entram no prompt, e há uma regra explícita proibindo citar outros. |
| E se o cliente mudar de ideia no meio? | A extração relê a conversa inteira a cada mensagem; a informação mais recente prevalece e o roteador troca de agente. |
| Quanto custa? | Com `gpt-4o-mini` são cerca de 2 chamadas por mensagem (extração + resposta); a busca semântica usa embeddings em cache. Dá para medir no LangSmith. |
| Escala? | O grafo não guarda estado; trocando SQLite por PostgreSQL, a API e o worker escalam horizontalmente. |
| LGPD? | Não pedimos documentos, removemos CPF e cartão, mascaramos dados pessoais nos logs, usamos hash do lead no tracing e respeitamos o pedido de não contato. |
