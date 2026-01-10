"""Command-line interface for Argus Governance Toolkit."""

import click
import sys
from pathlib import Path

from .generator import DocumentGenerator
from .validator import DocumentValidator
from .indexer import DocumentIndexer
from .parser import DocumentParser


@click.group()
@click.version_option(version='0.1.0', prog_name='argus_gov')
def cli():
    """Argus Governance Toolkit - CTO Authority Decision System."""
    pass


@cli.command()
@click.argument('decision_type', type=click.Choice(['architectural', 'technical', 'security']))
@click.option('--output', '-o', type=click.Path(), help='Output directory for generated documents')
@click.option('--format', '-f', type=click.Choice(['markdown', 'json']), default='markdown')
def generate(decision_type, output, format):
    """Generate a new governance document."""
    generator = DocumentGenerator()
    
    output_path = Path(output) if output else Path('docs')
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        doc_path = generator.generate_document(decision_type, output_path, format)
        click.echo(f"✅ Generated {decision_type} decision document: {doc_path}")
    except Exception as e:
        click.echo(f"❌ Error generating document: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('document_path', type=click.Path(exists=True))
def validate(document_path):
    """Validate a governance document against schema."""
    validator = DocumentValidator()
    
    try:
        is_valid, errors = validator.validate_document(Path(document_path))
        
        if is_valid:
            click.echo(f"✅ Document is valid: {document_path}")
        else:
            click.echo(f"❌ Document validation failed: {document_path}")
            for error in errors:
                click.echo(f"  - {error}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error validating document: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('docs_directory', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), default='index.json')
def index(docs_directory, output):
    """Create searchable index of governance documents."""
    indexer = DocumentIndexer()
    
    try:
        index_path = indexer.create_index(Path(docs_directory), Path(output))
        click.echo(f"✅ Created document index: {index_path}")
    except Exception as e:
        click.echo(f"❌ Error creating index: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('document_path', type=click.Path(exists=True))
@click.option('--format', '-f', type=click.Choice(['yaml', 'json']), default='yaml')
def parse(document_path, format):
    """Parse and extract metadata from governance document."""
    parser = DocumentParser()
    
    try:
        metadata = parser.parse_document(Path(document_path))
        
        if format == 'json':
            import json
            click.echo(json.dumps(metadata, indent=2))
        else:
            import yaml
            click.echo(yaml.dump(metadata, default_flow_style=False))
    except Exception as e:
        click.echo(f"❌ Error parsing document: {e}", err=True)
        sys.exit(1)


@cli.command()
def init():
    """Initialize Argus governance structure in current directory."""
    directories = ['docs/decisions', 'docs/architecture', 'docs/technical']
    
    try:
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            click.echo(f"✅ Created {directory}")
        
        click.echo("\n✅ Argus governance structure initialized successfully!")
    except Exception as e:
        click.echo(f"❌ Error initializing structure: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
