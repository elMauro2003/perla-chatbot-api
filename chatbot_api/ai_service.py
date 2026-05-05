import os
from typing import Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    user_input: str
    full_context: str
    bot_response: str
    needs_human: bool
    confidence_score: float

class ChatbotService:
    def __init__(self, knowledge_file="conocimiento.txt"):
        self.knowledge_file = knowledge_file
        self.full_context = self._load_knowledge()
        
        self.llm = ChatOpenAI(
            model="deepseek/deepseek-chat",
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0,        # CERO creatividad pa q no c coma tokens 
            max_tokens=800,       
        )
        
        self.graph = self._build_graph()
        logger.info("✅ ChatbotService inicializado correctamente :)")
    
    def _load_knowledge(self) -> str:
        """ Carga TODO el archivo de conocimiento para que ande en full contexto dp los tokens asere :( """
        try:
            possible_paths = [
                self.knowledge_file,
                os.path.join(os.path.dirname(__file__), self.knowledge_file),
                os.path.join(os.path.dirname(__file__), '..', self.knowledge_file),
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    token_estimate = len(content.split()) * 1.3
                    logger.info(f"✅ Conocimiento cargado desde {path}")
                    logger.info(f"📊 Tamaño: {len(content)} caracteres, ~{token_estimate:.0f} tokens")
                    
                    if token_estimate > 6000:
                        logger.warning("⚠️ El archivo es grande. Podría exceder límites del modelo gratuito")
                    
                    return content
            
            logger.error("❌ No se encontró el archivo de conocimiento")
            return self._get_default_knowledge()
            
        except Exception as e:
            logger.error(f"❌ Error cargando conocimiento: {e}")
            return self._get_default_knowledge()
    
    def _get_default_knowledge(self) -> str:
        """Conocimiento por defecto (solo emergencia)"""
        return """## PERLA SOLUTIONS
- WhatsApp: +53 58521602
- Consulta inicial gratuita
- Servicios: páginas web, chatbots IA, software a medida"""
    
    def reload_knowledge(self):
        self.full_context = self._load_knowledge()
        logger.info("🔄 Conocimiento recargado")
    
    def _build_graph(self):
        workflow = StateGraph(ChatState)
        
        workflow.add_node("prepare_context", self._prepare_context)
        workflow.add_node("generate_response", self._generate_response)
        
        workflow.add_edge(START, "prepare_context")
        workflow.add_edge("prepare_context", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    def _prepare_context(self, state: ChatState) -> ChatState:
        state["full_context"] = self.full_context
        logger.info(f"📝 Preparando respuesta para: '{state['user_input'][:80]}...'")
        return state
    
    def _generate_response(self, state: ChatState) -> ChatState:
        """
        Genera respuesta usando un prompt diseñado para:
        1. Usar SOLO información del contexto
        2. Auto-verificar su propia respuesta
        3. Ser honesto cuando no sabe algo
        """
        
        system_prompt = f"""Eres el asistente virtual oficial de Perla Solutions, una empresa de tecnología y desarrollo de software en Cienfuegos, Cuba.

        TU ÚNICA FUENTE DE INFORMACIÓN es el documento "INFORMACIÓN DE PERLA SOLUTIONS" que se proporciona abajo. No tienes acceso a internet ni a ninguna otra fuente.

        REGLAS OBLIGATORIAS:

        1. LEE PRIMERO LA PREGUNTA, luego BUSCA en la información proporcionada si existe respuesta.

        2. SI LA INFORMACIÓN EXISTE:
           - Responde de forma clara, amable y completa
           - Usa tus propias palabras pero SIN inventar nada que no esté escrito
           - Incluye detalles relevantes que estén en la información

        3. SI LA INFORMACIÓN NO EXISTE:
           - Di EXACTAMENTE: "Gracias por tu interés. Actualmente no tengo esa información en mi base de conocimiento. ¿Te gustaría que te contacte un miembro de nuestro equipo para ayudarte personalmente?"
           - NO inventes nada
           - NO hagas suposiciones

        4. NUNCA USES FRASES COMO:
           - "Tal vez", "probablemente", "creo que", "posiblemente"
           - "Según nuestro sitio web" (no tienes acceso a internet)
           - "Deberías consultar con..." seguido de información inventada

        5. SI EL CLIENTE PREGUNTA POR PRECIOS:
           - Indica que los precios son personalizados
           - Menciona que hay una consulta inicial gratuita
           - NO des precios que no estén explícitamente en la información

        6. SIEMPRE que sea relevante, recuerda:
           - Ofrecemos consulta inicial gratuita sin compromiso
           - Nuestro WhatsApp es +53 58521602
           - Trabajamos de forma remota con toda Cuba y el extranjero

        ========================================
        INFORMACIÓN DE PERLA SOLUTIONS:
        ========================================
        {state['full_context']}
        ========================================

        ANTES DE RESPONDER, VERIFICA MENTALMENTE:
        ¿Está esta información en el documento de arriba?
        - SI → Responde con confianza
        - NO → Usa la frase de "no tengo esa información"
        """

        # Construir mensajes
        messages = [SystemMessage(content=system_prompt)]
        
        # Agregar historial reciente (últimos 4 mensajes) si existe
        if state.get("messages") and len(state["messages"]) > 0:
            messages.extend(state["messages"][-4:])
        
        # Agregar pregunta actual
        messages.append(HumanMessage(content=state["user_input"]))
        
        try:
            logger.info("🤖 Llamando al LLM...")
            response = self.llm.invoke(messages)
            state["bot_response"] = response.content
            
            # Auto-evaluar la confianza basado en la respuesta
            response_lower = response.content.lower()
            
            # Indicadores de que el LLM no encontró la información
            no_info_phrases = [
                "no tengo esa información",
                "no encuentro",
                "no está en mi base",
                "no puedo responder",
                "actualmente no tengo"
            ]
            
            # Indicadores de incertidumbre (alucinación potencial)
            uncertainty_phrases = [
                "tal vez",
                "probablemente",
                "creo que",
                "posiblemente",
                "quizás"
            ]
            
            if any(phrase in response_lower for phrase in no_info_phrases):
                state["confidence_score"] = 0.9  # Es válido decir "no sé"
                state["needs_human"] = True
                logger.info("ℹ️ El LLM indicó que no tiene la información")
            elif any(phrase in response_lower for phrase in uncertainty_phrases):
                state["confidence_score"] = 0.3  # Baja confianza, posible alucinación
                state["needs_human"] = True
                logger.warning("⚠️ Detectada posible alucinación en la respuesta")
            else:
                state["confidence_score"] = 0.9  # Alta confianza
                state["needs_human"] = False
                logger.info("✅ Respuesta generada con alta confianza")
            
            logger.info(f"📤 Respuesta ({len(response.content)} caracteres): {response.content[:150]}...")
            
        except Exception as e:
            logger.error(f"❌ Error generando respuesta: {e}")
            state["bot_response"] = (
                "Lo siento, ocurrió un error técnico al procesar tu consulta. "
                "Por favor, contáctanos directamente por WhatsApp al +53 58521602 "
                "y te atenderemos personalmente."
            )
            state["confidence_score"] = 0.0
            state["needs_human"] = True
        
        return state
    
    def chat(self, user_message: str, history: list = None) -> dict:
        """Interfaz principal de chat"""
        try:
            logger.info(f"📨 Nueva consulta: '{user_message[:100]}...'")
            
            initial_state = {
                "messages": history or [],
                "user_input": user_message,
                "full_context": self.full_context,
                "bot_response": "",
                "needs_human": False,
                "confidence_score": 1.0,
            }
            
            result = self.graph.invoke(initial_state)
            
            response_data = {
                "success": True,
                "message": result["bot_response"],
                "needs_human": result.get("needs_human", False),
                "confidence": result.get("confidence_score", 1.0),
                "method": "direct_context"
            }
            
            logger.info(f"✅ Respuesta exitosa (confianza: {response_data['confidence']})")
            return response_data
            
        except Exception as e:
            logger.error(f"❌ Error fatal en chat: {e}", exc_info=True)
            return {
                "success": False,
                "message": (
                    "Lo siento, ocurrió un error inesperado. "
                    "Por favor, contáctanos por WhatsApp al +53 58521602 "
                    "para recibir atención personalizada."
                ),
                "needs_human": True,
                "confidence": 0.0,
                "method": "error_fallback"
            }

# Instancia global ;)
chatbot_service = ChatbotService()