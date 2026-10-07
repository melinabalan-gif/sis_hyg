import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { ESLint } from "eslint";

const eslint = new ESLint();
const lint = async (source) =>
  (await eslint.lintText(source, { filePath: "src/lint-probe.tsx" }))[0]
    .messages;

test("lint dependency tree excludes unpatched glob expansion", async () => {
  const lock = JSON.parse(await readFile("package-lock.json", "utf8"));
  assert.equal(
    Object.keys(lock.packages).some((path) => path.endsWith("/braces")),
    false,
  );
});

for (const [name, source, rule] of [
  [
    "conditional hook",
    'import {useState} from "react"; export function Example({yes}: {yes: boolean}) { if (yes) useState(0); return null; }',
    "react-hooks/rules-of-hooks",
  ],
  [
    "explicit any",
    "export const example: any = 1;",
    "@typescript-eslint/no-explicit-any",
  ],
  [
    "invalid aria",
    'export const Example = () => <button aria-unknown="x">Save</button>;',
    "jsx-a11y/aria-props",
  ],
  [
    "internal raw anchor",
    'export const Example = () => <a href="/worksites">Worksites</a>;',
    "no-restricted-syntax",
  ],
  [
    "raw image",
    'export const Example = () => <img alt="Synthetic" src="/og.png" />;',
    "no-restricted-syntax",
  ],
  [
    "sync script",
    'export const Example = () => <script src="/example.js" />;',
    "no-restricted-syntax",
  ],
  [
    "document import",
    'import Document from "next/document"; export default Document;',
    "no-restricted-imports",
  ],
]) {
  test(`rejects ${name}`, async () => {
    assert.ok((await lint(source)).some((message) => message.ruleId === rule));
  });
}

test("allows Next navigation and typed JSX", async () => {
  assert.deepEqual(
    await lint(
      'import Link from "next/link"; export const Example = () => <Link href="/worksites">Worksites</Link>;',
    ),
    [],
  );
});
