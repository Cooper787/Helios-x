"""Document validator for Argus governance toolkit."""

import json
from pathlib import Path
from typing import Tuple, List, Dict, Any
import re


class DocumentValidator:
    """Validates governance documents against standards."""
    
    REQUIRED_SECTIONS = {
        'architectural': ['Context', 'Decision', 'Rationale', 'Consequences'],
        'technical': ['Overview', 'Requirements', 'Design'],
        'security': ['Threat Model', 'Risk Assessment', 'Mitigation Strategy']
    }
    
    REQUIRED_METADATA = ['title', 'type', 'created', 'status']
    
    def validate_document(self, doc_path: Path) -> Tuple[bool, List[str]]:
        """Validate a governance document.
        
        Args:
            doc_path: Path to the document to validate
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        if not doc_path.exists():
            return False, [f"Document not found: {doc_path}"]
        
        if doc_path.suffix == '.md':
            errors.extend(self._validate_markdown(doc_path))
        elif doc_path.suffix == '.json':
            errors.extend(self._validate_json(doc_path))
        else:
            errors.append(f"Unsupported file format: {doc_path.suffix}")
        
        return len(errors) == 0, errors
    
    def _validate_markdown(self, doc_path: Path) -> List[str]:
        """Validate markdown format document."""
        errors = []
        content = doc_path.read_text()
        
        # Check for title
        if not re.search(r'^# .+', content, re.MULTILINE):
            errors.append("Missing main title (# heading)")
        
        # Check for metadata
        if '**Date:**' not in content:
            errors.append("Missing Date metadata")
        if '**Type:**' not in content:
            errors.append("Missing Type metadata")
        if '**Status:**' not in content:
            errors.append("Missing Status metadata")
        
        # Extract document type
        type_match = re.search(r'\*\*Type:\*\*\s+(\w+)', content)
        if type_match:
            doc_type = type_match.group(1).lower()
            if doc_type in self.REQUIRED_SECTIONS:
                # Check for required sections
                for section in self.REQUIRED_SECTIONS[doc_type]:
                    if f"## {section}" not in content:
                        errors.append(f"Missing required section: {section}")
        
        # Check for incomplete sections
        if content.count('[To be completed]') > 3:
            errors.append("Too many incomplete sections")
        
        return errors
    
    def _validate_json(self, doc_path: Path) -> List[str]:
        """Validate JSON format document."""
        errors = []
        
        try:
            with open(doc_path, 'r') as f:
                document = json.load(f)
        except json.JSONDecodeError as e:
            return [f"Invalid JSON format: {e}"]
        
        # Check metadata
        if 'metadata' not in document:
            errors.append("Missing metadata section")
        else:
            metadata = document['metadata']
            for field in self.REQUIRED_METADATA:
                if field not in metadata:
                    errors.append(f"Missing metadata field: {field}")
        
        # Check sections
        if 'sections' not in document:
            errors.append("Missing sections")
        else:
            doc_type = document.get('metadata', {}).get('type')
            if doc_type in self.REQUIRED_SECTIONS:
                sections = document['sections']
                for required_section in self.REQUIRED_SECTIONS[doc_type]:
                    if required_section not in sections:
                        errors.append(f"Missing required section: {required_section}")
        
        return errors
    
    def validate_directory(self, dir_path: Path) -> Dict[str, Tuple[bool, List[str]]]:
        """Validate all governance documents in a directory.
        
        Args:
            dir_path: Path to directory containing documents
            
        Returns:
            Dictionary mapping file paths to validation results
        """
        results = {}
        
        for doc_path in dir_path.rglob('*.md'):
            results[str(doc_path)] = self.validate_document(doc_path)
        
        for doc_path in dir_path.rglob('*.json'):
            results[str(doc_path)] = self.validate_document(doc_path)
        
        return results
