"""
OpenRouter client for complex reasoning and fallback processing.
"""
import json
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class OpenRouterMessage:
    """Message format for OpenRouter API."""
    role: str  # 'system', 'user', 'assistant'
    content: str


class OpenRouterClient:
    """
    OpenRouter API client for secondary reasoning layer.
    
    Used for:
    - Ambiguous intent parsing
    - Complex multi-step reasoning
    - Extracting structured data from messy input
    """
    
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1",
                 model: str = "anthropic/claude-3.5-sonnet"):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key
            base_url: API base URL
            model: Model identifier
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://relay-assistant.local",
            "X-Title": "Relay Assistant",
        }
    
    def chat(self, messages: List[OpenRouterMessage], 
             temperature: float = 0.3,
             max_tokens: int = 500) -> Optional[str]:
        """
        Send chat completion request.
        
        Args:
            messages: List of messages
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Response text or None if failed
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            return data['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            print(f"OpenRouter API error: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"Error parsing OpenRouter response: {e}")
            return None
    
    def parse_intent(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Use OpenRouter to parse ambiguous intent.
        
        Args:
            text: User input text
            
        Returns:
            Structured intent dict or None
        """
        system_prompt = """You are an intent parsing system for a voice assistant.
Parse the user input into a structured JSON response.

Output format:
{
  "intent": "brief description",
  "action_type": "email|calendar|reminder|note|timer|system|web|query|unknown",
  "entities": {
    // Extract all relevant entities
  },
  "confidence": 0.0-1.0,
  "requires_confirmation": true/false,
  "clarification_needed": "if confidence < 0.7, what should we ask the user?"
}

Rules:
- Be precise in entity extraction
- If ambiguous, set requires_confirmation to true
- Confidence should reflect parsing certainty
- Use null for missing optional fields"""

        messages = [
            OpenRouterMessage(role="system", content=system_prompt),
            OpenRouterMessage(role="user", content=f"Parse this input: '{text}'"),
        ]
        
        response = self.chat(messages, temperature=0.1, max_tokens=300)
        
        if not response:
            return None
        
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            return json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            print(f"Failed to parse OpenRouter intent response: {e}")
            print(f"Response: {response}")
            return None
    
    def generate_response(self, context: str, tone: str = "calm_efficient") -> Optional[str]:
        """
        Generate a response in Relay style tone.
        
        Args:
            context: Context for the response
            tone: Desired tone (calm_efficient, witty, apologetic)
            
        Returns:
            Generated response text
        """
        tone_instructions = {
            "calm_efficient": "Respond in a calm, efficient manner. Be concise and professional.",
            "witty": "Add a subtle, dry wit. Be clever but not disruptive. Occasional light sarcasm.",
            "apologetic": "Acknowledge the issue politely. Offer a solution. Be helpful and composed.",
        }
        
        system_prompt = f"""You are Relay, a calm and capable AI assistant.
{tone_instructions.get(tone, tone_instructions['calm_efficient'])}

Guidelines:
- Keep responses brief (1-2 sentences)
- Never be overly verbose
- Sound in control and composed
- Avoid excessive politeness or enthusiasm"""

        messages = [
            OpenRouterMessage(role="system", content=system_prompt),
            OpenRouterMessage(role="user", content=context),
        ]
        
        return self.chat(messages, temperature=0.5, max_tokens=150)
    
    def extract_structured_data(self, text: str, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract structured data from text according to schema.
        
        Args:
            text: Input text to parse
            schema: Dict describing expected fields and types
            
        Returns:
            Extracted data or None
        """
        schema_desc = json.dumps(schema, indent=2)
        
        system_prompt = f"""Extract structured data from the user input.

Expected schema:
{schema_desc}

Output only valid JSON matching the schema. Use null for missing fields."""

        messages = [
            OpenRouterMessage(role="system", content=system_prompt),
            OpenRouterMessage(role="user", content=text),
        ]
        
        response = self.chat(messages, temperature=0.1, max_tokens=300)
        
        if not response:
            return None
        
        try:
            # Extract JSON
            json_str = response
            if "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            return json.loads(json_str.strip())
        except json.JSONDecodeError:
            return None
    
    def health_check(self) -> bool:
        """Check if API is accessible."""
        try:
            # Try a simple request
            messages = [OpenRouterMessage(role="user", content="Hi")]
            response = self.chat(messages, max_tokens=10)
            return response is not None
        except Exception:
            return False
