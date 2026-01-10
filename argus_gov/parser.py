"""Document parser for Argus governance toolkit."""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, List
import re
from datetime import datetime


class DocumentParser:
    """Parses governance documents and extracts metadata."""
    
    def parse_document(self, doc_path: Path) -> Dict[str, Any]:
        """Parse a governance document and extract metadata.
        
        Args:
            doc_path: Path to the document to parse
            
        Returns:
            Dictionary containing parsed metadata and content
        """
        if not doc_path.exists():
            raise FileNotFoundError(f"Document not found: {doc_path}")
        
        if doc_path.suffix == '.md':
            return self._parse_markdown(doc_path)
        elif doc_path.suffix == '.json':
            return self._parse_json(doc_path)
        else:
            raise ValueError(f"Unsupported file format: {doc_path.suffix}")
    
    def _parse_markdown(self, doc_path: Path) -> Dict[str, Any]:
        """Parse markdown governance document."""
        content = doc_path.read_text()
        
        # Extract title
        title_match = re.search(r'^# (.+)', content, re.MULTILINE)
        title = title_match.group(1) if title_match else doc_path.stem
        
        # Extract metadata fields
        metadata = {
            'title': title,
            'path': str(doc_path),
            'format': 'markdown'
        }
        
        # Parse metadata block
        date_match = re.search(r'\*\*Date:\*\*\s+([\d-]+)', content)
        if date_match:
            metadata['date'] = date_match.group(1)
        
        type_match = re.search(r'\*\*Type:\*\*\s+(\w+)', content)
        if type_match:
            metadata['type'] = type_match.group(1).lower()
        
        status_match = re.search(r'\*\*Status:\*\*\s+(\w+)', content)
        if status_match:
            metadata['status'] = status_match.group(1).lower()
        
        version_match = re.search(r'\*\*Version:\*\*\s+([\d.]+)', content)
        if version_match:
            metadata['version'] = version_match.group(1)
        
        author_match = re.search(r'\*\*Author:\*\*\s+(.+)', content)
        if author_match:
            metadata['author'] = author_match.group(1).strip()
        
        # Extract sections
        sections = self._extract_sections(content)
        
        # Extract tags if present
        tags_match = re.search(r'\*\*Tags:\*\*\s+(.+)', content)
        if tags_match:
            tags_str = tags_match.group(1)
            metadata['tags'] = [tag.strip() for tag in tags_str.split(',')]
        
        # File statistics
        stat = doc_path.stat()
        metadata['file_size'] = stat.st_size
        metadata['last_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        metadata['created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
        
        return {
            'metadata': metadata,
            'sections': sections,
            'raw_content': content
        }
    
    def _parse_json(self, doc_path: Path) -> Dict[str, Any]:
        """Parse JSON governance document."""
        with open(doc_path, 'r') as f:
            document = json.load(f)
        
        metadata = document.get('metadata', {})
        metadata['path'] = str(doc_path)
        metadata['format'] = 'json'
        
        # File statistics
        stat = doc_path.stat()
        metadata['file_size'] = stat.st_size
        metadata['last_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        metadata['created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
        
        return {
            'metadata': metadata,
            'sections': document.get('sections', {}),
            'raw_content': json.dumps(document, indent=2)
        }
    
    def _extract_sections(self, content: str) -> Dict[str, str]:
        """Extract sections from markdown content."""
        sections = {}
        
        # Split by level-2 headers
        section_pattern = re.compile(r'^## (.+?)$', re.MULTILINE)
        section_matches = list(section_pattern.finditer(content))
        
        for i, match in enumerate(section_matches):
            section_name = match.group(1).strip()
            start_pos = match.end()
            
            # Find end position (next section or end of document)
            if i < len(section_matches) - 1:
                end_pos = section_matches[i + 1].start()
            else:
                end_pos = len(content)
            
            section_content = content[start_pos:end_pos].strip()
            sections[section_name] = section_content
        
        return sections
    
    def parse_directory(self, dir_path: Path) -> List[Dict[str, Any]]:
        """Parse all governance documents in a directory.
        
        Args:
            dir_path: Path to directory containing documents
            
        Returns:
            List of parsed document metadata
        """
        parsed_docs = []
        
        # Parse markdown documents
        for doc_path in dir_path.rglob('*.md'):
            if doc_path.name != 'README.md':
                try:
                    parsed = self.parse_document(doc_path)
                    parsed_docs.append(parsed)
                except Exception as e:
                    print(f"Error parsing {doc_path}: {e}")
        
        # Parse JSON documents
        for doc_path in dir_path.rglob('*.json'):
            try:
                parsed = self.parse_document(doc_path)
                parsed_docs.append(parsed)
            except Exception as e:
                print(f"Error parsing {doc_path}: {e}")
        
        return parsed_docs
    
    def export_metadata(self, parsed_doc: Dict[str, Any], format: str = 'yaml') -> str:
        """Export parsed document metadata in specified format.
        
        Args:
            parsed_doc: Parsed document dictionary
            format: Output format ('yaml' or 'json')
            
        Returns:
            Formatted metadata string
        """
        metadata = parsed_doc['metadata']
        
        if format == 'json':
            return json.dumps(metadata, indent=2)
        elif format == 'yaml':
            return yaml.dump(metadata, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
