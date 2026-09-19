# 🏠 Agente SDR Imobiliário — Tech Challenge Fase 5

Prova de conceito de um agente de IA para qualificação automática de leads imobiliários, construído com LangGraph, LangChain e OpenAI.

## Arquitetura

Agente multiagente com roteamento dinâmico por intenção:

```
Lead ──▶ Roteador (classifica intenção)
              │
    ┌─────────┴─────────┐
    ▼                     ▼
Agente Qualificador   Agente Especialista
(compra/aluguel)       (investimento)
    │                     │
    └─────────┬───────────┘
              ▼
        Resposta ao lead
```

Cada mensagem do lead é reavaliada pelo roteador, permitindo trocar de agente dinamicamente se a intenção mudar no meio da conversa.

## Estrutura do projeto

```
.
├── app.py                  # Interface Streamlit (chat + dashboard)
├── requirements.txt
├── .env.example
└── src/
    ├── config.py            # Configuração (LLM, chaves)
    ├── llm/
    │   └── client.py        # Cliente do modelo de linguagem
    ├── graph/
    │   ├── state.py         # Estado compartilhado entre os agentes
    │   ├── nodes.py         # Roteador + agentes + resumo
    │   └── sdr_graph.py     # Montagem do grafo LangGraph
    ├── data/                # Base simulada de imóveis (CSV)
    ├── tools/               # Funções de busca de imóveis e agendamento
    └── memory/              # Memória de sessão por lead
```

## Como executar

```bash
# 1. Clonar o repositório
git clone https://github.com/joaovpires/8iadt-hackaton-fase5.git
cd 8iadt-hackaton-fase5

# 2. Criar ambiente virtual (opcional, mas recomendado)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env e adicione sua OPENAI_API_KEY

# 5. Rodar a aplicação
streamlit run app.py
```

## Funcionalidades

- [x] Atendimento conversacional humanizado
- [x] Qualificação de leads (região, preço, quartos, urgência)
- [x] Identificação de intenção (compra, aluguel, investimento)
- [x] Continuidade da conversa (memória de sessão)
- [ ] Integração com base simulada de imóveis
- [ ] Agendamento de reuniões
- [ ] Resumo inteligente para o corretor
- [ ] Dashboard de acompanhamento de leads

## Time

| Pessoa | Responsabilidade |
|---|---|
| Pessoa 1 | Orquestração do agente (LangGraph) + IA conversacional |
| Pessoa 2 | Base de imóveis + busca |
| Pessoa 3 | Memória de sessão + agendamento |
| Pessoa 4 | Interface (Streamlit) + dashboard + demo |

## Limitações conhecidas

- Memória de sessão é volátil (não persiste entre reinicializações da aplicação)
- Agendamento é simulado (não integra com calendário real)
- Base de imóveis é simulada/sintética, não reflete dados reais de mercado