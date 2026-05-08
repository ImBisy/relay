#!/usr/bin/env python3
"""
Simple test script for Relay components.
"""
import sys
sys.path.insert(0, '/Users/charlieichikowitz/CascadeProjects/relay')

def test_intent_parser():
    """Test the intent parser."""
    print("\n=== Testing Intent Parser ===\n")
    
    from src.intent.parser import IntentParser
    from src.intent.models import ActionType
    
    parser = IntentParser()
    
    test_inputs = [
        "Remind me to call mom at 5pm",
        "Send an email to Work Email about the meeting",
        "Schedule a meeting tomorrow at 2pm",
        "Take a note: The API key is in the vault",
        "Set a 10 minute timer",
        "Open Safari",
        "What's the weather like?",
    ]
    
    for text in test_inputs:
        result = parser.parse(text)
        print(f"Input: {text}")
        print(f"  → Intent: {result.intent}")
        print(f"  → Action: {result.action_type.value}")
        print(f"  → Confidence: {result.confidence:.2f}")
        print(f"  → Entities: {result.entities}")
        print()


def test_tools():
    """Test the tools."""
    print("\n=== Testing Tools ===\n")
    
    from src.tools.notes import NotesTool
    from src.tools.timer import TimerTool
    
    # Test Notes
    print("Testing Notes Tool:")
    notes = NotesTool()
    result = notes.execute({
        'note_text': 'Test note from Relay',
        'content': 'Test note from Relay'
    })
    print(f"  Add note: {result.status.value} - {result.message}")
    
    # Test list notes
    result = notes.execute({'note_action': 'list', 'limit': 5})
    print(f"  List notes: {result.status.value} - {result.message}")
    
    # Test Timer
    print("\nTesting Timer Tool:")
    timer = TimerTool()
    result = timer.execute({
        'duration_minutes': 1,
        'timer_action': 'create'
    })
    print(f"  Create timer: {result.status.value} - {result.message}")
    
    result = timer.execute({'timer_action': 'status'})
    print(f"  Timer status: {result.status.value} - {result.message}")


def test_personality():
    """Test the personality engine."""
    print("\n=== Testing Personality Engine ===\n")
    
    from src.personality.responder import PersonalityEngine, ResponseContext
    
    personality = PersonalityEngine()
    
    contexts = [
        ResponseContext(action_type='reminder', success=True, requires_confirmation=False),
        ResponseContext(action_type='email', success=True, requires_confirmation=True),
        ResponseContext(action_type='calendar', success=True, requires_confirmation=False, urgent=False),
        ResponseContext(action_type='note', success=True, requires_confirmation=False),
    ]
    
    for i, ctx in enumerate(contexts):
        response = personality.generate_response(ctx)
        print(f"Response {i+1} ({ctx.action_type}): {response}")
    
    print(f"\nGreeting: {personality.greeting()}")
    print(f"Clarification: {personality.clarification('unclear time')}")


def test_orchestrator():
    """Test the orchestrator."""
    print("\n=== Testing Orchestrator ===\n")
    
    from src.core.orchestrator import RelayOrchestrator
    
    orchestrator = RelayOrchestrator()
    
    # Mock response callback
    responses = []
    orchestrator.set_response_callback(lambda text: responses.append(text))
    
    test_commands = [
        "remind me to buy milk",
        "take a note: review design mockups",
        "what's on my calendar today",
    ]
    
    for cmd in test_commands:
        print(f"Command: {cmd}")
        response = orchestrator.process_input(cmd)
        print(f"  → {response}\n")


if __name__ == '__main__':
    print("🤖 Relay Component Tests\n")
    print("=" * 50)
    
    try:
        test_intent_parser()
    except Exception as e:
        print(f"Intent parser test failed: {e}")
    
    try:
        test_personality()
    except Exception as e:
        print(f"Personality test failed: {e}")
    
    try:
        test_tools()
    except Exception as e:
        print(f"Tools test failed: {e}")
    
    try:
        test_orchestrator()
    except Exception as e:
        print(f"Orchestrator test failed: {e}")
    
    print("\n" + "=" * 50)
    print("Tests complete!")
