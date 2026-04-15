#!/usr/bin/env node
/**
 * Standalone script injected into Docker containers to introspect TypeScript schema packages.
 * Parses TypeScript AST for interfaces/types and outputs ClassifiedEntity JSON to stdout.
 * Usage: node ts_inspect.js <package_dir>
 */

const fs = require('fs');
const path = require('path');

function main() {
  const packageDir = process.argv[2];
  if (!packageDir) {
    console.error('Usage: node ts_inspect.js <package_dir>');
    process.exit(1);
  }

  const results = [];
  const tsFiles = findTsFiles(packageDir);

  for (const file of tsFiles) {
    const content = fs.readFileSync(file, 'utf-8');
    const relPath = path.relative(packageDir, file);

    // Simple regex-based interface/type extraction (no TS compiler needed)
    const interfaceRegex = /(?:export\s+)?interface\s+(\w+)\s*(?:extends\s+[\w,\s]+)?\s*\{([^}]*)\}/g;
    let match;
    while ((match = interfaceRegex.exec(content)) !== null) {
      const name = match[1];
      const body = match[2];
      const props = extractProperties(body);

      results.push({
        entity_type: 'class',
        semantic: { properties: props.map(p => p.name) },
        provenance: { source: path.basename(packageDir), class: name, name: name, description: '' },
        confidence: 0.85,
        source_context: { file: relPath, type: 'interface' },
      });

      for (const prop of props) {
        results.push({
          entity_type: 'attribute',
          semantic: { data_type: mapType(prop.type) },
          provenance: { source: path.basename(packageDir), class: name, name: prop.name, description: '' },
          confidence: 0.8,
          source_context: { file: relPath },
        });
      }
    }

    // Type aliases with object shape
    const typeRegex = /(?:export\s+)?type\s+(\w+)\s*=\s*\{([^}]*)\}/g;
    while ((match = typeRegex.exec(content)) !== null) {
      const name = match[1];
      const body = match[2];
      const props = extractProperties(body);

      results.push({
        entity_type: 'class',
        semantic: { properties: props.map(p => p.name) },
        provenance: { source: path.basename(packageDir), class: name, name: name, description: '' },
        confidence: 0.8,
        source_context: { file: relPath, type: 'type_alias' },
      });
    }

    // Enum declarations
    const enumRegex = /(?:export\s+)?enum\s+(\w+)\s*\{([^}]*)\}/g;
    while ((match = enumRegex.exec(content)) !== null) {
      const name = match[1];
      const body = match[2];
      const members = body.split(',').map(m => m.trim().split('=')[0].trim()).filter(Boolean);

      results.push({
        entity_type: 'valueset',
        semantic: { name: name, members: members.sort() },
        provenance: { source: path.basename(packageDir), class: '', name: name },
        confidence: 0.9,
        source_context: { file: relPath },
      });
    }
  }

  console.log(JSON.stringify(results, null, 2));
}

function findTsFiles(dir) {
  const files = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory() && entry.name !== 'node_modules' && entry.name !== '.git') {
        files.push(...findTsFiles(fullPath));
      } else if (entry.isFile() && (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) && !entry.name.endsWith('.d.ts')) {
        files.push(fullPath);
      }
    }
  } catch (e) { /* skip unreadable dirs */ }
  return files;
}

function extractProperties(body) {
  const props = [];
  const lines = body.split('\n');
  for (const line of lines) {
    const m = line.trim().match(/^(\w+)\??\s*:\s*(.+?)\s*;?\s*$/);
    if (m) {
      props.push({ name: m[1], type: m[2] });
    }
  }
  return props;
}

function mapType(tsType) {
  const t = tsType.toLowerCase().trim();
  if (t === 'number') return 'float';
  if (t === 'string') return 'string';
  if (t === 'boolean') return 'boolean';
  if (t.endsWith('[]') || t.startsWith('array')) return 'array';
  return 'string';
}

main();
