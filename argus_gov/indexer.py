"""Document indexer for Argus governance toolkit."""

import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import re


class DocumentIndexer:
    """Creates searchable indexes of governance documents."""
    
    def create_index(self, docs_dir: Path, output_path: Path) -> Path:
        """Create a searchable index of all governance documents.
        
        Args:
            docs_dir: Directory containing governance documents
            output_path: Path to save the index file
            
        Returns:
            Path to the created index file
        """
        index = {
            'metadata': {
                'created': datetime.now().isoformat(),
                'total_documents': 0,
                'indexed_directories': [str(docs_dir)]
            },
            'documents': []
        }
        
        # Index markdown documents
        for doc_path in docs_dir.rglob('*.md'):
            if doc_path.name != 'README.md':  # Skip README files
                doc_info = self._index_markdown(doc_path, docs_dir)
                if doc_info:
                    index['documents'].append(doc_info)
        
        # Index JSON documents
        for doc_path in docs_dir.rglob('*.json'):
            doc_info = self._index_json(doc_path, docs_dir)
            if doc_info:
                index['documents'].append(doc_info)
        
        index['metadata']['total_documents'] = len(index['documents'])
        
        # Save index
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(index, indent=2))
        
        return output_path
    
    def _index_markdown(self, doc_path: Path, base_dir: Path) -> Dict[str, Any]:
        """Index a markdown document."""
        try:
            content = doc_path.read_text()
            
            # Extract metadata
            title_match = re.search(r'^# (.+)', content, re.MULTILINE)
            title = title_match.group(1) if title_match else doc_path.stem
            
            type_match = re.search(r'\*\*Type:\*\*\s+(\w+)', content)
            doc_type = type_match.group(1).lower() if type_match else 'unknown'
            
            status_match = re.search(r'\*\*Status:\*\*\s+(\w+)', content)
            status = status_match.group(1).lower() if status_match else 'unknown'
            
            date_match = re.search(r'\*\*Date:\*\*\s+([\d-]+)', content)
            created = date_match.group(1) if date_match else None
            
            # Extract sections
            sections = re.findall(r'^## (.+)', content, re.MULTILINE)
            
            # Create search excerpt (first 200 chars of content)
            content_clean = re.sub(r'[#*_\[\]]', '', content)
            excerpt = ' '.join(content_clean.split()[:30])
            
            return {
                'path': str(doc_path.relative_to(base_dir)),
                'title': title,
                'type': doc_type,
                'status': status,
                'created': created,
                'format': 'markdown',
                'sections': sections,
                'excerpt': excerpt,
                'last_modified': datetime.fromtimestamp(doc_path.stat().st_mtime).isoformat()
            }
        except Exception as e:
            print(f"Error indexing {doc_path}: {e}")
            return None
    
    def _index_json(self, doc_path: Path, base_dir: Path) -> Dict[str, Any]:
        """Index a JSON document."""
        try:
            with open(doc_path, 'r') as f:
                document = json.load(f)
            
            metadata = document.get('metadata', {})
            sections = list(document.get('sections', {}).keys())
            
            # Create excerpt from sections
            section_texts = []
            for section, content in document.get('sections', {}).items():
                if content:
                    section_texts.append(f"{section}: {content[:50]}")
            excerpt = ' | '.join(section_texts[:3])
            
            return {
                'path': str(doc_path.relative_to(base_dir)),
                'title': metadata.get('title', doc_path.stem),
                'type': metadata.get('type', 'unknown'),
                'status': metadata.get('status', 'unknown'),
                'created': metadata.get('created'),
                'format': 'json',
                'sections': sections,
                'excerpt': excerpt,
                'last_modified': datetime.fromtimestamp(doc_path.stat().st_mtime).isoformat()
            }
        except Exception as e:
            print(f"Error indexing {doc_path}: {e}")
            return None
    
    def search_index(self, index_path: Path, query: str) -> List[Dict[str, Any]]:
        """Search the document index.
        
        Args:
            index_path: Path to the index file
            query: Search query string
            
        Returns:
            List of matching documents
        """
        try:
            with open(index_path, 'r') as f:
                index = json.load(f)
        except FileNotFoundError:
            return []
        
        query_lower = query.lower()
        results = []
        
        for doc in index['documents']:
            # Search in title, type, excerpt, and sections
            searchable = [
                doc.get('title', ''),
                doc.get('type', ''),
                doc.get('excerpt', ''),
                ' '.join(doc.get('sections', []))
            ]
            
            searchable_text = ' '.join(searchable).lower()
            
            if query_lower in searchable_text:
                results.append(doc)
        
        return results
