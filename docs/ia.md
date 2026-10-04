# Explicação da IA utilizada

## Modelos

| Uso | Modelo (configurável no `.env`) | Por quê |
|---|---|---|
| Conversa dos agentes | `gpt-4o-mini`, temperatura 0,6 | Ótima relação qualidade/custo/latência para português conversacional; um pouco de variação deixa o texto natural |
| Extração estruturada | `gpt-4o-mini`, temperatura 0, function calling | Saída determinística validada por Pydantic |
| Busca semântica (RAG) | `text-embedding-3-small` | Embeddings baratos e bons em português; 124 vetores cabem em memória |
| Voz para texto | `whisper-1` | Transcreve áudios do chat e do WhatsApp |
| Texto para voz | `gpt-4o-mini-tts` (voz `nova`) | Resposta falada opcional no chat |

Toda chamada passa por `src/llm/client.py`, o que permite trocar de provedor ou modelo em um único lugar e substituir o LLM por um falso nos testes. O cliente aceita qualquer API compatível com a da OpenAI (`LLM_BASE_URL`), e o projeto já vem com uma configuração pronta para o Google Gemini gratuito (`.env.gemini.example`). A extração estruturada tenta function calling e, se o provedor não suportar, usa JSON schema.

## Orquestração multiagente (LangGraph)

O agente não é um prompt gigante: é um **grafo de estados** em que cada nó tem uma responsabilidade. A cada mensagem:

1. **Guardrail** — bloqueia tentativas de prompt injection antes de gastar tokens.
2. **Extração** — o LLM lê a conversa inteira e devolve um objeto `Extracao` com:
   - `dados`: intenção (compra, aluguel ou investimento), região, valor máximo, quartos, urgência, preferências, forma de pagamento, ticket, retorno esperado, perfil do investidor, nome, contato e imóvel de interesse;
   - `sinais` da última mensagem: aceitou ou recusou agendar, qual opção de horário escolheu, se pediu outro dia ou período, se perdeu o interesse.
3. **Qualificação** — código Python compara os dados com os campos exigidos por intenção e define a etapa.
4. **Roteamento** — escolhe o agente: qualificador (compra/aluguel), especialista em investimento, agendamento (quando qualificado) ou encerramento.
5. **Consolidação** — recalcula o score e, ao virar qualificado ou agendado, gera o resumo para o corretor.

Como a intenção é reavaliada a cada mensagem sobre o histórico completo, se o cliente começa falando de compra e passa a falar de investimento, o roteador troca de agente sem perder os dados.

## Humanização e contexto conversacional

A persona "Lia" (`src/graph/prompts.py`) define:
- **Estilo WhatsApp:** no máximo 3 frases, sem markdown, no máximo 1 emoji.
- **Uma pergunta por vez**, sempre depois de reagir ao que o cliente disse.
- **Nunca repetir perguntas:** cada agente recebe "o que já sabemos" e "o que falta, em ordem de prioridade", calculados a partir da extração, e não apenas o histórico.
- **Perguntas contextuais:** em vez de "qual sua faixa de preço?", algo como "pra eu filtrar as melhores opções, até quanto você pensa em investir?". No aluguel, o valor é tratado como mensal.
- **Transparência:** ela se apresenta como assistente virtual.

O histórico é enviado como mensagens de chat (`HumanMessage` / `AIMessage`), na janela das últimas 30 mensagens, e fica persistido no SQLite. Por isso a conversa continua de onde parou mesmo dias depois ou após reiniciar o sistema.

## RAG: recuperação de imóveis

A busca (`src/tools/imoveis.py`) é **híbrida**:
1. **Filtros estruturados** sobre os dados extraídos: finalidade (venda/aluguel), tipo, quartos ≥ desejado, preço ≤ máximo + 10%, região (bairro ou zona).
2. **Ranking:** 60% similaridade semântica (cosseno entre o embedding das preferências do cliente e o de cada imóvel) + 40% aderência ao orçamento.
3. Regiões que não são bairro nem zona ("perto do Ibirapuera") viram consulta semântica: as descrições citam pontos de referência, então Moema aparece primeiro.
4. Sem opções na região, o agente avisa que está mostrando opções de outras regiões.
5. Para investimento: imóveis à venda dentro do ticket, filtrados por perfil (residencial/comercial) e ordenados por rentabilidade bruta estimada.

Os imóveis recuperados entram no prompt do agente de agendamento, que **só pode citar esses imóveis** (geração aumentada por recuperação). Isso evita que o modelo invente endereços ou preços. Os embeddings da base são calculados uma vez e guardados em cache; se não houver chave ou rede, a busca cai para similaridade léxica.

As políticas da imobiliária (formas de pagamento, garantias de locação, horários) ficam em `src/data/imobiliaria.md` e entram no contexto da persona, para que dúvidas comuns sejam respondidas com informação verdadeira.

## Score do lead (explicável)

O score (`src/services/score.py`) é por regras, de propósito: o corretor vê **por que** o lead está quente.

| Critério | Pontos |
|---|---|
| Intenção identificada | +10 |
| Dados de qualificação preenchidos | até +35 (proporcional) |
| Urgência alta / média / baixa | +25 / +12 / +3 |
| Ticket de investimento ≥ R$ 1 milhão | +10 |
| Forma de pagamento definida | +5 |
| Cliente se identificou | +5 |
| Engajamento (mensagens do cliente) | até +10 |
| Qualificação completa / visita agendada | +10 / +20 |

Quente ≥ 70, morno ≥ 40, frio < 40 (máximo 100). Lead perdido = 0.

## Agendamento

O agente de agendamento oferece **3 horários numerados** de corretores com a especialidade certa (residencial ou investimento), em dias diferentes, dentro do expediente e com pelo menos 3 h de antecedência. O cliente responde em linguagem natural ("pode ser a segunda", "terça às 14h") e a extração converte isso no número da opção. Se pedir outro dia ou período ("sábado de manhã"), novos horários são filtrados. A gravação usa uma restrição única no banco para evitar conflito de agenda.

## Follow-up

O agente de follow-up recebe a conversa, os dados coletados, o que faltava descobrir, há quanto tempo o cliente está em silêncio e qual é a tentativa (1, 2 ou 3). O tom muda por tentativa: leve, depois traz uma novidade, e na última é breve e deixa a porta aberta. Sempre que possível usa um imóvel compatível como gancho. Ele não diz que é uma mensagem automática nem cobra resposta.

## Guardrails

- Padrões de prompt injection em PT e EN ("ignore suas instruções", "mostre seu prompt", "a partir de agora você é…"), calibrados com testes para não bloquear frases legítimas como "esquece tudo, quero alugar".
- CPF e cartão são removidos da mensagem antes de chegar ao LLM.
- O prompt proíbe inventar dados, pedir documentos e revelar instruções.

## Avaliação

- 28 testes automatizados com LLM falso validam o comportamento determinístico: roteamento, etapas, agenda, score, RAG, follow-up, segurança, API e WhatsApp.
- A qualidade das respostas do LLM é avaliada manualmente com o roteiro de demonstração. Com o LangSmith ativo, cada execução fica rastreável (prompts, latência, tokens) para comparar versões de prompt.

## Limitações conhecidas

- O LLM pode errar a extração em frases ambíguas; o impacto é limitado porque o agente pergunta o que falta e o cliente pode corrigir (a informação mais recente prevalece).
- O guardrail por padrões não cobre todos os ataques possíveis; as regras do prompt são a segunda camada.
- A rentabilidade dos imóveis é uma estimativa bruta simulada, e o agente é instruído a deixar isso claro.
