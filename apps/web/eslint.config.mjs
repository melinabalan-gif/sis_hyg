import { defineConfig, globalIgnores } from "eslint/config";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import hooks from "eslint-plugin-react-hooks";
import a11y from "eslint-plugin-jsx-a11y";
import globals from "globals";

export default defineConfig([
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{js,mjs,ts,tsx}"],
    plugins: { react, "react-hooks": hooks, "jsx-a11y": a11y },
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    settings: { react: { version: "detect" } },
    rules: {
      ...react.configs.recommended.rules,
      ...hooks.configs.recommended.rules,
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      "react/no-unknown-property": "off",
      "react/jsx-no-target-blank": "off",
      "jsx-a11y/alt-text": ["error", { elements: ["img"], img: ["Image"] }],
      "jsx-a11y/aria-props": "error",
      "jsx-a11y/aria-proptypes": "error",
      "jsx-a11y/aria-unsupported-elements": "error",
      "jsx-a11y/role-has-required-aria-props": "error",
      "jsx-a11y/role-supports-aria-props": "error",
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "next/document",
              message: "App Router uses app/layout.tsx, not next/document.",
            },
            { name: "next/head", message: "App Router uses the metadata API." },
          ],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXOpeningElement[name.name='img']",
          message: "Use next/image for image elements.",
        },
        {
          selector: "JSXOpeningElement[name.name='head']",
          message: "Use App Router metadata.",
        },
        {
          selector: "JSXOpeningElement[name.name='script']",
          message: "Use next/script for scripts.",
        },
        {
          selector:
            "JSXOpeningElement[name.name='a'] > JSXAttribute[name.name='href'][value.value=/^\\//]",
          message: "Use next/link for internal navigation.",
        },
      ],
    },
  },
  {
    files: ["src/generated/api/**/*.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
  globalIgnores([
    ".next/**",
    "coverage/**",
    "next-env.d.ts",
    "test-results/**",
    "playwright-report/**",
  ]),
]);
