"""Document generator for Argus governance toolkit."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class DocumentGenerator:
    """Generates governance decision documents."""
    
    TEMPLATES = {
        'architectural': {
            'title': 'Architectural Decision Record',
            'sections': [
                'Context',
                'Decision',
                'Rationale',
                'Consequences',
                'Alternatives Considered'
            ]
        },
        'technical': {
            'title': 'Technical Design Document',
            'sections': [
                'Overview',
                'Requirements',
                'Design',
                'Implementation Plan',
                'Testing Strategy'
            ]
        },
        'security': {
            'title': 'Security Assessment',
            'sections': [
                'Threat Model',
                'Risk Assessment',
                'Mitigation Strategy',
                'Implementation',
                'Monitoring'
            ]
        }
    }
    
    def generate_document(self, doc_type: str, output_path: Path, format: str = 'markdown') -> Path:
        """Generate a governance document template.
        
        Args:
            doc_type: Type of document (architectural, technical, security)
            output_path: Directory to save the document
            format: Output format (markdown or json)
            
        Returns:
            Path to the generated document
        """
        if doc_type not in self.TEMPLATES:
            raise ValueError(f"Unknown document type: {doc_type}")
        
        template = self.TEMPLATES[doc_type]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format == 'markdown':
            return self._generate_markdown(doc_type, template, output_path, timestamp)
        elif format == 'json':
            return self._generate_json(doc_type, template, output_path, timestamp)
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def _generate_markdown(self, doc_type: str, template: Dict[str, Any], 
                          output_path: Path, timestamp: str) -> Path:
        """Generate markdown format document."""
        filename = f"{doc_type}_{timestamp}.md"
        filepath = output_path / filename
        
        content = f"# {template['title']}\n\n"
        content += f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n"
        content += f"**Type:** {doc_type.capitalize()}\n"
        content += f"**Status:** Draft\n\n"
        content += "---\n\n"
        
        for section in template['sections']:
            content += f"## {section}\n\n"
            content += "_[To be completed]_\n\n"
        
        filepath.write_text(content)
        return filepath
    
    def _generate_json(self, doc_type: str, template: Dict[str, Any],
                      output_path: Path, timestamp: str) -> Path:
        """Generate JSON format document."""
        filename = f"{doc_type}_{timestamp}.json"
        filepath = output_path / filename
        
        document = {
            'metadata': {
                'title': template['title'],
                'type': doc_type,
                'created': datetime.now().isoformat(),
                'status': 'draft',
                'version': '1.0'
            },
            'sections': {section: '' for section in template['sections']}
        }
        
        filepath.write_text(json.dumps(document, indent=2))
        return filepath
