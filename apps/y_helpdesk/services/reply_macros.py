"""
Reply Macros Service.

Template-based quick replies with variable substitution for helpdesk.
Stores macros in TypeAssist.other_data['reply_macros'].

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling

@ontology(
    domain="helpdesk",
    purpose="Template replies with variable substitution",
    business_value="Faster response times, consistent messaging",
    criticality="low",
    tags=["helpdesk", "automation", "templates"]
)
"""

import logging
import re
from typing import Dict, List, Optional
from django.core.exceptions import ValidationError

logger = logging.getLogger('y_helpdesk.reply_macros')

__all__ = ['ReplyMacroService']


class ReplyMacroService:
    """Manage and render reply macros with variable substitution."""
    
    @classmethod
    def create_macro(
        cls,
        typeassist_obj,
        macro_key: str,
        template: str,
        description: str = ""
    ) -> None:
        """
        Store reply macro in TypeAssist.other_data.
        
        Args:
            typeassist_obj: TypeAssist instance
            macro_key: Unique macro identifier
            template: Reply template with {{variables}}
            description: Macro description
        """
        if not hasattr(typeassist_obj, 'other_data') or typeassist_obj.other_data is None:
            typeassist_obj.other_data = {}
        
        if 'reply_macros' not in typeassist_obj.other_data:
            typeassist_obj.other_data['reply_macros'] = {}
        
        typeassist_obj.other_data['reply_macros'][macro_key] = {
            'template': template,
            'description': description,
            'created_at': str(typeassist_obj.cdtz) if hasattr(typeassist_obj, 'cdtz') else None
        }
        
        typeassist_obj.save()
    
    @classmethod
    def render_macro(
        cls,
        typeassist_obj,
        macro_key: str,
        variables: Dict[str, str]
    ) -> str:
        """
        Render macro with variable substitution.
        
        Args:
            typeassist_obj: TypeAssist instance
            macro_key: Macro identifier
            variables: Dict of variable replacements
            
        Returns:
            Rendered template string
            
        Raises:
            ValidationError: If macro not found
        """
        if not hasattr(typeassist_obj, 'other_data') or 'reply_macros' not in typeassist_obj.other_data:
            raise ValidationError(f"Macro '{macro_key}' not found")
        
        macros = typeassist_obj.other_data['reply_macros']
        if macro_key not in macros:
            raise ValidationError(f"Macro '{macro_key}' not found")
        
        template = macros[macro_key]['template']
        
        rendered = template
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            rendered = rendered.replace(placeholder, str(var_value))
        
        return rendered
    
    @classmethod
    def list_macros(cls, typeassist_obj) -> List[Dict]:
        """
        List all available macros.
        
        Returns:
            List of macro metadata dicts
        """
        if not hasattr(typeassist_obj, 'other_data') or 'reply_macros' not in typeassist_obj.other_data:
            return []
        
        macros = typeassist_obj.other_data['reply_macros']
        
        return [
            {
                'key': key,
                'description': data.get('description', ''),
                'template': data.get('template', ''),
                'variables': cls._extract_variables(data.get('template', ''))
            }
            for key, data in macros.items()
        ]
    
    @classmethod
    def _extract_variables(cls, template: str) -> List[str]:
        """Extract variable names from template."""
        return re.findall(r'\{\{(\w+)\}\}', template)
    
    @classmethod
    def delete_macro(cls, typeassist_obj, macro_key: str) -> None:
        """Delete macro from TypeAssist."""
        if hasattr(typeassist_obj, 'other_data') and 'reply_macros' in typeassist_obj.other_data:
            typeassist_obj.other_data['reply_macros'].pop(macro_key, None)
            typeassist_obj.save()
