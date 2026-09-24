import { readFileSync, writeFileSync } from 'node:fs'

const report = new URL('../coverage/lcov.info', import.meta.url)
const coverage = readFileSync(report, 'utf8')

// SonarQube scans from the repository root, so LCOV paths need the frontend prefix.
writeFileSync(report, coverage.replace(/^SF:src\//gm, 'SF:frontend/src/'))
