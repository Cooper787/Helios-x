"""Command-line interface for Argus Governance Toolkit.

Stdlib-only (argparse). Exit codes: 0 = success, 1 = validation failure, 2 = error.
"""

import argparse
import json
import sys
from pathlib import Path

from .generator import DocumentGenerator
from .indexer import DocumentIndexer
from .parser import DocumentParser
from .validator import DocumentValidator

EXIT_OK = 0
EXIT_VALIDATION_FAILED = 1
EXIT_ERROR = 2


def _cmd_generate(args: argparse.Namespace) -> int:
    generator = DocumentGenerator()
    output_path = Path(args.output) if args.output else Path("docs")
    output_path.mkdir(parents=True, exist_ok=True)
    try:
        doc_path = generator.generate_document(args.decision_type, output_path, args.format)
        print(f"Generated {args.decision_type} decision document: {doc_path}")
        return EXIT_OK
    except Exception as e:
        print(f"Error generating document: {e}", file=sys.stderr)
        return EXIT_ERROR


def _cmd_validate(args: argparse.Namespace) -> int:
    doc_path = Path(args.document_path)
    if not doc_path.exists():
        print(f"Error: path does not exist: {doc_path}", file=sys.stderr)
        return EXIT_ERROR
    validator = DocumentValidator()
    try:
        is_valid, errors = validator.validate_document(doc_path)
        if is_valid:
            print(f"Document is valid: {doc_path}")
            return EXIT_OK
        print(f"Document validation failed: {doc_path}")
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    except Exception as e:
        print(f"Error validating document: {e}", file=sys.stderr)
        return EXIT_ERROR


def _cmd_index(args: argparse.Namespace) -> int:
    docs_dir = Path(args.docs_directory)
    if not docs_dir.exists():
        print(f"Error: directory does not exist: {docs_dir}", file=sys.stderr)
        return EXIT_ERROR
    indexer = DocumentIndexer()
    try:
        index_path = indexer.create_index(docs_dir, Path(args.output))
        print(f"Created document index: {index_path}")
        return EXIT_OK
    except Exception as e:
        print(f"Error creating index: {e}", file=sys.stderr)
        return EXIT_ERROR


def _cmd_parse(args: argparse.Namespace) -> int:
    doc_path = Path(args.document_path)
    if not doc_path.exists():
        print(f"Error: path does not exist: {doc_path}", file=sys.stderr)
        return EXIT_ERROR
    parser = DocumentParser()
    try:
        metadata = parser.parse_document(doc_path)
        if args.format == "json":
            print(json.dumps(metadata, indent=2, default=str))
        else:
            import yaml  # optional dependency, only needed for yaml output

            print(yaml.dump(metadata, default_flow_style=False))
        return EXIT_OK
    except Exception as e:
        print(f"Error parsing document: {e}", file=sys.stderr)
        return EXIT_ERROR


def _cmd_init(args: argparse.Namespace) -> int:
    directories = ["docs/decisions", "docs/architecture", "docs/technical"]
    try:
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            print(f"Created {directory}")
        print("Argus governance structure initialized successfully.")
        return EXIT_OK
    except Exception as e:
        print(f"Error initializing structure: {e}", file=sys.stderr)
        return EXIT_ERROR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="argus_gov",
        description="Argus Governance Toolkit - CTO Authority Decision System",
    )
    parser.add_argument("--version", action="version", version="argus_gov 0.1.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_gen = subparsers.add_parser("generate", help="Generate a new governance document")
    p_gen.add_argument("decision_type", choices=["architectural", "technical", "security"])
    p_gen.add_argument("--output", "-o", help="Output directory for generated documents")
    p_gen.add_argument("--format", "-f", choices=["markdown", "json"], default="markdown")
    p_gen.set_defaults(func=_cmd_generate)

    p_val = subparsers.add_parser("validate", help="Validate a governance document")
    p_val.add_argument("document_path")
    p_val.set_defaults(func=_cmd_validate)

    p_idx = subparsers.add_parser("index", help="Create searchable index of documents")
    p_idx.add_argument("docs_directory")
    p_idx.add_argument("--output", "-o", default="index.json")
    p_idx.set_defaults(func=_cmd_index)

    p_par = subparsers.add_parser("parse", help="Parse and extract document metadata")
    p_par.add_argument("document_path")
    p_par.add_argument("--format", "-f", choices=["yaml", "json"], default="json")
    p_par.set_defaults(func=_cmd_parse)

    p_init = subparsers.add_parser("init", help="Initialize governance structure")
    p_init.set_defaults(func=_cmd_init)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
