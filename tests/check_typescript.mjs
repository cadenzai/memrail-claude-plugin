// Type-check the actual Markdown examples against a built SDK checkout.
// node tests/check_typescript.mjs /path/to/memrail_api/sdk-ts
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sdk = path.resolve(process.argv[2]);
const require = createRequire(path.join(sdk, 'package.json'));
const ts = require('typescript');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'memrail-skill-examples-'));
const files = [];
try {
  for (const name of ['05b-sdk-integration-typescript.md', '09-tool-registry-executors.md']) {
    const markdown = fs.readFileSync(path.join(root, 'skills/memrail/references', name), 'utf8');
    let index = 0;
    for (const [, code] of markdown.matchAll(/^```typescript\n(.*?)^```/gms)) {
      const source = ts.createSourceFile('example.ts', code, ts.ScriptTarget.ES2022, true);
      const declared = new Set();
      for (const node of source.statements) {
        if (ts.isVariableStatement(node)) {
          for (const declaration of node.declarationList.declarations) declared.add(declaration.name.getText());
        }
        if (ts.isFunctionDeclaration(node)) declared.add(node.name?.text);
      }
      // Context supplied by the immediately preceding example, fully typed.
      let prefix = 'import type * as SkillSDK from "@memrail/sdk";\n';
      for (const [variable, type] of [['registry', 'ToolRegistry'], ['executor', 'ActionExecutor'], ['client', 'AMIClient']]) {
        if (!declared.has(variable)) prefix += `declare const ${variable}: SkillSDK.${type};\n`;
      }
      const file = path.join(temp, `${name}-${index++}.ts`);
      fs.writeFileSync(file, prefix + code);
      files.push(file);
    }
  }
  const program = ts.createProgram(files, {
    noEmit: true, strict: true, skipLibCheck: true,
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
    moduleResolution: ts.ModuleResolutionKind.Node10,
    baseUrl: sdk, paths: { '@memrail/sdk': [path.join(sdk, 'dist/index.d.ts')] },
    typeRoots: [path.join(sdk, 'node_modules/@types')],
  });
  const diagnostics = ts.getPreEmitDiagnostics(program);
  if (diagnostics.length) {
    console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
      getCurrentDirectory: () => root, getCanonicalFileName: x => x, getNewLine: () => '\n',
    }));
    process.exitCode = 1;
  } else {
    console.log(`Type-checked ${files.length} Markdown examples against the built SDK.`);
  }
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
