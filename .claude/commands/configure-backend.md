# Contexto do Projeto: Backend Voice Agent (Python)
Você deve construir o "coração" de um agente de voz para o teste da Aloware. O objetivo é um agente que funcione via telefone/voz em tempo real.

## Requisitos Técnicos
- **Linguagem:** Python 3.10+
- **Framework:** LiveKit Agents SDK (escolhido pela robustez em WebRTC).
- **Provedores:** OpenAI (LLM).
- **Cenário:** Recepção de uma Clínica Médica (Aloware Health).

## Tarefas Específicas
1. **Estrutura de Configuração:**
   - Crie um arquivo `config.json` que armazene: `system_prompt`, `agent_name`, `greeting`, `voice_id` e `enabled_tools`.
   - O agente deve recarregar essas configurações a cada nova conexão/chamada.

2. **Implementação de 3 Tools (Funções):**
   - `check_availability(date)`: Simular consulta em um calendário (retornar horários fictícios).
   - `book_appointment(date, time, patient_name)`: Simular a marcação (apenas logar o sucesso).
   - `transfer_to_human()`: Simular a transferência da chamada.

3. **Guardrails:**
   - Implementar um filtro de conteúdo ou instrução rígida no `system_prompt` para que o agente nunca discuta diagnósticos médicos ou temas fora da agenda da clínica.

4. **Integração LiveKit:**
   - Configure o `WorkerOptions` e o `VoiceAssistant`.
   - Garanta que o agente use `VAD` (Voice Activity Detection) para não interromper o usuário de forma grosseira.

5. **API de Sincronização:**
   - Crie um endpoint simples usando `FastAPI` para que o Frontend possa dar um POST e atualizar o `config.json`.

## Output Esperado
- Um script `agent.py` principal.
- Um arquivo `tools.py` com as funções decoradas para o LLM.
- Um `requirements.txt` com as dependências necessárias.