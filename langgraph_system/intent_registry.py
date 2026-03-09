import yaml
import os
from typing import List, Dict, Any
from langchain_core.tools import BaseTool


class IntentRegistry:
    """
    Loads the intents.yaml config and exposes its data to the LangGraph.
    
    This is the bridge between the YAML config and the Python code.
    When a new MCP or intent is added, only the YAML file needs to change.
    This class itself never needs to be modified.
    """

    def __init__(self, yaml_path: str | None = None):
        if yaml_path is None:
            yaml_path = os.path.join(os.path.dirname(__file__), "knowledge", "intents.yaml")
        
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        self._intents: Dict[str, Any] = config.get("intents", {})

    def get_intent_names(self) -> List[str]:
        """Returns the list of valid intent names, e.g. ['analyze', 'info_only', ...]"""
        return list(self._intents.keys())

    def get_intent_descriptions(self) -> str:
        """
        Returns a formatted string of all intents and descriptions.
        Used to build the Intent Router prompt dynamically.
        """
        lines = []
        for name, data in self._intents.items():
            desc = data.get("description", "")
            lines.append(f"- '{name}': {desc}")
        return "\n".join(lines)

    def get_few_shot_examples(self) -> str:
        """
        Returns formatted few-shot examples for all intents.
        This significantly helps small models stay on track.
        """
        lines = []
        for name, data in self._intents.items():
            for example in data.get("examples", []):
                lines.append(f'Kullanıcı: "{example}" → {name}')
        return "\n".join(lines)

    def get_tools_for_intent(self, intent: str, all_tools: List[BaseTool]) -> List[BaseTool]:
        """
        Filters the full list of loaded MCP tools down to only
        the subset relevant to the given intent.
        
        This is the key to scaling: the model sees 8-12 tools, not 100.
        """
        if intent not in self._intents:
            # Fallback: return a minimal set or nothing
            print(f"⚠️ Unknown intent '{intent}', returning empty tool list.")
            return []

        allowed_tool_names = set(self._intents[intent].get("tools", []))
        filtered = [t for t in all_tools if t.name in allowed_tool_names]

        print(f"   🔧 Intent '{intent}' → Loaded {len(filtered)} tools: {[t.name for t in filtered]}")
        return filtered
