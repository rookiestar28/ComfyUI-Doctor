#!/usr/bin/env node
/**
 * Preflight JS Syntax Validation (5B.4)
 * 
 * Parses all JavaScript files in web/ as ESM modules to catch syntax errors
 * before runtime. Uses acorn parser for accurate ESM parsing.
 * 
 * Usage: npm run preflight:js
 * Exit code: 0 = success, 1 = syntax errors found
 */

import { readdir, readFile } from 'fs/promises';
import { join, relative } from 'path';
import { fileURLToPath } from 'url';
import * as acorn from 'acorn';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const WEB_DIR = join(__dirname, '..', 'web');

// Recursively find all .js files
async function findJsFiles(dir) {
    const files = [];
    const entries = await readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
        const fullPath = join(dir, entry.name);
        if (entry.isDirectory()) {
            // Skip node_modules and lib (vendor files)
            if (entry.name === 'node_modules' || entry.name === 'lib') continue;
            files.push(...await findJsFiles(fullPath));
        } else if (entry.name.endsWith('.js')) {
            files.push(fullPath);
        }
    }
    return files;
}

// Validate a single JS file as ESM
async function validateFile(filePath) {
    const content = await readFile(filePath, 'utf-8');
    const relativePath = relative(join(__dirname, '..'), filePath);

    try {
        acorn.parse(content, {
            ecmaVersion: 'latest',
            sourceType: 'module',
            locations: true
        });
        return { file: relativePath, valid: true };
    } catch (error) {
        return {
            file: relativePath,
            valid: false,
            error: error.message,
            line: error.loc?.line || null,
            column: error.loc?.column || null
        };
    }
}

// Main execution
async function main() {
    console.log('🔍 Preflight JS Syntax Check (acorn)\n');
    console.log(`Scanning: ${WEB_DIR}\n`);

    const files = await findJsFiles(WEB_DIR);
    console.log(`Found ${files.length} JavaScript files\n`);

    const results = await Promise.all(files.map(validateFile));

    const errors = results.filter(r => !r.valid);
    const valid = results.filter(r => r.valid);

    // Report valid files
    for (const r of valid) {
        console.log(`✅ ${r.file}`);
    }

    // Report errors
    if (errors.length > 0) {
        console.log('\n❌ Syntax Errors Found:\n');
        for (const r of errors) {
            console.log(`  ❌ ${r.file}`);
            console.log(`     ${r.error}`);
            if (r.line) console.log(`     Line: ${r.line}, Column: ${r.column}`);
            console.log('');
        }
        console.log(`\n🚫 ${errors.length} file(s) with syntax errors`);
        process.exit(1);
    }

    console.log(`\n✅ All ${valid.length} files passed syntax check`);
    process.exit(0);
}

main().catch(err => {
    console.error('Preflight check failed:', err);
    process.exit(1);
});
