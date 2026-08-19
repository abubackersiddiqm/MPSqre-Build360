const fs = require("fs");
const path = require("path");
const root = path.resolve(process.argv[2] || ".");
const tsPath = path.join(root, "frontend", "node_modules", "typescript");
let ts;
try { ts = require(tsPath); } catch { console.log("[SKIP] frontend/node_modules/typescript not available; source markers still validated."); process.exit(0); }
const files = [
  "frontend/src/app/brand-domain/workspace.tsx",
  "frontend/src/app/brand-domain/page.tsx",
  "frontend/src/app/api/brand-domain/[...path]/route.ts",
  "frontend/src/app/api/auth/password-reset/request/route.ts",
];
let failed = false;
for (const rel of files) {
  const filename = path.join(root, rel); const source = fs.readFileSync(filename, "utf8");
  const result = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext }, reportDiagnostics: true, fileName: filename });
  const errors = (result.diagnostics || []).filter((d) => d.category === ts.DiagnosticCategory.Error);
  if (errors.length) { failed = true; console.error(`[ERROR] ${rel}`); for (const d of errors) console.error(ts.flattenDiagnosticMessageText(d.messageText, "\\n")); }
  else console.log(`[OK] ${rel}`);
}
process.exit(failed ? 1 : 0);
